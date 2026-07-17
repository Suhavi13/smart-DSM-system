from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import get_db
from .models import SensorPoint, SensorReading
from .schemas import (
    DashboardOverviewResponse,
    SensorReadingsResponse,
    SensorSummaryResponse,
)

app = FastAPI(
    title="Smart Building DSM API",
    version="0.1.0",
    description=(
        "Backend API for historical smart-building sensor analytics and "
        "DSM recommendation development."
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def serialize_sensor(sensor: SensorPoint) -> dict:
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
    }


def scale_value(sensor: SensorPoint, raw_value: float | None) -> float | None:
    if raw_value is None:
        return None
    return raw_value * (sensor.scale_factor or 1.0)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Smart Building DSM API",
        "datasetType": "historical",
    }


@app.get(
    "/api/v1/sensors",
    response_model=list[SensorSummaryResponse],
)
def get_selected_sensors(db: Session = Depends(get_db)):
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

    return serialize_sensor(sensor)


@app.get(
    "/api/v1/readings/{sensor_code}",
    response_model=SensorReadingsResponse,
)
def get_sensor_readings(
    sensor_code: str,
    limit: int = Query(default=500, ge=1, le=10_000),
    db: Session = Depends(get_db),
):
    sensor = (
        db.query(SensorPoint)
        .filter(SensorPoint.sensor_code == sensor_code)
        .first()
    )

    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found.")

    readings = (
        db.query(SensorReading)
        .filter(SensorReading.sensor_point_id == sensor.sensor_point_id)
        .order_by(SensorReading.reading_time.desc())
        .limit(limit)
        .all()
    )
    readings.reverse()

    return {
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
        "points": [
            {
                "timestamp": reading.reading_time,
                "rawValue": reading.value,
                "value": scale_value(sensor, reading.value),
            }
            for reading in readings
        ],
    }


@app.get(
    "/api/v1/dashboard/overview",
    response_model=DashboardOverviewResponse,
)
def get_dashboard_overview(db: Session = Depends(get_db)):
    core_sensor_codes = [
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
    ]

    cards = []
    latest_dataset_timestamp = None

    for sensor_code in core_sensor_codes:
        sensor = (
            db.query(SensorPoint)
            .filter(SensorPoint.sensor_code == sensor_code)
            .first()
        )
        if sensor is None:
            continue

        latest_reading = (
            db.query(SensorReading)
            .filter(SensorReading.sensor_point_id == sensor.sensor_point_id)
            .order_by(SensorReading.reading_time.desc())
            .first()
        )

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
