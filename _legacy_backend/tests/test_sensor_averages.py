"""Tests for calculating averages across user-selected sensors."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models import SensorPoint, SensorReading


def seed_average_data(db: Session) -> tuple[SensorPoint, SensorPoint]:
    power = SensorPoint(
        sensor_code="POWER_1",
        trend_column="POWER_1_TREND",
        display_name="Main Power",
        category="Energy",
        raw_unit="W",
        display_unit="kW",
        scale_factor=0.001,
        location="Main floor",
        is_selected=True,
    )
    temperature = SensorPoint(
        sensor_code="TEMP_1",
        trend_column="TEMP_1_TREND",
        display_name="Lobby Temperature",
        category="Temperature",
        raw_unit="°C",
        display_unit="°C",
        scale_factor=1.0,
        location="Lobby",
        is_selected=True,
    )
    db.add_all([power, temperature])
    db.flush()

    db.add_all(
        [
            SensorReading(
                sensor_point_id=power.sensor_point_id,
                reading_time=datetime(2025, 1, 1, 10, 0),
                value=1000.0,
            ),
            SensorReading(
                sensor_point_id=power.sensor_point_id,
                reading_time=datetime(2025, 1, 1, 11, 0),
                value=3000.0,
            ),
            SensorReading(
                sensor_point_id=temperature.sensor_point_id,
                reading_time=datetime(2025, 1, 1, 10, 0),
                value=20.0,
            ),
            SensorReading(
                sensor_point_id=temperature.sensor_point_id,
                reading_time=datetime(2025, 1, 2, 10, 0),
                value=24.0,
            ),
        ]
    )
    db.commit()
    return power, temperature


def test_selected_sensor_averages_are_scaled_and_returned_in_request_order(
    client: TestClient,
    db_session: Session,
):
    seed_average_data(db_session)

    response = client.post(
        "/api/v1/sensors/averages",
        json={"sensorCodes": ["TEMP_1", "POWER_1"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requestedSensorCount"] == 2
    assert payload["returnedSensorCount"] == 2
    assert [item["sensorCode"] for item in payload["sensors"]] == [
        "TEMP_1",
        "POWER_1",
    ]

    temperature, power = payload["sensors"]
    assert temperature["readingCount"] == 2
    assert temperature["averageValue"] == 22.0
    assert temperature["minimumValue"] == 20.0
    assert temperature["maximumValue"] == 24.0

    assert power["readingCount"] == 2
    assert power["averageValue"] == 2.0
    assert power["minimumValue"] == 1.0
    assert power["maximumValue"] == 3.0


def test_selected_sensor_averages_support_date_filtering(
    client: TestClient,
    db_session: Session,
):
    seed_average_data(db_session)

    response = client.post(
        "/api/v1/sensors/averages",
        json={
            "sensorCodes": ["TEMP_1"],
            "start": "2025-01-02T00:00:00",
            "end": "2025-01-02T23:59:59",
        },
    )

    assert response.status_code == 200
    result = response.json()["sensors"][0]
    assert result["readingCount"] == 1
    assert result["averageValue"] == 24.0
    assert result["firstTimestamp"] == "2025-01-02T10:00:00"
    assert result["lastTimestamp"] == "2025-01-02T10:00:00"


def test_missing_sensor_codes_are_reported(
    client: TestClient,
    db_session: Session,
):
    seed_average_data(db_session)

    response = client.post(
        "/api/v1/sensors/averages",
        json={"sensorCodes": ["TEMP_1", "UNKNOWN"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["returnedSensorCount"] == 1
    assert payload["missingSensorCodes"] == ["UNKNOWN"]


def test_invalid_average_date_range_returns_400(
    client: TestClient,
    db_session: Session,
):
    seed_average_data(db_session)

    response = client.post(
        "/api/v1/sensors/averages",
        json={
            "sensorCodes": ["TEMP_1"],
            "start": "2025-01-03T00:00:00",
            "end": "2025-01-02T00:00:00",
        },
    )

    assert response.status_code == 400
    assert "start timestamp" in response.json()["detail"]
