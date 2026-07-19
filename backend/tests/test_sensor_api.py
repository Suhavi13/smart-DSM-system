from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models import SensorPoint, SensorReading


def seed_site_consumption(db: Session) -> SensorPoint:
    sensor = SensorPoint(
        sensor_code="30000_TL342",
        trend_column="SaitSolarLab_30000_TL342",
        display_name="GBT Site Consumption",
        category="Energy",
        priority="P1",
        raw_unit="W",
        display_unit="kW",
        scale_factor=0.001,
        data_type="power",
        location="GBTAC building",
        is_selected=True,
    )
    db.add(sensor)
    db.flush()

    db.add_all(
        [
            SensorReading(
                sensor_point_id=sensor.sensor_point_id,
                reading_time=datetime(2025, 1, 1, 10, 5),
                value=1000.0,
            ),
            SensorReading(
                sensor_point_id=sensor.sensor_point_id,
                reading_time=datetime(2025, 1, 1, 10, 35),
                value=3000.0,
            ),
            SensorReading(
                sensor_point_id=sensor.sensor_point_id,
                reading_time=datetime(2025, 1, 1, 11, 0),
                value=-1000.0,
            ),
        ]
    )
    db.commit()
    return sensor


def test_sensor_list_can_include_latest_reading(
    client: TestClient,
    db_session: Session,
):
    seed_site_consumption(db_session)

    response = client.get("/api/v1/sensors?includeLatest=true")

    assert response.status_code == 200
    sensor = response.json()[0]
    assert sensor["hasReadings"] is True
    assert sensor["latestRawValue"] == -1000.0
    assert sensor["latestValue"] == -1.0
    assert sensor["latestTimestamp"] == "2025-01-01T11:00:00"


def test_readings_support_date_filtering(
    client: TestClient,
    db_session: Session,
):
    seed_site_consumption(db_session)

    response = client.get(
        "/api/v1/sensors/30000_TL342/readings",
        params={
            "start": "2025-01-01T10:30:00",
            "end": "2025-01-01T11:00:00",
            "interval": "raw",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pointCount"] == 2
    assert [point["value"] for point in payload["points"]] == [3.0, -1.0]


def test_readings_support_hourly_aggregation(
    client: TestClient,
    db_session: Session,
):
    seed_site_consumption(db_session)

    response = client.get(
        "/api/v1/sensors/30000_TL342/readings",
        params={"interval": "hour"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pointCount"] == 2

    first_hour = payload["points"][0]
    assert first_hour["timestamp"] == "2025-01-01T10:00:00"
    assert first_hour["value"] == 2.0
    assert first_hour["minimumValue"] == 1.0
    assert first_hour["maximumValue"] == 3.0
    assert first_hour["count"] == 2


def test_invalid_date_range_returns_400(
    client: TestClient,
    db_session: Session,
):
    seed_site_consumption(db_session)

    response = client.get(
        "/api/v1/sensors/30000_TL342/readings",
        params={
            "start": "2025-01-02T00:00:00",
            "end": "2025-01-01T00:00:00",
        },
    )

    assert response.status_code == 400
    assert "start timestamp" in response.json()["detail"]


def test_missing_sensor_returns_404(client: TestClient):
    response = client.get("/api/v1/sensors/UNKNOWN/readings")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sensor not found."
