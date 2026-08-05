"""FastAPI application, dashboard endpoints, CORS, and static frontend hosting."""

from contextlib import asynccontextmanager
from datetime import datetime
import os
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from .auth import CurrentUser, viewer_or_operator
from .cache_service import cache
from .dashboard_sensors import (
    ENERGY_CONSUMPTION_SENSOR_CODE,
    INDOOR_AMBIENT_TEMPERATURE_SENSOR_CODES,
    INDOOR_TEMPERATURE_SENSOR_CODES,
    INDOOR_WALL_TEMPERATURE_SENSOR_CODES,
)
from .database import Base, engine, get_db
from .models import SensorPoint, SensorReading
from .schemas import (
    DashboardOverviewResponse,
    EnergyConsumptionResponse,
    IndoorConditionsResponse,
    SensorReadingsResponse,
    SensorSummaryResponse,
    WeatherForecastResponse,
)
from .services import (
    aggregate_temperature_sensor_group,
    derive_energy_usage_points,
    scale_value,
    serialize_readings,
)
from .weather_service import (
    WeatherProviderError,
    get_weather_forecast,
)

from .routers.decisions import router as decisions_router
from .routers.recommendations import router as recommendations_router
from backend.app.routers import auth



ReadingInterval = Literal["raw", "15min", "hour", "day"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # create_all only creates missing sensor and decision tables.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="GBTAC Sensor Data Service",
    version="0.6.0",
    lifespan=lifespan,
    description=(
        "Read-only API for the full historical GBTAC sensor inventory, "
        "Redis-cached dashboard aggregation, and normalized external "
        "weather data."
    ),
)

app.include_router(decisions_router)
app.include_router(recommendations_router)
app.include_router(auth.router)

frontend_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5500,http://localhost:5501,http://localhost:5173,http://127.0.0.1:5500,http://127.0.0.1:5501,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Content-Type",
        "Authorization",
        "Idempotency-Key",
    ],
    expose_headers=["X-Cache"],
)

DASHBOARD_OVERVIEW_CACHE_SECONDS = max(
    10, int(os.getenv("DASHBOARD_OVERVIEW_CACHE_SECONDS", "60"))
)
DASHBOARD_CHART_CACHE_SECONDS = max(
    30, int(os.getenv("DASHBOARD_CHART_CACHE_SECONDS", "300"))
)
ENERGY_CONSUMPTION_COUNTER_CODE = os.getenv(
    "ENERGY_CONSUMPTION_SENSOR_CODE",
    ENERGY_CONSUMPTION_SENSOR_CODE,
).strip()
ENERGY_COUNTER_DIRECTION = os.getenv(
    "ENERGY_COUNTER_DIRECTION", "decreasing"
).strip().lower()

if ENERGY_COUNTER_DIRECTION not in {"auto", "increasing", "decreasing"}:
    ENERGY_COUNTER_DIRECTION = "decreasing"



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
    redis_available = cache.ping()
    return {
        "status": "ok",
        "service": "GBTAC Sensor Data and Integration Service",
        "version": "0.6.0",
        "datasetType": "historical",
        "externalApi": "Open-Meteo",
        "cache": {
            "enabled": cache.enabled,
            "provider": "Redis",
            "status": (
                "connected"
                if redis_available
                else "unavailable"
                if cache.enabled
                else "disabled"
            ),
        },
    }


@app.get(
    "/api/v1/external/weather/forecast",
    response_model=WeatherForecastResponse,
)
def get_weather_dashboard_forecast(
    response: Response,
    user: CurrentUser = Depends(viewer_or_operator),
):
    try:
        payload = get_weather_forecast()
        response.headers["X-Cache"] = payload["cacheStatus"].upper()
        return payload
    except WeatherProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


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
    user: CurrentUser = Depends(viewer_or_operator),
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
def get_sensor(
    sensor_code: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(viewer_or_operator),
):
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
    user: CurrentUser = Depends(viewer_or_operator),
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
    "/api/v1/dashboard/energy-consumption",
    response_model=EnergyConsumptionResponse,
)
@app.get(
    "/api/v1/dashboard/site-consumption",
    response_model=EnergyConsumptionResponse,
    include_in_schema=False,
)
def get_dashboard_energy_consumption(
    response: Response,
    start: datetime | None = Query(
        default=None,
        description="Inclusive start timestamp in ISO-8601 format.",
    ),
    end: datetime | None = Query(
        default=None,
        description="Inclusive end timestamp in ISO-8601 format.",
    ),
    interval: ReadingInterval = Query(
        default="day",
        description=(
            "Group derived consumption into raw, 15-minute, hourly, or "
            "daily periods."
        ),
    ),
    limit: int = Query(default=500, ge=1, le=10_000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(viewer_or_operator),
):
    """Derive Wh/kWh usage and average W from a cumulative energy counter."""
    if start and end and start > end:
        raise HTTPException(
            status_code=400,
            detail="The start timestamp must be before the end timestamp.",
        )

    cache_key = cache.parameter_key(
        "dashboard:energy-consumption",
        sensor_code=ENERGY_CONSUMPTION_COUNTER_CODE,
        counter_direction=ENERGY_COUNTER_DIRECTION,
        start=start,
        end=end,
        interval=interval,
        limit=limit,
    )
    cached_payload = cache.get_json(cache_key, namespaced=False)
    if isinstance(cached_payload, dict):
        response.headers["X-Cache"] = "HIT"
        return cached_payload

    sensor = (
        db.query(SensorPoint)
        .filter(
            SensorPoint.sensor_code == ENERGY_CONSUMPTION_COUNTER_CODE
        )
        .first()
    )

    if sensor is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Configured cumulative energy sensor "
                f"{ENERGY_CONSUMPTION_COUNTER_CODE} was not found."
            ),
        )

    query = db.query(SensorReading).filter(
        SensorReading.sensor_point_id == sensor.sensor_point_id
    )

    if start:
        query = query.filter(SensorReading.reading_time >= start)

    if end:
        query = query.filter(SensorReading.reading_time <= end)

    readings = query.order_by(SensorReading.reading_time.asc()).all()

    # Include the immediately preceding reading so the first period inside a
    # requested date range can still be calculated as a delta.
    if start:
        previous_reading = (
            db.query(SensorReading)
            .filter(
                SensorReading.sensor_point_id == sensor.sensor_point_id,
                SensorReading.reading_time < start,
            )
            .order_by(SensorReading.reading_time.desc())
            .first()
        )
        if previous_reading is not None:
            readings.insert(0, previous_reading)

    try:
        points, counter_direction, skipped_counter_changes = (
            derive_energy_usage_points(
                sensor=sensor,
                readings=readings,
                interval=interval,
                limit=limit,
                counter_direction=ENERGY_COUNTER_DIRECTION,
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    payload = {
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
        "sourceUnit": sensor.raw_unit or sensor.display_unit or "Wh",
        "energyUnit": "Wh",
        "demandUnit": "W",
        "counterDirection": counter_direction,
        "skippedCounterChanges": skipped_counter_changes,
        "points": points,
    }
    cached = cache.set_json(
        cache_key,
        payload,
        DASHBOARD_CHART_CACHE_SECONDS,
        namespaced=False,
    )
    response.headers["X-Cache"] = "MISS" if cached else "BYPASS"
    return payload


@app.get(
    "/api/v1/dashboard/indoor-conditions",
    response_model=IndoorConditionsResponse,
)
def get_indoor_conditions(
    response: Response,
    start: datetime | None = Query(
        default=None,
        description="Inclusive start timestamp in ISO-8601 format.",
    ),
    end: datetime | None = Query(
        default=None,
        description="Inclusive end timestamp in ISO-8601 format.",
    ),
    interval: ReadingInterval = Query(
        default="hour",
        description="Return raw, 15-minute, hourly, or daily points.",
    ),
    limit: int = Query(default=500, ge=1, le=10_000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(viewer_or_operator),
):
    """Return an equal-weight average of 31 confirmed temperature sensors."""
    cache_key = cache.parameter_key(
        "dashboard:indoor-conditions",
        start=start,
        end=end,
        interval=interval,
        limit=limit,
    )
    cached_payload = cache.get_json(cache_key, namespaced=False)
    if isinstance(cached_payload, dict):
        response.headers["X-Cache"] = "HIT"
        return cached_payload

    if start and end and start > end:
        raise HTTPException(
            status_code=400,
            detail="The start timestamp must be before the end timestamp.",
        )

    temperature_sensors = (
        db.query(SensorPoint)
        .filter(
            SensorPoint.sensor_code.in_(INDOOR_TEMPERATURE_SENSOR_CODES)
        )
        .all()
    )

    if not temperature_sensors:
        raise HTTPException(
            status_code=404,
            detail="No configured indoor temperature sensors were found.",
        )

    found_codes = {sensor.sensor_code for sensor in temperature_sensors}
    missing_codes = [
        sensor_code
        for sensor_code in INDOOR_TEMPERATURE_SENSOR_CODES
        if sensor_code not in found_codes
    ]
    temperature_sensor_ids = [
        sensor.sensor_point_id for sensor in temperature_sensors
    ]

    temperature_query = db.query(SensorReading).filter(
        SensorReading.sensor_point_id.in_(temperature_sensor_ids)
    )

    if start:
        temperature_query = temperature_query.filter(
            SensorReading.reading_time >= start
        )

    if end:
        temperature_query = temperature_query.filter(
            SensorReading.reading_time <= end
        )

    temperature_readings = temperature_query.order_by(
        SensorReading.reading_time.asc()
    ).all()
    temperature_points = aggregate_temperature_sensor_group(
        sensors=temperature_sensors,
        readings=temperature_readings,
        interval=interval,
        limit=limit,
    )

    payload = {
        "datasetType": "historical",
        "interval": interval,
        "start": start,
        "end": end,
        "pointCount": len(temperature_points),
        "configuredTemperatureSensorCount": len(
            INDOOR_TEMPERATURE_SENSOR_CODES
        ),
        "availableTemperatureSensorCount": len(temperature_sensors),
        "ambientTemperatureSensorCount": len(
            INDOOR_AMBIENT_TEMPERATURE_SENSOR_CODES
        ),
        "wallTemperatureSensorCount": len(
            INDOOR_WALL_TEMPERATURE_SENSOR_CODES
        ),
        "missingTemperatureSensorCodes": missing_codes,
        "temperatureUnit": "°C",
        "points": temperature_points,
    }
    cached = cache.set_json(
        cache_key,
        payload,
        DASHBOARD_CHART_CACHE_SECONDS,
        namespaced=False,
    )
    response.headers["X-Cache"] = "MISS" if cached else "BYPASS"
    return payload


@app.get(
    "/api/v1/dashboard/overview",
    response_model=DashboardOverviewResponse,
)
def get_dashboard_overview(
    response: Response,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(viewer_or_operator),
):
    cache_key = "dashboard:overview"
    cached_payload = cache.get_json(cache_key)
    if isinstance(cached_payload, dict):
        response.headers["X-Cache"] = "HIT"
        return cached_payload
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

    payload = {
        "datasetType": "historical",
        "cards": cards,
        "latestDatasetTimestamp": latest_dataset_timestamp,
    }
    cached = cache.set_json(
        cache_key,
        payload,
        DASHBOARD_OVERVIEW_CACHE_SECONDS,
    )
    response.headers["X-Cache"] = "MISS" if cached else "BYPASS"
    return payload

# For the quickest and most reliable deployment, serve the static frontend
# from the same origin as the API. Set SERVE_FRONTEND=false only when using a
# separate frontend host and configure FRONTEND_ORIGINS.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
SERVE_FRONTEND = os.getenv("SERVE_FRONTEND", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
if SERVE_FRONTEND and FRONTEND_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIR, html=True),
        name="frontend",
    )
