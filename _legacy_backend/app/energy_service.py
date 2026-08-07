"""Energy analytics for the historical GBTAC dataset.

The project contains two distinct measurement types:

* Direct power sensors whose source values are already watts (W).
* A cumulative totalized meter whose source values are kilowatt-hours (kWh).

Do not calculate a reading-to-reading delta for a direct W sensor. Deltas are
only used for the cumulative kWh meter when calculating energy used during a
period.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
import os

from sqlalchemy.orm import Session

from .models import SensorPoint, SensorReading


CUMULATIVE_ENERGY_SENSOR_CODE = os.getenv(
    "CUMULATIVE_ENERGY_SENSOR_CODE", "30000_TL388"
).strip()


def _load_sensor(db: Session, sensor_code: str) -> SensorPoint | None:
    return (
        db.query(SensorPoint)
        .filter(SensorPoint.sensor_code == sensor_code)
        .first()
    )


def _beginning_of_day(value: datetime) -> datetime:
    return datetime.combine(value.date(), time.min)


def build_daily_energy_usage(
    db: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    days: int = 7,
) -> dict:
    """Calculate daily energy from a cumulative kWh meter.

    Positive reading-to-reading changes are summed into the day containing the
    newer reading. Negative changes are treated as meter resets/data anomalies
    and are excluded instead of turning daily usage negative.
    """
    sensor = _load_sensor(db, CUMULATIVE_ENERGY_SENSOR_CODE)
    if sensor is None:
        raise LookupError(
            f"Cumulative energy sensor {CUMULATIVE_ENERGY_SENSOR_CODE} was not found."
        )

    latest = (
        db.query(SensorReading)
        .filter(
            SensorReading.sensor_point_id == sensor.sensor_point_id,
            SensorReading.value.is_not(None),
        )
        .order_by(SensorReading.reading_time.desc())
        .first()
    )
    if latest is None:
        raise LookupError(
            f"Cumulative energy sensor {CUMULATIVE_ENERGY_SENSOR_CODE} has no readings."
        )

    effective_end = end or latest.reading_time
    effective_start = start or (
        _beginning_of_day(effective_end) - timedelta(days=max(days - 1, 0))
    )

    if effective_start > effective_end:
        raise ValueError("The start timestamp must be before the end timestamp.")

    # Include the last value before the requested range so the first in-range
    # reading can produce a valid delta.
    previous = (
        db.query(SensorReading)
        .filter(
            SensorReading.sensor_point_id == sensor.sensor_point_id,
            SensorReading.value.is_not(None),
            SensorReading.reading_time < effective_start,
        )
        .order_by(SensorReading.reading_time.desc())
        .first()
    )

    readings = (
        db.query(SensorReading)
        .filter(
            SensorReading.sensor_point_id == sensor.sensor_point_id,
            SensorReading.value.is_not(None),
            SensorReading.reading_time >= effective_start,
            SensorReading.reading_time <= effective_end,
        )
        .order_by(SensorReading.reading_time.asc())
        .all()
    )

    sequence = ([previous] if previous is not None else []) + readings
    daily_kwh: dict[date, float] = defaultdict(float)
    reading_counts: dict[date, int] = defaultdict(int)
    negative_delta_counts: dict[date, int] = defaultdict(int)
    first_times: dict[date, datetime] = {}
    last_times: dict[date, datetime] = {}

    for reading in readings:
        reading_day = reading.reading_time.date()
        reading_counts[reading_day] += 1
        first_times.setdefault(reading_day, reading.reading_time)
        last_times[reading_day] = reading.reading_time

    for older, newer in zip(sequence, sequence[1:]):
        if older is None or newer is None:
            continue
        if older.value is None or newer.value is None:
            continue
        if not (effective_start <= newer.reading_time <= effective_end):
            continue

        delta_kwh = float(newer.value) - float(older.value)
        day_key = newer.reading_time.date()

        if delta_kwh < 0:
            negative_delta_counts[day_key] += 1
            continue

        daily_kwh[day_key] += delta_kwh

    points = []
    current_day = effective_start.date()
    final_day = effective_end.date()

    while current_day <= final_day:
        energy_kwh = daily_kwh.get(current_day, 0.0)
        first_time = first_times.get(current_day)
        last_time = last_times.get(current_day)
        covered_hours = None
        average_power_w = None

        if first_time and last_time and last_time > first_time:
            covered_hours = (
                last_time - first_time
            ).total_seconds() / 3600.0
            if covered_hours > 0:
                average_power_w = energy_kwh * 1000.0 / covered_hours

        points.append(
            {
                "date": current_day.isoformat(),
                "energyKwh": round(energy_kwh, 3),
                "energyWh": round(energy_kwh * 1000.0, 1),
                "averagePowerW": (
                    round(average_power_w, 1)
                    if average_power_w is not None
                    else None
                ),
                "coveredHours": (
                    round(covered_hours, 2)
                    if covered_hours is not None
                    else None
                ),
                "readingCount": reading_counts.get(current_day, 0),
                "ignoredNegativeDeltaCount": negative_delta_counts.get(
                    current_day, 0
                ),
            }
        )
        current_day += timedelta(days=1)

    return {
        "datasetType": "historical",
        "start": effective_start,
        "end": effective_end,
        "sensor": {
            "sensorCode": sensor.sensor_code,
            "displayName": sensor.display_name,
            "rawUnit": sensor.raw_unit or "kWh",
            "dataType": sensor.data_type or "cumulative_energy",
        },
        "calculation": {
            "method": "positive cumulative reading deltas",
            "formula": "daily kWh = sum(max(current kWh - previous kWh, 0))",
            "wattHourFormula": "Wh = kWh × 1,000",
            "averagePowerFormula": "average W = kWh ÷ covered hours × 1,000",
            "negativeDeltaHandling": (
                "Negative deltas are excluded as possible resets or data anomalies."
            ),
        },
        "pointCount": len(points),
        "points": points,
    }
