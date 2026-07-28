from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models import SensorPoint, SensorReading


def seed_cumulative_consumption(db: Session) -> SensorPoint:
    sensor = SensorPoint(
        sensor_code="30000_TL337",
        trend_column="SaitSolarLab_30000_TL337",
        display_name="GBT Consumption Wh",
        category="Energy",
        priority="P1",
        raw_unit="Wh",
        display_unit="Wh",
        scale_factor=1.0,
        sign_convention=(
            "The cumulative consumption counter becomes more negative as "
            "energy is used."
        ),
        data_type="cumulative_consumption_energy",
        location="GBTAC building",
        is_selected=True,
    )
    db.add(sensor)
    db.flush()
    db.add_all(
        [
            SensorReading(
                sensor_point_id=sensor.sensor_point_id,
                reading_time=datetime(2025, 1, 1, 12, 0),
                value=-1_500_000.0,
            ),
            SensorReading(
                sensor_point_id=sensor.sensor_point_id,
                reading_time=datetime(2025, 1, 1, 13, 0),
                value=-1_500_500.0,
            ),
            SensorReading(
                sensor_point_id=sensor.sensor_point_id,
                reading_time=datetime(2025, 1, 1, 14, 0),
                value=-1_501_250.0,
            ),
        ]
    )
    db.commit()
    return sensor


def test_daily_energy_is_derived_from_cumulative_wh(
    client: TestClient,
    db_session: Session,
):
    seed_cumulative_consumption(db_session)

    response = client.get(
        "/api/v1/dashboard/energy-consumption",
        params={"interval": "day"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["counterDirection"] == "decreasing"
    assert payload["sourceUnit"] == "Wh"
    assert payload["pointCount"] == 1

    point = payload["points"][0]
    assert point["timestamp"] == "2025-01-01T00:00:00"
    assert point["energyWh"] == 1250.0
    assert point["energyKwh"] == 1.25
    assert point["durationHours"] == 2.0
    assert point["averageWatts"] == 625.0
    assert point["count"] == 2


def test_date_filter_uses_reading_before_start_for_first_delta(
    client: TestClient,
    db_session: Session,
):
    seed_cumulative_consumption(db_session)

    response = client.get(
        "/api/v1/dashboard/energy-consumption",
        params={
            "start": "2025-01-01T13:00:00",
            "end": "2025-01-01T13:00:00",
            "interval": "raw",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pointCount"] == 1
    assert payload["points"][0]["energyWh"] == 500.0
    assert payload["points"][0]["averageWatts"] == 500.0


def test_counter_reversal_is_skipped_instead_of_becoming_false_usage(
    client: TestClient,
    db_session: Session,
):
    sensor = seed_cumulative_consumption(db_session)
    db_session.add(
        SensorReading(
            sensor_point_id=sensor.sensor_point_id,
            reading_time=datetime(2025, 1, 1, 15, 0),
            value=-1_500_000.0,
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/dashboard/energy-consumption",
        params={"interval": "raw"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pointCount"] == 2
    assert payload["skippedCounterChanges"] == 1
