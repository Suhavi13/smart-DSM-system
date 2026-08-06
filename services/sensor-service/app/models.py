"""Sensor-service-owned SQLAlchemy tables."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


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
