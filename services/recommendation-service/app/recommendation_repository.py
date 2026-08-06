"""Persistence helpers for generated recommendations and their workflow status."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .models import Recommendation, RecommendationDecision, SensorPoint


FINAL_STATUSES = {"approved", "rejected"}


def _as_utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sensor_codes(snapshot: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    for evidence in snapshot.get("evidence") or []:
        if not isinstance(evidence, dict):
            continue
        for code in evidence.get("sourceCodes") or []:
            normalized = str(code).strip()
            if normalized and normalized not in codes:
                codes.append(normalized)
    return codes


def _first_current_value(snapshot: dict[str, Any]) -> float | None:
    direct_value = _as_optional_float(snapshot.get("currentValue"))
    if direct_value is not None:
        return direct_value

    for evidence in snapshot.get("evidence") or []:
        if not isinstance(evidence, dict):
            continue
        value = _as_optional_float(evidence.get("value"))
        if value is not None:
            return value
    return None


def _recommendation_text(snapshot: dict[str, Any]) -> str:
    title = str(snapshot.get("title") or "Untitled recommendation").strip()
    description = str(snapshot.get("description") or "").strip()
    return f"{title}\n\n{description}".strip()


def _target_sensor_id(
    db: Session,
    snapshot: dict[str, Any],
) -> int | None:
    codes = _sensor_codes(snapshot)
    if not codes:
        return None

    sensor = (
        db.query(SensorPoint)
        .filter(SensorPoint.sensor_code.in_(codes))
        .order_by(SensorPoint.sensor_point_id.asc())
        .first()
    )
    return sensor.sensor_point_id if sensor else None


def _decision_status(
    db: Session,
    recommendation_key: str,
    recommendation_version: int,
) -> str | None:
    try:
        decision = (
            db.query(RecommendationDecision)
            .filter(
                RecommendationDecision.recommendation_id == recommendation_key,
                RecommendationDecision.recommendation_version
                == recommendation_version,
                RecommendationDecision.is_active.is_(True),
            )
            .first()
        )
        return decision.action if decision else None
    except SQLAlchemyError:
        # decision-service owns this table and may not have started yet.
        db.rollback()
        return None


def upsert_recommendation(
    db: Session,
    snapshot: dict[str, Any],
    *,
    generated_at: datetime | str | None = None,
    recommendation_key: str | None = None,
    recommendation_version: int | None = None,
    commit: bool = False,
) -> Recommendation:
    """Insert or refresh one generated recommendation without duplicating it."""
    key = str(
        recommendation_key
        or snapshot.get("recommendationId")
        or ""
    ).strip()
    if not key:
        raise ValueError("A recommendationId is required for persistence.")

    version = int(
        recommendation_version
        or snapshot.get("recommendationVersion")
        or 1
    )
    if version < 1:
        raise ValueError("recommendationVersion must be at least 1.")

    record = (
        db.query(Recommendation)
        .filter(
            Recommendation.recommendation_key == key,
            Recommendation.recommendation_version == version,
        )
        .first()
    )

    # The active decision is the source of truth. If no active decision
    # remains, the recommendation is pending even when an older audit row exists.
    decision_status = _decision_status(db, key, version)
    status = decision_status or "pending"

    values = {
        "recommendation_key": key,
        "recommendation_version": version,
        "recommendation_time": _as_utc_datetime(generated_at),
        "recommendation_text": _recommendation_text(snapshot),
        "reason": str(snapshot.get("reason") or "").strip() or None,
        "status": status,
        "target_sensor_point_id": _target_sensor_id(db, snapshot),
        "current_value": _first_current_value(snapshot),
        "recommended_value": _as_optional_float(
            snapshot.get("recommendedValue")
        ),
        "expected_savings_kwh": _as_optional_float(
            snapshot.get("expectedSavingsKwh")
        ),
        "category": str(snapshot.get("category") or "").strip() or None,
        "priority": str(snapshot.get("priority") or "").strip() or None,
        # Recommendation evidence can contain Python datetime objects.
        # Convert the snapshot to JSON-safe strings before PostgreSQL JSON/JSONB serialization.
        "recommendation_snapshot": jsonable_encoder(snapshot),
    }

    if record is None:
        record = Recommendation(**values)
        db.add(record)
    else:
        for field, value in values.items():
            setattr(record, field, value)

    db.flush()
    if commit:
        db.commit()
        db.refresh(record)
    return record


def persist_generated_recommendations(
    db: Session,
    service_result: dict[str, Any],
) -> list[Recommendation]:
    """Persist every recommendation returned by the recommendation service."""
    generated_at = service_result.get("generatedAt")
    records: list[Recommendation] = []

    try:
        for snapshot in service_result.get("recommendations") or []:
            if not isinstance(snapshot, dict):
                continue
            records.append(
                upsert_recommendation(
                    db,
                    snapshot,
                    generated_at=generated_at,
                )
            )
        db.commit()
        for record in records:
            db.refresh(record)
        return records
    except Exception:
        db.rollback()
        raise


def set_recommendation_status(
    recommendation: Recommendation,
    action: str,
) -> None:
    if action not in FINAL_STATUSES:
        raise ValueError("Recommendation status must be approved or rejected.")
    recommendation.status = action


def set_recommendation_pending(
    recommendation: Recommendation,
) -> None:
    recommendation.status = "pending"
