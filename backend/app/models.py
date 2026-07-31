"""SQLAlchemy tables for users, sensors, readings, and recommendation decisions."""

from datetime import datetime
from typing import Optional, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    JSON,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class AppUser(Base):
    __tablename__ = "app_users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('Viewer', 'Operator')",
            name="ck_app_users_role",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Viewer",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SensorPoint(Base):
    __tablename__ = "sensor_points"

    sensor_point_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    sensor_code: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    trend_column: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    measurement_property: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    priority: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )

    why_selected: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    dashboard_feature: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )

    raw_unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    display_unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    scale_factor: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )

    sign_convention: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    data_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    location: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )

    is_selected: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )


class SensorReading(Base):

    __tablename__ = "sensor_readings"

    reading_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    sensor_point_id: Mapped[int] = mapped_column(
        ForeignKey("sensor_points.sensor_point_id"),
        nullable=False,
        index=True,
    )

    reading_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "sensor_point_id",
            "reading_time",
            name="unique_sensor_reading",
        ),
    )

class RecommendationDecision(Base):
    __tablename__ = "recommendation_decisions"

    __table_args__ = (
        CheckConstraint(
            "action IN ('approved', 'rejected')",
            name="ck_recommendation_decisions_action",
        ),
        UniqueConstraint(
            "recommendation_id",
            "recommendation_version",
            name="uq_recommendation_decision_version",
        ),
    )

    decision_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    recommendation_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    recommendation_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    operator_label: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    recommendation_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
