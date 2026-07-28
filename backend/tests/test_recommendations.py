from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app import recommendation_service
from backend.app.models import SensorPoint, SensorReading
from backend.app.weather_service import WeatherProviderError


def add_sensor(
    db: Session,
    *,
    code: str,
    name: str,
    readings: list[tuple[datetime, float]],
) -> None:
    sensor = SensorPoint(
        sensor_code=code,
        trend_column=f"SaitSolarLab_{code}",
        display_name=name,
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
        SensorReading(
            sensor_point_id=sensor.sensor_point_id,
            reading_time=timestamp,
            value=value,
        )
        for timestamp, value in readings
    )


def warm_weather_payload() -> dict:
    return {
        "location": "Calgary, Alberta",
        "source": "Open-Meteo",
        "providerRetrievedAt": "2026-07-28T09:00",
        "servedAt": "2026-07-28T09:00:01+00:00",
        "isStale": False,
        "daily": [
            {
                "date": "2026-07-28",
                "maximumTemperatureC": 27.0,
                "minimumTemperatureC": 14.0,
                "condition": "Partly cloudy",
            }
        ],
    }


def seed_triggering_evidence(db: Session) -> None:
    latest = datetime(2025, 12, 31, 23, 59)

    add_sensor(
        db,
        code="30000_TL209",
        name="GBT Lighting consumption",
        readings=[(latest, 300.0)],
    )
    add_sensor(
        db,
        code="30000_TL208",
        name="GBT Space heating/cooling consumption",
        readings=[(latest, 2000.0)],
    )
    add_sensor(
        db,
        code="30000_TL342",
        name="GBT Site Consumption",
        readings=[(latest, -8000.0)],
    )

    dhw_readings = [
        (latest - timedelta(minutes=index + 1), 50.0)
        for index in range(30)
    ]
    dhw_readings.append((latest, 200.0))
    add_sensor(
        db,
        code="30000_TL210",
        name="GBT Domestic Hot Water consumption",
        readings=dhw_readings,
    )
    db.commit()


def test_recommendation_endpoint_returns_three_explainable_rules(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    seed_triggering_evidence(db_session)
    monkeypatch.setattr(
        recommendation_service,
        "get_weather_forecast",
        warm_weather_payload,
    )

    response = client.get("/api/v1/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluatedRuleCount"] == 3
    assert payload["recommendationCount"] == 3
    assert payload["externalDataStatus"] == "available"

    recommendations = {
        item["recommendationId"]: item
        for item in payload["recommendations"]
    }
    assert set(recommendations) == {
        "after-hours-lighting",
        "dhw-above-baseline",
        "weather-aware-hvac-plan",
    }

    lighting = recommendations["after-hours-lighting"]
    assert lighting["ruleId"] == "R1_AFTER_HOURS_LIGHTING"
    assert any(
        item.get("sensorCode") == "30000_TL209"
        for item in lighting["evidence"]
    )

    dhw = recommendations["dhw-above-baseline"]
    ratio = next(
        item
        for item in dhw["evidence"]
        if item["label"] == "Latest-to-baseline ratio"
    )
    assert ratio["value"] == 4.0

    hvac = recommendations["weather-aware-hvac-plan"]
    assert any(
        item["sourceType"] == "external"
        and item["value"] == 27.0
        for item in hvac["evidence"]
    )
    assert any(
        "historical" in limitation.lower()
        for limitation in hvac["limitations"]
    )


def test_weather_failure_skips_only_weather_rule(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    seed_triggering_evidence(db_session)

    def fail_weather():
        raise WeatherProviderError("Provider unavailable")

    monkeypatch.setattr(
        recommendation_service,
        "get_weather_forecast",
        fail_weather,
    )

    response = client.get("/api/v1/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendationCount"] == 2
    assert payload["externalDataStatus"] == "unavailable"
    assert payload["warnings"]
    assert {
        item["recommendationId"]
        for item in payload["recommendations"]
    } == {
        "after-hours-lighting",
        "dhw-above-baseline",
    }
