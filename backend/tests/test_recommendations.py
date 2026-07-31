"""Recommendation rule and API tests."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app import recommendation_service
from backend.app.models import SensorPoint, SensorReading
from backend.app.weather_service import WeatherProviderError


def add_sensor(
    db: Session,
    *,
    code: str,
    display_name: str,
    unit: str,
    data_type: str,
) -> SensorPoint:
    sensor = SensorPoint(
        sensor_code=code,
        trend_column=f"SaitSolarLab_{code}",
        display_name=display_name,
        category="Energy" if unit == "W" else "Temperature",
        priority="P1",
        raw_unit=unit,
        display_unit=unit,
        scale_factor=1.0,
        data_type=data_type,
        location="GBTAC building",
        is_selected=True,
    )
    db.add(sensor)
    db.flush()
    return sensor


def seed_recommendation_inputs(db: Session) -> None:
    power_sensor = add_sensor(
        db,
        code="30000_TL342",
        display_name="GBT Site Consumption",
        unit="W",
        data_type="power",
    )

    power_values = [
        (datetime(2025, 12, 31, 0, 0), -9_000.0),
        (datetime(2025, 12, 31, 1, 0), -10_000.0),
        (datetime(2025, 12, 31, 2, 0), -9_000.0),
        (datetime(2025, 12, 31, 3, 0), -10_000.0),
        (datetime(2025, 12, 31, 4, 0), -9_000.0),
        (datetime(2025, 12, 31, 5, 0), -10_000.0),
        (datetime(2025, 12, 31, 12, 0), -5_000.0),
        (datetime(2025, 12, 31, 14, 0), -22_000.0),
        (datetime(2025, 12, 31, 23, 0), -7_000.0),
    ]

    db.add_all(
        [
            SensorReading(
                sensor_point_id=power_sensor.sensor_point_id,
                reading_time=timestamp,
                value=value,
            )
            for timestamp, value in power_values
        ]
    )

    for code, value in [
        ("20003_TL2", 24.0),
        ("20009_TL2", 25.0),
    ]:
        sensor = add_sensor(
            db,
            code=code,
            display_name=f"Ambient temperature {code}",
            unit="°C",
            data_type="temperature",
        )
        db.add(
            SensorReading(
                sensor_point_id=sensor.sensor_point_id,
                reading_time=datetime(2025, 12, 31, 23, 0),
                value=value,
            )
        )

    db.commit()


def weather_payload() -> dict:
    return {
        "location": "Calgary, Alberta",
        "source": "Open-Meteo",
        "retrievedAt": "2026-07-28T04:00:00-06:00",
        "servedAt": "2026-07-28T10:00:00+00:00",
        "current": {
            "temperatureC": 15.0,
            "humidityPercent": 55.0,
            "condition": "Clear sky",
        },
        "daily": [],
    }


def test_api_returns_three_explainable_triggered_recommendations(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    seed_recommendation_inputs(db_session)
    monkeypatch.setattr(
        recommendation_service,
        "get_weather_forecast",
        weather_payload,
    )

    response = client.get("/api/v1/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rulesEvaluated"] == 3
    assert payload["recommendationCount"] == 3

    recommendation_ids = {
        item["recommendationId"]
        for item in payload["recommendations"]
    }
    assert recommendation_ids == {
        "reduce-overnight-baseload",
        "investigate-demand-spike",
        "evaluate-economizer-cooling",
    }

    for recommendation in payload["recommendations"]:
        assert recommendation["reason"]
        assert recommendation["rule"]["condition"]
        assert recommendation["evidence"]
        assert all(
            evidence["sourceName"]
            and evidence["comparison"]
            and evidence["details"]
            for evidence in recommendation["evidence"]
        )

    economizer = next(
        item
        for item in payload["recommendations"]
        if item["recommendationId"] == "evaluate-economizer-cooling"
    )
    evidence_types = {
        item["evidenceType"] for item in economizer["evidence"]
    }
    assert evidence_types == {"sensor", "external"}


def test_weather_failure_skips_only_external_rule(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    seed_recommendation_inputs(db_session)

    def unavailable_weather():
        raise WeatherProviderError("provider unavailable")

    monkeypatch.setattr(
        recommendation_service,
        "get_weather_forecast",
        unavailable_weather,
    )

    response = client.get("/api/v1/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rulesEvaluated"] == 3
    assert payload["recommendationCount"] == 2
    assert any(
        item["ruleId"] == "weather-economizer"
        for item in payload["skippedRules"]
    )


def test_empty_database_returns_rule_evaluations_without_fake_results(
    client: TestClient,
    monkeypatch,
):
    monkeypatch.setattr(
        recommendation_service,
        "get_weather_forecast",
        weather_payload,
    )

    response = client.get("/api/v1/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rulesEvaluated"] == 3
    assert payload["recommendationCount"] == 0
    assert len(payload["evaluations"]) == 3
    assert all(not item["triggered"] for item in payload["evaluations"])
