from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models import SensorPoint, SensorReading


def add_sensor(
    db: Session,
    *,
    code: str,
    name: str,
    raw_unit: str,
    display_unit: str,
    scale_factor: float,
    data_type: str,
    readings: list[tuple[datetime, float]],
) -> SensorPoint:
    sensor = SensorPoint(
        sensor_code=code,
        trend_column=f"SaitSolarLab_{code}",
        display_name=name,
        category="Energy",
        priority="P1",
        raw_unit=raw_unit,
        display_unit=display_unit,
        scale_factor=scale_factor,
        data_type=data_type,
        location="GBTAC building",
        is_selected=True,
    )
    db.add(sensor)
    db.flush()
    db.add_all(
        SensorReading(
            sensor_point_id=sensor.sensor_point_id,
            reading_time=timestamp,
            value=value,
        )
        for timestamp, value in readings
    )
    return sensor


def test_daily_energy_uses_positive_cumulative_kwh_deltas(
    client: TestClient,
    db_session: Session,
):
    add_sensor(
        db_session,
        code="30000_TL388",
        name="GBT Totalized Energy",
        raw_unit="kWh",
        display_unit="kWh",
        scale_factor=1.0,
        data_type="cumulative_energy",
        readings=[
            (datetime(2025, 12, 30, 23, 59), 1000.0),
            (datetime(2025, 12, 31, 0, 5), 1000.5),
            (datetime(2025, 12, 31, 12, 0), 1003.0),
            (datetime(2025, 12, 31, 18, 0), 900.0),  # reset: ignored
            (datetime(2025, 12, 31, 23, 59), 901.0),
        ],
    )
    db_session.commit()

    response = client.get(
        "/api/v1/dashboard/daily-energy-usage",
        params={
            "start": "2025-12-31T00:00:00",
            "end": "2025-12-31T23:59:59",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sensor"]["sensorCode"] == "30000_TL388"
    assert payload["calculation"]["wattHourFormula"] == "Wh = kWh × 1,000"
    assert payload["pointCount"] == 1

    point = payload["points"][0]
    assert point["energyKwh"] == 4.0
    assert point["energyWh"] == 4000.0
    assert point["ignoredNegativeDeltaCount"] == 1


def test_site_demand_endpoint_returns_watts_even_with_old_kw_metadata(
    client: TestClient,
    db_session: Session,
):
    add_sensor(
        db_session,
        code="30000_TL342",
        name="GBT Site Consumption",
        raw_unit="W",
        display_unit="kW",
        scale_factor=0.001,
        data_type="power",
        readings=[
            (datetime(2025, 12, 31, 10, 0), -8000.0),
            (datetime(2025, 12, 31, 10, 30), -7000.0),
        ],
    )
    db_session.commit()

    response = client.get(
        "/api/v1/dashboard/site-consumption",
        params={"interval": "hour"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sensor"]["displayUnit"] == "W"
    assert payload["sensor"]["scaleFactor"] == 1.0
    assert payload["points"][0]["value"] == -7500.0
    assert payload["points"][0]["minimumValue"] == -8000.0
    assert payload["points"][0]["maximumValue"] == -7000.0
