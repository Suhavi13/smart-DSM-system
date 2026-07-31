"""Redis JSON cache behavior tests."""

from datetime import datetime

import fakeredis

from backend.app.cache_service import RedisJsonCache


def test_redis_json_cache_round_trip(monkeypatch):
    monkeypatch.setenv("CACHE_ENABLED", "true")
    client = fakeredis.FakeRedis(decode_responses=True)
    cache = RedisJsonCache(client=client)

    assert cache.set_json(
        "dashboard:test",
        {"value": 21.5, "timestamp": datetime(2025, 1, 1, 12, 0)},
        60,
    )
    result = cache.get_json("dashboard:test")

    assert result["value"] == 21.5
    assert result["timestamp"] == "2025-01-01T12:00:00"
    assert cache.ttl("dashboard:test") > 0


def test_parameter_cache_key_is_stable(monkeypatch):
    monkeypatch.setenv("CACHE_ENABLED", "true")
    cache = RedisJsonCache(
        client=fakeredis.FakeRedis(decode_responses=True)
    )

    first = cache.parameter_key(
        "dashboard:chart",
        interval="hour",
        limit=500,
    )
    second = cache.parameter_key(
        "dashboard:chart",
        limit=500,
        interval="hour",
    )

    assert first == second
    assert first.startswith("gbtac:v1:dashboard:chart:")
