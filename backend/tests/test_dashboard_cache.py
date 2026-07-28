from datetime import datetime

import fakeredis
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app import main
from backend.app.cache_service import RedisJsonCache
from backend.app.models import SensorPoint, SensorReading


def add_site_consumption_reading(db: Session) -> None:
    sensor = SensorPoint(
        sensor_code="30000_TL342",
        trend_column="30000_TL342",
        display_name="GBT Site Consumption",
        category="Energy",
        raw_unit="W",
        display_unit="kW",
        scale_factor=0.001,
        data_type="power",
        location="GBTAC building",
        is_selected=True,
    )
    db.add(sensor)
    db.flush()
    db.add(
        SensorReading(
            sensor_point_id=sensor.sensor_point_id,
            reading_time=datetime(2025, 1, 1, 10, 0),
            value=12000.0,
        )
    )
    db.commit()


def test_dashboard_overview_uses_redis(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    add_site_consumption_reading(db_session)
    monkeypatch.setenv("CACHE_ENABLED", "true")
    fake_cache = RedisJsonCache(
        client=fakeredis.FakeRedis(decode_responses=True)
    )
    monkeypatch.setattr(main, "cache", fake_cache)

    first = client.get("/api/v1/dashboard/overview")
    second = client.get("/api/v1/dashboard/overview")

    assert first.status_code == 200
    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"
    assert second.json() == first.json()


def test_site_consumption_dashboard_response_uses_redis(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    add_site_consumption_reading(db_session)
    monkeypatch.setenv("CACHE_ENABLED", "true")
    fake_cache = RedisJsonCache(
        client=fakeredis.FakeRedis(decode_responses=True)
    )
    monkeypatch.setattr(main, "cache", fake_cache)

    path = "/api/v1/dashboard/site-consumption?interval=hour&limit=100"
    first = client.get(path)
    second = client.get(path)

    assert first.status_code == 200
    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"
    assert second.json()["pointCount"] == 1
    assert second.json()["points"][0]["value"] == 12.0
