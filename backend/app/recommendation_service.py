"""Transparent rule-based recommendations for Phase 5.

The service deliberately uses a small set of operator-readable rules rather
than a black-box model. Every returned recommendation includes the sensor,
external, and derived values that caused the rule to trigger.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from .models import SensorPoint, SensorReading
from .services import scale_value
from .weather_service import WeatherProviderError, get_weather_forecast


SITE_CONSUMPTION_SENSOR_CODE = os.getenv(
    "SITE_CONSUMPTION_SENSOR_CODE", "30000_TL342"
).strip()
HVAC_CONSUMPTION_SENSOR_CODE = os.getenv(
    "HVAC_CONSUMPTION_SENSOR_CODE", "30000_TL208"
).strip()
LIGHTING_CONSUMPTION_SENSOR_CODE = os.getenv(
    "LIGHTING_CONSUMPTION_SENSOR_CODE", "30000_TL209"
).strip()
DHW_CONSUMPTION_SENSOR_CODE = os.getenv(
    "DHW_CONSUMPTION_SENSOR_CODE", "30000_TL210"
).strip()

OCCUPIED_START_HOUR = int(os.getenv("OCCUPIED_START_HOUR", "7"))
OCCUPIED_END_HOUR = int(os.getenv("OCCUPIED_END_HOUR", "19"))
LIGHTING_AFTER_HOURS_THRESHOLD_KW = float(
    os.getenv("LIGHTING_AFTER_HOURS_THRESHOLD_KW", "0.25")
)
DHW_BASELINE_SAMPLE_COUNT = int(
    os.getenv("DHW_BASELINE_SAMPLE_COUNT", "10000")
)
DHW_SPIKE_RATIO = float(os.getenv("DHW_SPIKE_RATIO", "3.0"))
DHW_MINIMUM_TRIGGER_KW = float(
    os.getenv("DHW_MINIMUM_TRIGGER_KW", "0.15")
)
WARM_WEATHER_THRESHOLD_C = float(
    os.getenv("WARM_WEATHER_THRESHOLD_C", "20.0")
)
HVAC_MINIMUM_TRIGGER_KW = float(
    os.getenv("HVAC_MINIMUM_TRIGGER_KW", "0.5")
)
HVAC_SITE_SHARE_THRESHOLD = float(
    os.getenv("HVAC_SITE_SHARE_THRESHOLD", "0.15")
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sensor_version(timestamp: datetime) -> int:
    """Create a repeatable integer version for one hour of sensor evidence."""
    aware = timestamp
    if aware.tzinfo is None:
        aware = aware.replace(tzinfo=timezone.utc)
    return int(aware.timestamp() // 3600)


def _daily_version(timestamp: datetime) -> int:
    return int(timestamp.strftime("%Y%m%d"))


def _round(value: float | None, places: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), places)


def _format_schedule() -> str:
    return f"{OCCUPIED_START_HOUR:02d}:00-{OCCUPIED_END_HOUR:02d}:00"


def _load_sensor(db: Session, sensor_code: str) -> SensorPoint | None:
    return (
        db.query(SensorPoint)
        .filter(SensorPoint.sensor_code == sensor_code)
        .first()
    )


def _latest_reading(
    db: Session,
    sensor: SensorPoint | None,
) -> SensorReading | None:
    if sensor is None:
        return None
    return (
        db.query(SensorReading)
        .filter(SensorReading.sensor_point_id == sensor.sensor_point_id)
        .order_by(SensorReading.reading_time.desc())
        .first()
    )


def _recent_scaled_values(
    db: Session,
    sensor: SensorPoint | None,
    limit: int,
) -> list[float]:
    if sensor is None:
        return []

    rows = (
        db.query(SensorReading)
        .filter(
            SensorReading.sensor_point_id == sensor.sensor_point_id,
            SensorReading.value.is_not(None),
        )
        .order_by(SensorReading.reading_time.desc())
        .limit(limit)
        .all()
    )

    values = []
    for row in rows:
        value = scale_value(sensor, row.value)
        if value is not None:
            values.append(float(value))
    return values


def _sensor_evidence(
    *,
    label: str,
    sensor: SensorPoint,
    reading: SensorReading,
    interpreted_value: float | None = None,
    interpreted_unit: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    scaled = scale_value(sensor, reading.value)
    return {
        "sourceType": "sensor",
        "label": label,
        "sensorCode": sensor.sensor_code,
        "displayName": sensor.display_name,
        "value": _round(
            interpreted_value if interpreted_value is not None else scaled
        ),
        "unit": interpreted_unit or sensor.display_unit or sensor.raw_unit,
        "rawValue": _round(reading.value),
        "rawUnit": sensor.raw_unit,
        "timestamp": reading.reading_time,
        "source": "GBTAC historical sensor dataset",
        "note": note,
    }


def _derived_evidence(
    *,
    label: str,
    value: float | str,
    unit: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "sourceType": "derived",
        "label": label,
        "value": _round(value) if isinstance(value, float) else value,
        "unit": unit,
        "source": "Recommendation rule calculation",
        "note": note,
    }


def _external_evidence(
    *,
    label: str,
    value: float | str | None,
    unit: str | None,
    timestamp: str | None,
    source: str,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "sourceType": "external",
        "label": label,
        "value": _round(value) if isinstance(value, float) else value,
        "unit": unit,
        "timestamp": timestamp,
        "source": source,
        "note": note,
    }


def _after_hours_lighting_rule(
    db: Session,
) -> dict[str, Any] | None:
    sensor = _load_sensor(db, LIGHTING_CONSUMPTION_SENSOR_CODE)
    reading = _latest_reading(db, sensor)
    if sensor is None or reading is None:
        return None

    lighting_kw = scale_value(sensor, reading.value)
    if lighting_kw is None:
        return None

    hour = reading.reading_time.hour
    outside_occupied_hours = not (
        OCCUPIED_START_HOUR <= hour < OCCUPIED_END_HOUR
    )
    if not (
        outside_occupied_hours
        and lighting_kw >= LIGHTING_AFTER_HOURS_THRESHOLD_KW
    ):
        return None

    return {
        "recommendationId": "after-hours-lighting",
        "recommendationVersion": _sensor_version(reading.reading_time),
        "ruleId": "R1_AFTER_HOURS_LIGHTING",
        "category": "Lighting",
        "priority": "Medium",
        "title": "Review lighting outside occupied hours",
        "description": (
            "The latest imported lighting reading is above the configured "
            "after-hours threshold. Check schedules, overrides, and zones that "
            "may have been left on."
        ),
        "recommendedAction": (
            "Confirm whether the building was occupied at this timestamp. If "
            "not, reduce the lighting schedule or investigate manual overrides."
        ),
        "reason": (
            f"Lighting was {_round(lighting_kw)} kW at "
            f"{reading.reading_time.isoformat()}, outside the configured "
            f"occupied schedule of {_format_schedule()}."
        ),
        "status": "pending",
        "evidence": [
            _sensor_evidence(
                label="Lighting demand",
                sensor=sensor,
                reading=reading,
            ),
            _derived_evidence(
                label="Configured occupied schedule",
                value=_format_schedule(),
                note=(
                    "The rule triggers before the start hour or at/after the "
                    "end hour."
                ),
            ),
            _derived_evidence(
                label="After-hours trigger threshold",
                value=LIGHTING_AFTER_HOURS_THRESHOLD_KW,
                unit="kW",
            ),
        ],
        "limitations": [
            "The historical dataset does not confirm actual occupancy.",
            "An operator should verify special events and approved overrides.",
        ],
    }


def _dhw_baseline_rule(db: Session) -> dict[str, Any] | None:
    sensor = _load_sensor(db, DHW_CONSUMPTION_SENSOR_CODE)
    reading = _latest_reading(db, sensor)
    if sensor is None or reading is None:
        return None

    current_kw = scale_value(sensor, reading.value)
    recent_values = _recent_scaled_values(
        db,
        sensor,
        DHW_BASELINE_SAMPLE_COUNT,
    )
    if current_kw is None or len(recent_values) < 20:
        return None

    baseline_kw = median(recent_values)
    if baseline_kw <= 0:
        return None

    ratio = current_kw / baseline_kw
    if not (
        current_kw >= DHW_MINIMUM_TRIGGER_KW
        and ratio >= DHW_SPIKE_RATIO
    ):
        return None

    return {
        "recommendationId": "dhw-above-baseline",
        "recommendationVersion": _sensor_version(reading.reading_time),
        "ruleId": "R2_DHW_ABOVE_BASELINE",
        "category": "Domestic hot water",
        "priority": "High",
        "title": "Investigate domestic-hot-water demand",
        "description": (
            "The latest domestic-hot-water load is several times higher than "
            "its recent median. Review the heating schedule, recirculation, "
            "and possible continuous hot-water demand."
        ),
        "recommendedAction": (
            "Compare the timestamp with expected hot-water use. Check the DHW "
            "schedule and recirculation settings before changing equipment."
        ),
        "reason": (
            f"The latest value was {_round(current_kw)} kW, which is "
            f"{_round(ratio)} times the recent median of "
            f"{_round(baseline_kw)} kW."
        ),
        "status": "pending",
        "evidence": [
            _sensor_evidence(
                label="Latest DHW demand",
                sensor=sensor,
                reading=reading,
            ),
            _derived_evidence(
                label="Recent median baseline",
                value=float(baseline_kw),
                unit=sensor.display_unit or "kW",
                note=(
                    f"Median of the latest {len(recent_values)} available "
                    "readings."
                ),
            ),
            _derived_evidence(
                label="Latest-to-baseline ratio",
                value=float(ratio),
                unit="x",
            ),
            _derived_evidence(
                label="Rule ratio threshold",
                value=DHW_SPIKE_RATIO,
                unit="x",
            ),
        ],
        "limitations": [
            "A high value may be expected during scheduled recovery or heavy use.",
            "The rule detects an anomaly but does not diagnose its cause.",
        ],
    }


def _weather_aware_hvac_rule(
    db: Session,
    weather: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not weather:
        return None

    daily = weather.get("daily") or []
    if not daily:
        return None

    forecast_day = daily[0]
    maximum_temperature = forecast_day.get("maximumTemperatureC")
    if maximum_temperature is None:
        return None

    hvac_sensor = _load_sensor(db, HVAC_CONSUMPTION_SENSOR_CODE)
    site_sensor = _load_sensor(db, SITE_CONSUMPTION_SENSOR_CODE)
    hvac_reading = _latest_reading(db, hvac_sensor)
    site_reading = _latest_reading(db, site_sensor)

    if (
        hvac_sensor is None
        or site_sensor is None
        or hvac_reading is None
        or site_reading is None
    ):
        return None

    hvac_kw = scale_value(hvac_sensor, hvac_reading.value)
    signed_site_kw = scale_value(site_sensor, site_reading.value)
    if hvac_kw is None or signed_site_kw is None:
        return None

    site_magnitude_kw = abs(signed_site_kw)
    if site_magnitude_kw <= 0:
        return None

    hvac_share = hvac_kw / site_magnitude_kw
    if not (
        maximum_temperature >= WARM_WEATHER_THRESHOLD_C
        and hvac_kw >= HVAC_MINIMUM_TRIGGER_KW
        and hvac_share >= HVAC_SITE_SHARE_THRESHOLD
    ):
        return None

    generated_at = _utc_now()
    return {
        "recommendationId": "weather-aware-hvac-plan",
        "recommendationVersion": _daily_version(generated_at),
        "ruleId": "R3_WEATHER_AWARE_HVAC",
        "category": "HVAC",
        "priority": "Medium",
        "title": "Prepare a warm-weather HVAC operating plan",
        "description": (
            "The live forecast is warm and the latest historical snapshot shows "
            "a meaningful HVAC share of site demand. Review pre-cooling, "
            "setpoints, and peak-period scheduling with the operator."
        ),
        "recommendedAction": (
            "Before the warmest period, verify occupied-zone setpoints and "
            "consider shifting safe cooling activity away from the expected "
            "peak. Do not write changes to the BMS without operator approval."
        ),
        "reason": (
            f"The forecast maximum is {_round(float(maximum_temperature))} °C. "
            f"HVAC demand is {_round(hvac_kw)} kW, or "
            f"{_round(hvac_share * 100)}% of the interpreted site-load magnitude."
        ),
        "status": "pending",
        "evidence": [
            _sensor_evidence(
                label="HVAC demand",
                sensor=hvac_sensor,
                reading=hvac_reading,
            ),
            _sensor_evidence(
                label="Signed site-consumption reading",
                sensor=site_sensor,
                reading=site_reading,
                note=(
                    "The original sign is preserved. Only the magnitude is used "
                    "for the share calculation because the source sign "
                    "convention still requires client confirmation."
                ),
            ),
            _derived_evidence(
                label="Interpreted site-load magnitude",
                value=float(site_magnitude_kw),
                unit=site_sensor.display_unit or "kW",
            ),
            _derived_evidence(
                label="HVAC share of site-load magnitude",
                value=float(hvac_share * 100),
                unit="%",
            ),
            _external_evidence(
                label="Forecast maximum outdoor temperature",
                value=float(maximum_temperature),
                unit="°C",
                timestamp=forecast_day.get("date"),
                source=weather.get("source", "External weather provider"),
                note=weather.get("location"),
            ),
        ],
        "limitations": [
            "The sensor snapshot is historical while the weather forecast is live.",
            "This is a planning prompt, not proof that current HVAC operation is inefficient.",
        ],
    }


def generate_recommendations(db: Session) -> dict[str, Any]:
    """Evaluate all Phase 5 rules and return only triggered recommendations."""
    generated_at = _utc_now()
    warnings: list[str] = []

    try:
        weather = get_weather_forecast()
        external_data_status = (
            "stale" if weather.get("isStale") else "available"
        )
    except WeatherProviderError:
        weather = None
        external_data_status = "unavailable"
        warnings.append(
            "The weather provider was unavailable, so the weather-aware HVAC "
            "rule was skipped."
        )

    rules = [
        _after_hours_lighting_rule(db),
        _dhw_baseline_rule(db),
        _weather_aware_hvac_rule(db, weather),
    ]
    recommendations = [rule for rule in rules if rule is not None]

    source_timestamps = [
        evidence.get("timestamp")
        for recommendation in recommendations
        for evidence in recommendation["evidence"]
        if evidence.get("sourceType") == "sensor"
        and isinstance(evidence.get("timestamp"), datetime)
    ]

    return {
        "generatedAt": generated_at,
        "datasetType": "historical",
        "datasetLatestTimestamp": max(source_timestamps)
        if source_timestamps
        else None,
        "externalDataStatus": external_data_status,
        "evaluatedRuleCount": 3,
        "recommendationCount": len(recommendations),
        "warnings": warnings,
        "recommendations": recommendations,
    }
