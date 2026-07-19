from collections import defaultdict
from datetime import datetime
from typing import Literal

from .models import SensorPoint, SensorReading

ReadingInterval = Literal["raw", "15min", "hour", "day"]


def scale_value(sensor: SensorPoint, raw_value: float | None) -> float | None:
    """Convert a source reading into the unit shown by the dashboard."""
    if raw_value is None:
        return None
    return raw_value * (sensor.scale_factor or 1.0)


def bucket_timestamp(timestamp: datetime, interval: ReadingInterval) -> datetime:
    """Return the beginning of the requested aggregation interval."""
    if interval == "15min":
        minute = (timestamp.minute // 15) * 15
        return timestamp.replace(minute=minute, second=0, microsecond=0)

    if interval == "hour":
        return timestamp.replace(minute=0, second=0, microsecond=0)

    if interval == "day":
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

    return timestamp


def serialize_readings(
    sensor: SensorPoint,
    readings: list[SensorReading],
    interval: ReadingInterval,
    limit: int,
) -> list[dict]:
    """Convert database readings into raw or aggregated API points."""
    if interval == "raw":
        return [
            {
                "timestamp": reading.reading_time,
                "rawValue": reading.value,
                "value": scale_value(sensor, reading.value),
                "minimumValue": None,
                "maximumValue": None,
                "count": 1,
            }
            for reading in readings[-limit:]
        ]

    buckets: dict[datetime, list[float]] = defaultdict(list)

    for reading in readings:
        if reading.value is None:
            continue
        buckets[bucket_timestamp(reading.reading_time, interval)].append(
            reading.value
        )

    points = []

    for timestamp in sorted(buckets):
        raw_values = buckets[timestamp]
        raw_average = sum(raw_values) / len(raw_values)
        raw_minimum = min(raw_values)
        raw_maximum = max(raw_values)

        points.append(
            {
                "timestamp": timestamp,
                "rawValue": raw_average,
                "value": scale_value(sensor, raw_average),
                "minimumValue": scale_value(sensor, raw_minimum),
                "maximumValue": scale_value(sensor, raw_maximum),
                "count": len(raw_values),
            }
        )

    return points[-limit:]
