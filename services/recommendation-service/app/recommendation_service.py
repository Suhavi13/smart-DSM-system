"""Explainable rule-based recommendations for the GBTAC dashboard.

Phase 5 intentionally uses a small number of transparent rules rather than a
black-box model. Every triggered recommendation contains the exact sensor or
external values that caused the rule to fire.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import os
from typing import Any, Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from .dashboard_sensors import INDOOR_AMBIENT_TEMPERATURE_SENSOR_CODES
from .models import SensorPoint, SensorReading
from .services import scale_value
from .weather_service import WeatherProviderError, get_weather_forecast
from .ai_service import generate_recommendation


SITE_POWER_SENSOR_CODE = os.getenv(
    "RECOMMENDATION_SITE_POWER_SENSOR_CODE", "30000_TL342"
).strip()


def _float_setting(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


OVERNIGHT_BASELOAD_THRESHOLD_W = _float_setting(
    "OVERNIGHT_BASELOAD_THRESHOLD_W", 8_000.0
)
PEAK_DEMAND_MINIMUM_W = _float_setting(
    "PEAK_DEMAND_MINIMUM_W", 15_000.0
)
PEAK_DEMAND_RATIO = _float_setting("PEAK_DEMAND_RATIO", 1.5)
ECONOMIZER_MIN_INDOOR_C = _float_setting(
    "ECONOMIZER_MIN_INDOOR_C", 22.0
)
ECONOMIZER_MIN_OUTDOOR_C = _float_setting(
    "ECONOMIZER_MIN_OUTDOOR_C", 5.0
)
ECONOMIZER_TEMPERATURE_DIFFERENCE_C = _float_setting(
    "ECONOMIZER_TEMPERATURE_DIFFERENCE_C", 2.0
)


def _round(value: float, digits: int = 1) -> float:
    return round(float(value), digits)


def _sensor_evidence(
    *,
    label: str,
    sensor: SensorPoint,
    value: float,
    unit: str,
    timestamp: datetime | None,
    comparison: str,
    details: str,
    source_codes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "evidenceType": "sensor",
        "label": label,
        "sourceName": sensor.display_name,
        "sourceCodes": source_codes or [sensor.sensor_code],
        "value": value,
        "unit": unit,
        "timestamp": timestamp,
        "comparison": comparison,
        "details": details,
    }


def _external_evidence(
    *,
    label: str,
    source_name: str,
    value: float,
    unit: str,
    timestamp: str | None,
    comparison: str,
    details: str,
) -> dict[str, Any]:
    return {
        "evidenceType": "external",
        "label": label,
        "sourceName": source_name,
        "sourceCodes": [],
        "value": value,
        "unit": unit,
        "timestamp": timestamp,
        "comparison": comparison,
        "details": details,
    }


def _load_site_power(db: Session) -> tuple[SensorPoint | None, list[SensorReading]]:
    sensor = (
        db.query(SensorPoint)
        .filter(SensorPoint.sensor_code == SITE_POWER_SENSOR_CODE)
        .first()
    )
    if sensor is None:
        return None, []

    readings = (
        db.query(SensorReading)
        .filter(SensorReading.sensor_point_id == sensor.sensor_point_id)
        .order_by(SensorReading.reading_time.asc())
        .all()
    )
    return sensor, readings


def _power_magnitude_w(sensor: SensorPoint, reading: SensorReading) -> float | None:
    value = scale_value(sensor, reading.value)
    if value is None:
        return None

    # This confirmed GBTAC point reports consumption as negative W. Convert
    # only negative consumption values into a positive magnitude; a positive
    # value is not silently reclassified as consumption.
    return max(0.0, -float(value))


def _evaluate_overnight_baseload(
    sensor: SensorPoint | None,
    readings: list[SensorReading],
) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    rule_id = "overnight-baseload"
    rule_name = "Overnight base-load threshold"

    if sensor is None or not readings:
        summary = f"Skipped because {SITE_POWER_SENSOR_CODE} has no readings."
        return None, {
            "ruleId": rule_id,
            "ruleName": rule_name,
            "triggered": False,
            "summary": summary,
        }, summary

    latest_timestamp = readings[-1].reading_time
    evaluation_day = latest_timestamp.date()
    if latest_timestamp.hour < 6:
        evaluation_day = (latest_timestamp - timedelta(days=1)).date()

    overnight_values: list[tuple[datetime, float]] = []
    for reading in readings:
        if reading.reading_time.date() != evaluation_day:
            continue
        if not 0 <= reading.reading_time.hour < 6:
            continue
        magnitude = _power_magnitude_w(sensor, reading)
        if magnitude is not None:
            overnight_values.append((reading.reading_time, magnitude))

    if len(overnight_values) < 3:
        summary = "Skipped because fewer than three overnight readings were available."
        return None, {
            "ruleId": rule_id,
            "ruleName": rule_name,
            "triggered": False,
            "summary": summary,
        }, summary

    average_w = sum(value for _, value in overnight_values) / len(overnight_values)
    triggered = average_w >= OVERNIGHT_BASELOAD_THRESHOLD_W
    summary = (
        f"Overnight average was {_round(average_w):,.1f} W; the rule threshold "
        f"is {_round(OVERNIGHT_BASELOAD_THRESHOLD_W):,.1f} W."
    )

    evaluation = {
        "ruleId": rule_id,
        "ruleName": rule_name,
        "triggered": triggered,
        "summary": summary,
    }
    if not triggered:
        return None, evaluation, None

    recommendation = {
        "recommendationId": "reduce-overnight-baseload",
        "recommendationVersion": int(evaluation_day.strftime("%Y%m%d")),
        "category": "Energy",
        "title": "Reduce overnight base load",
        "description": (
            "Review after-hours HVAC schedules, lighting, plug loads, and "
            "equipment that may be operating unnecessarily between midnight "
            "and 6:00 a.m."
        ),
        "reason": (
            f"Average site demand was {_round(average_w):,.0f} W during the "
            f"latest overnight window, above the configured "
            f"{_round(OVERNIGHT_BASELOAD_THRESHOLD_W):,.0f} W threshold."
        ),
        "priority": (
            "High"
            if average_w >= OVERNIGHT_BASELOAD_THRESHOLD_W * 1.25
            else "Medium"
        ),
        "status": "triggered",
        "rule": {
            "ruleId": rule_id,
            "condition": (
                "Average absolute site power from 00:00 through 05:59 is "
                f">= {OVERNIGHT_BASELOAD_THRESHOLD_W:,.0f} W."
            ),
        },
        "evidence": [
            _sensor_evidence(
                label="Overnight average demand",
                sensor=sensor,
                value=_round(average_w),
                unit="W",
                timestamp=overnight_values[-1][0],
                comparison=(
                    f"Threshold: {OVERNIGHT_BASELOAD_THRESHOLD_W:,.0f} W"
                ),
                details=(
                    f"Calculated from {len(overnight_values)} readings on "
                    f"{evaluation_day.isoformat()}. The source reports "
                    "consumption as negative W, so the rule uses its positive "
                    "magnitude."
                ),
            )
        ],
    }
    return recommendation, evaluation, None


def _evaluate_peak_demand(
    sensor: SensorPoint | None,
    readings: list[SensorReading],
) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    rule_id = "peak-demand-spike"
    rule_name = "Seven-day demand spike"

    if sensor is None or not readings:
        summary = f"Skipped because {SITE_POWER_SENSOR_CODE} has no readings."
        return None, {
            "ruleId": rule_id,
            "ruleName": rule_name,
            "triggered": False,
            "summary": summary,
        }, summary

    latest_timestamp = readings[-1].reading_time
    start_timestamp = latest_timestamp - timedelta(days=7)
    window_values: list[tuple[datetime, float]] = []

    for reading in readings:
        if reading.reading_time < start_timestamp:
            continue
        magnitude = _power_magnitude_w(sensor, reading)
        if magnitude is not None:
            window_values.append((reading.reading_time, magnitude))

    if len(window_values) < 3:
        summary = "Skipped because fewer than three recent power readings were available."
        return None, {
            "ruleId": rule_id,
            "ruleName": rule_name,
            "triggered": False,
            "summary": summary,
        }, summary

    average_w = sum(value for _, value in window_values) / len(window_values)
    peak_timestamp, peak_w = max(window_values, key=lambda item: item[1])
    relative_threshold_w = average_w * PEAK_DEMAND_RATIO
    effective_threshold_w = max(PEAK_DEMAND_MINIMUM_W, relative_threshold_w)
    triggered = peak_w >= effective_threshold_w

    summary = (
        f"Seven-day peak was {_round(peak_w):,.1f} W versus an average of "
        f"{_round(average_w):,.1f} W; trigger level was "
        f"{_round(effective_threshold_w):,.1f} W."
    )
    evaluation = {
        "ruleId": rule_id,
        "ruleName": rule_name,
        "triggered": triggered,
        "summary": summary,
    }
    if not triggered:
        return None, evaluation, None

    recommendation = {
        "recommendationId": "investigate-demand-spike",
        "recommendationVersion": int(latest_timestamp.strftime("%Y%m%d")),
        "category": "Demand",
        "title": "Investigate the recent demand spike",
        "description": (
            "Check which major loads started near the peak timestamp and "
            "consider staggering HVAC, pumps, laboratory equipment, or other "
            "large loads to reduce simultaneous demand."
        ),
        "reason": (
            f"The highest recent site demand was {_round(peak_w):,.0f} W, "
            f"which exceeded the rule trigger of "
            f"{_round(effective_threshold_w):,.0f} W."
        ),
        "priority": "High",
        "status": "triggered",
        "rule": {
            "ruleId": rule_id,
            "condition": (
                "Seven-day peak site power is at least "
                f"{PEAK_DEMAND_RATIO:.1f} times the seven-day average and at "
                f"least {PEAK_DEMAND_MINIMUM_W:,.0f} W."
            ),
        },
        "evidence": [
            _sensor_evidence(
                label="Seven-day peak demand",
                sensor=sensor,
                value=_round(peak_w),
                unit="W",
                timestamp=peak_timestamp,
                comparison=f"Trigger: {effective_threshold_w:,.0f} W",
                details=(
                    "Peak positive consumption magnitude from the confirmed "
                    "site power point."
                ),
            ),
            _sensor_evidence(
                label="Seven-day average demand",
                sensor=sensor,
                value=_round(average_w),
                unit="W",
                timestamp=latest_timestamp,
                comparison=f"Peak/average ratio: {peak_w / average_w:.2f}",
                details=f"Calculated from {len(window_values)} recent readings.",
            ),
        ],
    }
    return recommendation, evaluation, None


def _latest_ambient_snapshot(db: Session) -> dict[str, Any] | None:
    sensors = (
        db.query(SensorPoint)
        .filter(SensorPoint.sensor_code.in_(INDOOR_AMBIENT_TEMPERATURE_SENSOR_CODES))
        .all()
    )
    if not sensors:
        return None

    sensor_by_id = {sensor.sensor_point_id: sensor for sensor in sensors}
    sensor_ids = list(sensor_by_id)
    latest_timestamp = (
        db.query(func.max(SensorReading.reading_time))
        .filter(SensorReading.sensor_point_id.in_(sensor_ids))
        .scalar()
    )
    if latest_timestamp is None:
        return None

    window_start = latest_timestamp - timedelta(hours=1)
    recent_readings = (
        db.query(SensorReading)
        .filter(
            SensorReading.sensor_point_id.in_(sensor_ids),
            SensorReading.reading_time >= window_start,
            SensorReading.reading_time <= latest_timestamp,
        )
        .order_by(SensorReading.reading_time.asc())
        .all()
    )

    latest_by_sensor: dict[int, SensorReading] = {}
    for reading in recent_readings:
        latest_by_sensor[reading.sensor_point_id] = reading

    values: list[float] = []
    source_codes: list[str] = []
    representative_sensor: SensorPoint | None = None
    for sensor_id, reading in latest_by_sensor.items():
        sensor = sensor_by_id[sensor_id]
        value = scale_value(sensor, reading.value)
        if value is None or not 5.0 <= value <= 40.0:
            continue
        values.append(float(value))
        source_codes.append(sensor.sensor_code)
        if representative_sensor is None:
            representative_sensor = sensor

    if not values or representative_sensor is None:
        return None

    return {
        "averageTemperatureC": sum(values) / len(values),
        "timestamp": latest_timestamp,
        "sensorCount": len(values),
        "sourceCodes": sorted(source_codes),
        "representativeSensor": representative_sensor,
    }


def _evaluate_weather_economizer(
    db: Session,
    weather_loader: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any], str | None]:
    rule_id = "weather-economizer"
    rule_name = "Cool-outdoor-air opportunity"
    indoor = _latest_ambient_snapshot(db)

    if indoor is None:
        summary = "Skipped because no recent indoor ambient-temperature snapshot was available."
        return None, {
            "ruleId": rule_id,
            "ruleName": rule_name,
            "triggered": False,
            "summary": summary,
        }, summary

    try:
        weather = weather_loader()
    except WeatherProviderError as error:
        summary = f"Skipped because weather data was unavailable: {error}"
        return None, {
            "ruleId": rule_id,
            "ruleName": rule_name,
            "triggered": False,
            "summary": summary,
        }, summary

    current = weather.get("current") or {}
    outdoor_c = current.get("temperatureC")
    if outdoor_c is None:
        summary = "Skipped because the weather response did not include outdoor temperature."
        return None, {
            "ruleId": rule_id,
            "ruleName": rule_name,
            "triggered": False,
            "summary": summary,
        }, summary

    indoor_c = float(indoor["averageTemperatureC"])
    outdoor_c = float(outdoor_c)
    difference_c = indoor_c - outdoor_c
    triggered = (
        indoor_c >= ECONOMIZER_MIN_INDOOR_C
        and outdoor_c >= ECONOMIZER_MIN_OUTDOOR_C
        and difference_c >= ECONOMIZER_TEMPERATURE_DIFFERENCE_C
    )

    summary = (
        f"Indoor ambient average was {_round(indoor_c):.1f} °C and current "
        f"outdoor temperature was {_round(outdoor_c):.1f} °C, a "
        f"{_round(difference_c):.1f} °C difference."
    )
    evaluation = {
        "ruleId": rule_id,
        "ruleName": rule_name,
        "triggered": triggered,
        "summary": summary,
    }
    if not triggered:
        return None, evaluation, None

    weather_timestamp = (
        weather.get("retrievedAt")
        or weather.get("providerRetrievedAt")
        or weather.get("servedAt")
    )
    representative_sensor: SensorPoint = indoor["representativeSensor"]

    recommendation = {
        "recommendationId": "evaluate-economizer-cooling",
        "recommendationVersion": int(datetime.now(timezone.utc).strftime("%Y%m%d")),
        "category": "HVAC",
        "title": "Evaluate economizer or free cooling",
        "description": (
            "Before mechanical cooling is increased, verify live conditions "
            "and consider using cooler outdoor air where the HVAC system and "
            "ventilation requirements permit it. Operator approval is required."
        ),
        "reason": (
            f"The latest imported indoor ambient average was "
            f"{_round(indoor_c):.1f} °C while Open-Meteo reported "
            f"{_round(outdoor_c):.1f} °C outdoors, a difference of "
            f"{_round(difference_c):.1f} °C."
        ),
        "priority": "Medium",
        "status": "triggered",
        "rule": {
            "ruleId": rule_id,
            "condition": (
                f"Indoor average >= {ECONOMIZER_MIN_INDOOR_C:.1f} °C, outdoor "
                f">= {ECONOMIZER_MIN_OUTDOOR_C:.1f} °C, and outdoor air is at "
                f"least {ECONOMIZER_TEMPERATURE_DIFFERENCE_C:.1f} °C cooler."
            ),
        },
        "evidence": [
            _sensor_evidence(
                label="Indoor ambient average",
                sensor=representative_sensor,
                value=_round(indoor_c),
                unit="°C",
                timestamp=indoor["timestamp"],
                comparison=(
                    f"Minimum indoor trigger: {ECONOMIZER_MIN_INDOOR_C:.1f} °C"
                ),
                details=(
                    f"Average of {indoor['sensorCount']} ambient sensors with "
                    "plausible readings in the latest one-hour sensor window."
                ),
                source_codes=indoor["sourceCodes"],
            ),
            _external_evidence(
                label="Current outdoor temperature",
                source_name=weather.get("source", "Weather provider"),
                value=_round(outdoor_c),
                unit="°C",
                timestamp=weather_timestamp,
                comparison=f"Indoor-outdoor difference: {difference_c:.1f} °C",
                details=(
                    f"External weather value for {weather.get('location', 'the configured location')}."
                ),
            ),
        ],
    }
    return recommendation, evaluation, None


def evaluate_recommendations(
    db: Session,
    weather_loader: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate all Phase 5 rules and return explainable active results."""
    if weather_loader is None:
        weather_loader = get_weather_forecast

    power_sensor, power_readings = _load_site_power(db)
    recommendations: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    skipped_rules: list[dict[str, str]] = []

    rule_results = [
        _evaluate_overnight_baseload(power_sensor, power_readings),
        _evaluate_peak_demand(power_sensor, power_readings),
        _evaluate_weather_economizer(db, weather_loader),
    ]

    for recommendation, evaluation, skipped_reason in rule_results:
        evaluations.append(evaluation)
        if recommendation is not None:
            recommendations.append(recommendation)
        if skipped_reason:
            skipped_rules.append(
                {
                    "ruleId": evaluation["ruleId"],
                    "reason": skipped_reason,
                }
            )
    # ------------------------------------------------
    # Generate AI-powered energy optimization recommendations
    # ------------------------------------------------

    try:
         # Load the latest weather information for the building
        weather = weather_loader()

 # Send weather and predicted power usage to the AI model
    # The AI returns multiple energy-saving recommendations
        ai_recommendations = generate_recommendation(
            weather=weather,
            predicted_power=22000
        )
 # Process each AI-generated recommendation
        for index, ai_text in enumerate(ai_recommendations, start=1):

            # Default title and description
            title = f"AI Recommendation {index}"
            description = ai_text

  # Extract the title and recommendation text if the AI
        # follows the expected output format
            if "Title:" in ai_text:
                content = ai_text.split("Title:", 1)[1].strip()

                if "Recommendation:" in content:
                    title, description = content.split("Recommendation:", 1)
                    title = title.strip()
                    description = "Recommendation:\n" + description.strip()


 # Store the AI recommendation in the response list
            recommendations.append(
                {
                    "recommendationId": f"ai-energy-{index}",
                    "recommendationVersion": 1,
                    "category": "AI",
                    "title": title,
                    "description": description,
                    "reason": "Generated using the Qwen AI model.",
                    "priority": "Medium",
                    "status": "triggered",
                    "rule": {
                        "ruleId": f"ai-model-{index}",
                        "condition": "AI-generated recommendation",
                    },
                    "evidence": [],
                }
            )

    except Exception as e:
          # Log AI errors without stopping the application
        print("AI Error:", e)


    


    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    recommendations.sort(
        key=lambda item: (
            priority_order.get(item["priority"], 9),
            item["title"],
        )
    )

    return {
        "datasetType": "historical-plus-current-external",
        "generatedAt": datetime.now(timezone.utc),
        "rulesEvaluated": len(evaluations),
        "recommendationCount": len(recommendations),
        "dataNotice": (
            "Sensor evidence comes from the latest imported historical data. "
            "Weather evidence is current external data. Recommendations are "
            "decision support only and require operator verification and approval."
        ),
        "recommendations": recommendations,
        "evaluations": evaluations,
        "skippedRules": skipped_rules,
    }