from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models import SensorPoint, SensorReading


def add_temperature_sensor(
    db: Session,
    sensor_code: str,
    readings: list[tuple[datetime, float]],
    data_type: str,
) -> SensorPoint:
    sensor = SensorPoint(
        sensor_code=sensor_code,
        trend_column=f"SaitSolarLab_{sensor_code}",
        display_name=sensor_code,
        category="Temperature",
        raw_unit="°C",
        display_unit="°C",
        scale_factor=1.0,
        data_type=data_type,
        location="Inside building",
        is_selected=True,
    )
    db.add(sensor)
    db.flush()
    db.add_all(
        [
            SensorReading(
                sensor_point_id=sensor.sensor_point_id,
                reading_time=reading_time,
                value=value,
            )
            for reading_time, value in readings
        ]
    )
    return sensor


def test_indoor_conditions_average_ambient_and_wall_sensors_equally(
    client: TestClient,
    db_session: Session,
):
    # The first sensor reports twice. Its hourly average is 20 °C, and it must
    # still receive the same weight as each other sensor.
    add_temperature_sensor(
        db_session,
        "20003_TL2",
        [
            (datetime(2025, 1, 1, 10, 5), 10.0),
            (datetime(2025, 1, 1, 10, 35), 30.0),
        ],
        "ambient_temperature",
    )
    add_temperature_sensor(
        db_session,
        "20004_TL2",
        [(datetime(2025, 1, 1, 10, 15), 40.0)],
        "ambient_temperature",
    )
    add_temperature_sensor(
        db_session,
        "30000_TL55",
        [(datetime(2025, 1, 1, 10, 25), 30.0)],
        "wall_temperature",
    )
    db_session.commit()

    response = client.get(
        "/api/v1/dashboard/indoor-conditions",
        params={"interval": "hour"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["configuredTemperatureSensorCount"] == 31
    assert payload["availableTemperatureSensorCount"] == 3
    assert payload["ambientTemperatureSensorCount"] == 14
    assert payload["wallTemperatureSensorCount"] == 17
    assert payload["pointCount"] == 1

    point = payload["points"][0]
    assert point["timestamp"] == "2025-01-01T10:00:00"
    assert point["averageTemperatureC"] == 30.0
    assert point["minimumTemperatureC"] == 20.0
    assert point["maximumTemperatureC"] == 40.0
    assert point["contributingSensorCount"] == 3
    assert "co2Ppm" not in point


def test_indoor_conditions_ignores_missing_sensor_readings(
    client: TestClient,
    db_session: Session,
):
    add_temperature_sensor(
        db_session,
        "20003_TL2",
        [(datetime(2025, 1, 1, 10, 0), 21.0)],
        "ambient_temperature",
    )
    # This configured sensor exists but has no reading in the requested range.
    add_temperature_sensor(
        db_session,
        "30000_TL55",
        [(datetime(2025, 1, 2, 10, 0), 50.0)],
        "wall_temperature",
    )
    db_session.commit()

    response = client.get(
        "/api/v1/dashboard/indoor-conditions",
        params={
            "start": "2025-01-01T00:00:00",
            "end": "2025-01-01T23:59:59",
            "interval": "hour",
        },
    )

    assert response.status_code == 200
    point = response.json()["points"][0]
    assert point["averageTemperatureC"] == 21.0
    assert point["contributingSensorCount"] == 1


def test_indoor_conditions_rejects_invalid_date_range(
    client: TestClient,
    db_session: Session,
):
    add_temperature_sensor(
        db_session,
        "20003_TL2",
        [(datetime(2025, 1, 1, 10, 0), 21.0)],
        "ambient_temperature",
    )
    db_session.commit()

    response = client.get(
        "/api/v1/dashboard/indoor-conditions",
        params={
            "start": "2025-01-02T00:00:00",
            "end": "2025-01-01T00:00:00",
        },
    )

    assert response.status_code == 400
