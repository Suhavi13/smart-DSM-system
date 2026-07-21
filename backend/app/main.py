from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from .database import get_db
from .models import SensorPoint, SensorReading
from .schemas import (
    DashboardOverviewResponse,
    SensorReadingsResponse,
    SensorSummaryResponse,
)
from .services import scale_value, serialize_readings

ReadingInterval = Literal["raw", "15min", "hour", "day"]

app = FastAPI(
    title="GBTAC Sensor Data Service",
    version="0.2.1",
    description=(
        "Read-only API for the full historical GBTAC sensor inventory, "
        "latest values, date-filtered readings, and chart aggregation."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8081",
        "http://localhost:8081",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def serialize_sensor(
    sensor: SensorPoint,
    latest_reading: SensorReading | None = None,
) -> dict:
    return {
        "sensorPointId": sensor.sensor_point_id,
        "sensorCode": sensor.sensor_code,
        "trendColumn": sensor.trend_column,
        "displayName": sensor.display_name,
        "measurementProperty": sensor.measurement_property,
        "category": sensor.category,
        "priority": sensor.priority,
        "whySelected": sensor.why_selected,
        "dashboardFeature": sensor.dashboard_feature,
        "rawUnit": sensor.raw_unit,
        "displayUnit": sensor.display_unit,
        "scaleFactor": sensor.scale_factor or 1.0,
        "signConvention": sensor.sign_convention,
        "dataType": sensor.data_type,
        "location": sensor.location,
        "hasReadings": latest_reading is not None,
        "latestValue": (
            scale_value(sensor, latest_reading.value)
            if latest_reading
            else None
        ),
        "latestRawValue": latest_reading.value if latest_reading else None,
        "latestTimestamp": (
            latest_reading.reading_time if latest_reading else None
        ),
    }


def inventory_sensor_latest_rows(db: Session):
    """Fetch all imported inventory sensors and their latest readings."""
    latest_times = (
        db.query(
            SensorReading.sensor_point_id.label("sensor_point_id"),
            func.max(SensorReading.reading_time).label("latest_time"),
        )
        .group_by(SensorReading.sensor_point_id)
        .subquery()
    )

    return (
        db.query(SensorPoint, SensorReading)
        .outerjoin(
            latest_times,
            SensorPoint.sensor_point_id == latest_times.c.sensor_point_id,
        )
        .outerjoin(
            SensorReading,
            and_(
                SensorReading.sensor_point_id
                == latest_times.c.sensor_point_id,
                SensorReading.reading_time == latest_times.c.latest_time,
            ),
        )
        .filter(SensorPoint.is_selected.is_(True))
        .order_by(
            SensorPoint.priority,
            SensorPoint.category,
            SensorPoint.display_name,
        )
        .all()
    )


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "GBTAC Sensor Data Service",
        "version": "0.2.1",
        "datasetType": "historical",
    }


@app.get(
    "/api/v1/sensors",
    response_model=list[SensorSummaryResponse],
)
def get_sensors(
    includeLatest: bool = Query(
        default=False,
        description="Include each sensor's latest imported reading.",
    ),
    db: Session = Depends(get_db),
):
    if includeLatest:
        rows = inventory_sensor_latest_rows(db)
        return [
            serialize_sensor(sensor, latest_reading)
            for sensor, latest_reading in rows
        ]

    sensors = (
        db.query(SensorPoint)
        .filter(SensorPoint.is_selected.is_(True))
        .order_by(
            SensorPoint.priority,
            SensorPoint.category,
            SensorPoint.display_name,
        )
        .all()
    )
    return [serialize_sensor(sensor) for sensor in sensors]


@app.get(
    "/api/v1/sensors/{sensor_code}",
    response_model=SensorSummaryResponse,
)
def get_sensor(sensor_code: str, db: Session = Depends(get_db)):
    sensor = (
        db.query(SensorPoint)
        .filter(SensorPoint.sensor_code == sensor_code)
        .first()
    )

    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found.")

    latest_reading = (
        db.query(SensorReading)
        .filter(SensorReading.sensor_point_id == sensor.sensor_point_id)
        .order_by(SensorReading.reading_time.desc())
        .first()
    )

    return serialize_sensor(sensor, latest_reading)


@app.get(
    "/api/v1/sensors/{sensor_code}/readings",
    response_model=SensorReadingsResponse,
)
@app.get(
    "/api/v1/readings/{sensor_code}",
    response_model=SensorReadingsResponse,
    include_in_schema=False,
)
def get_sensor_readings(
    sensor_code: str,
    start: datetime | None = Query(
        default=None,
        description="Inclusive start timestamp in ISO-8601 format.",
    ),
    end: datetime | None = Query(
        default=None,
        description="Inclusive end timestamp in ISO-8601 format.",
    ),
    interval: ReadingInterval = Query(
        default="raw",
        description="Return raw, 15-minute, hourly, or daily points.",
    ),
    limit: int = Query(default=500, ge=1, le=10_000),
    db: Session = Depends(get_db),
):
    if start and end and start > end:
        raise HTTPException(
            status_code=400,
            detail="The start timestamp must be before the end timestamp.",
        )

    sensor = (
        db.query(SensorPoint)
        .filter(SensorPoint.sensor_code == sensor_code)
        .first()
    )

    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found.")

    query = db.query(SensorReading).filter(
        SensorReading.sensor_point_id == sensor.sensor_point_id
    )

    if start:
        query = query.filter(SensorReading.reading_time >= start)

    if end:
        query = query.filter(SensorReading.reading_time <= end)

    if interval == "raw":
        readings = (
            query.order_by(SensorReading.reading_time.desc())
            .limit(limit)
            .all()
        )
        readings.reverse()
    else:
        # Phase 1 imports at most 10,000 readings per sensor, so filtered
        # aggregation remains bounded while avoiding database-specific SQL.
        readings = query.order_by(SensorReading.reading_time.asc()).all()

    points = serialize_readings(sensor, readings, interval, limit)

    return {
        "datasetType": "historical",
        "interval": interval,
        "start": start,
        "end": end,
        "pointCount": len(points),
        "sensor": {
            "sensorCode": sensor.sensor_code,
            "displayName": sensor.display_name,
            "category": sensor.category,
            "priority": sensor.priority,
            "rawUnit": sensor.raw_unit,
            "displayUnit": sensor.display_unit,
            "scaleFactor": sensor.scale_factor or 1.0,
            "signConvention": sensor.sign_convention,
            "dataType": sensor.data_type,
            "location": sensor.location,
        },
        "points": points,
    }


@app.get(
    "/api/v1/dashboard/overview",
    response_model=DashboardOverviewResponse,
)
def get_dashboard_overview(db: Session = Depends(get_db)):
    core_sensor_codes = {
        "30000_TL342",
        "30000_TL335",
        "30000_TL3",
        "30000_TL252",
        "30000_TL253",
        "30000_TL208",
        "30000_TL4",
        "30000_TL209",
        "30000_TL210",
        "30000_TL211",
        "30000_TL212",
        "20000_TL92",
    }

    rows = inventory_sensor_latest_rows(db)
    cards = []
    latest_dataset_timestamp = None

    for sensor, latest_reading in rows:
        if sensor.sensor_code not in core_sensor_codes:
            continue

        if latest_reading and (
            latest_dataset_timestamp is None
            or latest_reading.reading_time > latest_dataset_timestamp
        ):
            latest_dataset_timestamp = latest_reading.reading_time

        cards.append(
            {
                "sensorCode": sensor.sensor_code,
                "displayName": sensor.display_name,
                "category": sensor.category,
                "priority": sensor.priority,
                "latestValue": (
                    scale_value(sensor, latest_reading.value)
                    if latest_reading
                    else None
                ),
                "latestRawValue": (
                    latest_reading.value if latest_reading else None
                ),
                "latestTimestamp": (
                    latest_reading.reading_time if latest_reading else None
                ),
                "displayUnit": sensor.display_unit,
            }
        )

    return {
        "datasetType": "historical",
        "cards": cards,
        "latestDatasetTimestamp": latest_dataset_timestamp,
    }
