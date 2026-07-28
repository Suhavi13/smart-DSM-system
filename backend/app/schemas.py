from datetime import datetime
from typing import Optional, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SensorBase(BaseModel):
    sensor_code: str
    trend_column: str
    display_name: str
    measurement_property: Optional[int] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    why_selected: Optional[str] = None
    dashboard_feature: Optional[str] = None
    raw_unit: Optional[str] = None
    display_unit: Optional[str] = None
    scale_factor: float = 1.0
    sign_convention: Optional[str] = None
    data_type: Optional[str] = None
    location: Optional[str] = None


class SensorResponse(SensorBase):
    model_config = ConfigDict(from_attributes=True)

    sensor_point_id: int


class SensorSummaryResponse(BaseModel):
    sensorPointId: int
    sensorCode: str
    trendColumn: str
    displayName: str
    measurementProperty: Optional[int] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    whySelected: Optional[str] = None
    dashboardFeature: Optional[str] = None
    rawUnit: Optional[str] = None
    displayUnit: Optional[str] = None
    scaleFactor: float = 1.0
    signConvention: Optional[str] = None
    dataType: Optional[str] = None
    location: Optional[str] = None
    hasReadings: bool = False
    latestValue: Optional[float] = None
    latestRawValue: Optional[float] = None
    latestTimestamp: Optional[datetime] = None


class ReadingPointResponse(BaseModel):
    timestamp: datetime
    value: Optional[float] = None
    rawValue: Optional[float] = None
    minimumValue: Optional[float] = None
    maximumValue: Optional[float] = None
    count: int = 1


class ReadingSensorResponse(BaseModel):
    sensorCode: str
    displayName: str
    category: Optional[str] = None
    priority: Optional[str] = None
    rawUnit: Optional[str] = None
    displayUnit: Optional[str] = None
    scaleFactor: float = 1.0
    signConvention: Optional[str] = None
    dataType: Optional[str] = None
    location: Optional[str] = None


class SensorReadingsResponse(BaseModel):
    datasetType: str = "historical"
    interval: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    pointCount: int
    sensor: ReadingSensorResponse
    points: list[ReadingPointResponse]


class DashboardCardResponse(BaseModel):
    sensorCode: str
    displayName: str
    category: Optional[str] = None
    priority: Optional[str] = None
    latestValue: Optional[float] = None
    latestRawValue: Optional[float] = None
    latestTimestamp: Optional[datetime] = None
    displayUnit: Optional[str] = None


class DashboardOverviewResponse(BaseModel):
    datasetType: str = "historical"
    cards: list[DashboardCardResponse]
    latestDatasetTimestamp: Optional[datetime] = None


class WeatherCurrentResponse(BaseModel):
    temperatureC: Optional[float] = None
    humidityPercent: Optional[float] = None
    weatherCode: Optional[int] = None
    condition: str


class WeatherDayResponse(BaseModel):
    date: str
    maximumTemperatureC: Optional[float] = None
    minimumTemperatureC: Optional[float] = None
    precipitationProbabilityPercent: Optional[float] = None
    weatherCode: Optional[int] = None
    condition: str


class WeatherUnitsResponse(BaseModel):
    temperature: str = "°C"
    humidity: str = "%"
    precipitationProbability: str = "%"


class WeatherForecastResponse(BaseModel):
    location: str
    latitude: float
    longitude: float
    timezone: str
    source: str
    sourceUrl: str
    providerRetrievedAt: Optional[str] = None
    retrievedAt: Optional[str] = None
    servedAt: str
    cacheStatus: str
    cacheTtlSeconds: Optional[int] = None
    isStale: bool = False
    units: WeatherUnitsResponse
    current: WeatherCurrentResponse
    daily: list[WeatherDayResponse]


class IndoorConditionsPointResponse(BaseModel):
    timestamp: datetime
    averageTemperatureC: float
    minimumTemperatureC: float
    maximumTemperatureC: float
    contributingSensorCount: int
    co2Ppm: Optional[float] = None


class IndoorConditionsResponse(BaseModel):
    datasetType: str = "historical"
    interval: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    pointCount: int
    configuredTemperatureSensorCount: int
    availableTemperatureSensorCount: int
    ambientTemperatureSensorCount: int
    wallTemperatureSensorCount: int
    missingTemperatureSensorCodes: list[str]
    temperatureUnit: str = "°C"
    co2SensorCode: str
    co2Unit: str = "ppm"
    points: list[IndoorConditionsPointResponse]

class DecisionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recommendation_id: str = Field(
        alias="recommendationId",
        min_length=1,
        max_length=100,
    )

    recommendation_version: int = Field(
        default=1,
        alias="recommendationVersion",
        ge=1,
    )

    action: Literal["approved", "rejected"]

    comment: str | None = Field(
        default=None,
        max_length=1000,
    )

    recommendation_snapshot: dict[str, Any] = Field(
        alias="recommendationSnapshot",
    )


class DecisionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    decision_id: int = Field(alias="decisionId")

    recommendation_id: str = Field(
        alias="recommendationId"
    )

    recommendation_version: int = Field(
        alias="recommendationVersion"
    )

    action: str
    comment: str | None

    operator_label: str = Field(
        alias="operatorLabel"
    )

    recommendation_snapshot: dict[str, Any] = Field(
        alias="recommendationSnapshot"
    )

    created_at: datetime = Field(
        alias="createdAt"
    )
