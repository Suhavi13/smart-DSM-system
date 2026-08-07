"""Shared sensor scaling and time-bucket aggregation helpers."""

from collections import defaultdict
from datetime import datetime
from typing import Literal

from .models import SensorPoint, SensorReading

ReadingInterval = Literal["raw", "15min", "hour", "day"]
CounterDirection = Literal["auto", "increasing", "decreasing"]


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


def aggregate_temperature_sensor_group(
    sensors: list[SensorPoint],
    readings: list[SensorReading],
    interval: ReadingInterval,
    limit: int,
) -> list[dict]:
    """Average a sensor group with equal weight for every available sensor.

    Each sensor is averaged inside the requested time bucket first. The bucket
    values are then averaged across sensors. This prevents a sensor that reports
    more frequently from having more influence on the building-wide result.
    Missing readings are ignored rather than treated as zero.
    """
    sensors_by_id = {
        sensor.sensor_point_id: sensor
        for sensor in sensors
    }
    sensor_bucket_values: dict[tuple[int, datetime], list[float]] = (
        defaultdict(list)
    )

    for reading in readings:
        if reading.value is None:
            continue

        sensor = sensors_by_id.get(reading.sensor_point_id)
        if sensor is None:
            continue

        scaled_value = scale_value(sensor, reading.value)
        if scaled_value is None:
            continue

        bucket = bucket_timestamp(reading.reading_time, interval)
        sensor_bucket_values[(sensor.sensor_point_id, bucket)].append(
            scaled_value
        )

    values_by_timestamp: dict[datetime, list[float]] = defaultdict(list)

    for (_, timestamp), values in sensor_bucket_values.items():
        if values:
            values_by_timestamp[timestamp].append(
                sum(values) / len(values)
            )

    points = []

    for timestamp in sorted(values_by_timestamp):
        sensor_values = values_by_timestamp[timestamp]
        points.append(
            {
                "timestamp": timestamp,
                "averageTemperatureC": (
                    sum(sensor_values) / len(sensor_values)
                ),
                "minimumTemperatureC": min(sensor_values),
                "maximumTemperatureC": max(sensor_values),
                "contributingSensorCount": len(sensor_values),
            }
        )

    return points[-limit:]


def energy_value_to_wh(
    sensor: SensorPoint,
    raw_value: float | None,
) -> float | None:
    """Convert a cumulative energy reading to Watt-hours.

    Dashboard demand calculations must start from an energy counter, not from
    an instantaneous power point. The project currently uses a Wh counter, but
    this conversion also supports a future kWh counter without changing the
    calculation code.
    """
    if raw_value is None:
        return None

    raw_unit = (sensor.raw_unit or "").strip().lower()
    display_unit = (sensor.display_unit or "").strip().lower()

    if raw_unit == "wh":
        return raw_value
    if raw_unit == "kwh":
        return raw_value * 1000.0

    scaled_value = scale_value(sensor, raw_value)
    if scaled_value is None:
        return None
    if display_unit == "wh":
        return scaled_value
    if display_unit == "kwh":
        return scaled_value * 1000.0

    raise ValueError(
        f"Sensor {sensor.sensor_code} must use Wh or kWh for cumulative "
        "energy calculations."
    )


def _resolve_counter_direction(
    values_wh: list[float],
    requested_direction: CounterDirection,
) -> Literal["increasing", "decreasing"]:
    if requested_direction in {"increasing", "decreasing"}:
        return requested_direction

    for first_value, last_value in zip(values_wh, reversed(values_wh)):
        if last_value > first_value:
            return "increasing"
        if last_value < first_value:
            return "decreasing"

    return "increasing"


def derive_energy_usage_points(
    sensor: SensorPoint,
    readings: list[SensorReading],
    interval: ReadingInterval,
    limit: int,
    counter_direction: CounterDirection = "auto",
) -> tuple[list[dict], Literal["increasing", "decreasing"], int]:
    """Derive interval energy and average demand from cumulative readings.

    For each pair of readings:
      energy Wh = direction-adjusted change in cumulative Wh
      average W = energy Wh / elapsed hours

    Counter reversals are skipped because they usually indicate a reset,
    rollover, or source-data correction. Silently taking abs(delta) would turn
    those events into false consumption spikes.
    """
    ordered_readings = sorted(readings, key=lambda item: item.reading_time)
    normalized_readings: list[tuple[datetime, float]] = []

    for reading in ordered_readings:
        value_wh = energy_value_to_wh(sensor, reading.value)
        if value_wh is not None:
            normalized_readings.append((reading.reading_time, value_wh))

    if len(normalized_readings) < 2:
        resolved_direction = _resolve_counter_direction(
            [value for _, value in normalized_readings],
            counter_direction,
        )
        return [], resolved_direction, 0

    resolved_direction = _resolve_counter_direction(
        [value for _, value in normalized_readings],
        counter_direction,
    )
    direction_multiplier = 1.0 if resolved_direction == "increasing" else -1.0
    segments: list[dict] = []
    skipped_counter_changes = 0

    previous_timestamp, previous_value_wh = normalized_readings[0]

    for current_timestamp, current_value_wh in normalized_readings[1:]:
        elapsed_hours = (
            current_timestamp - previous_timestamp
        ).total_seconds() / 3600.0

        if elapsed_hours <= 0:
            previous_timestamp = current_timestamp
            previous_value_wh = current_value_wh
            continue

        energy_wh = (
            current_value_wh - previous_value_wh
        ) * direction_multiplier

        if energy_wh < -1e-9:
            skipped_counter_changes += 1
            previous_timestamp = current_timestamp
            previous_value_wh = current_value_wh
            continue

        energy_wh = max(0.0, energy_wh)
        segments.append(
            {
                "timestamp": current_timestamp,
                "energyWh": energy_wh,
                "energyKwh": energy_wh / 1000.0,
                "averageWatts": energy_wh / elapsed_hours,
                "durationHours": elapsed_hours,
                "previousCumulativeWh": previous_value_wh,
                "currentCumulativeWh": current_value_wh,
                "count": 1,
            }
        )
        previous_timestamp = current_timestamp
        previous_value_wh = current_value_wh

    if interval == "raw":
        return segments[-limit:], resolved_direction, skipped_counter_changes

    bucketed: dict[datetime, dict] = {}

    for segment in segments:
        timestamp = bucket_timestamp(segment["timestamp"], interval)
        bucket = bucketed.setdefault(
            timestamp,
            {
                "timestamp": timestamp,
                "energyWh": 0.0,
                "durationHours": 0.0,
                "previousCumulativeWh": segment["previousCumulativeWh"],
                "currentCumulativeWh": segment["currentCumulativeWh"],
                "count": 0,
            },
        )
        bucket["energyWh"] += segment["energyWh"]
        bucket["durationHours"] += segment["durationHours"]
        bucket["currentCumulativeWh"] = segment["currentCumulativeWh"]
        bucket["count"] += 1

    points = []
    for timestamp in sorted(bucketed):
        bucket = bucketed[timestamp]
        energy_wh = bucket["energyWh"]
        duration_hours = bucket["durationHours"]
        points.append(
            {
                **bucket,
                "energyKwh": energy_wh / 1000.0,
                "averageWatts": (
                    energy_wh / duration_hours
                    if duration_hours > 0
                    else None
                ),
            }
        )

    return points[-limit:], resolved_direction, skipped_counter_changes
