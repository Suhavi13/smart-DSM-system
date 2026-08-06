"""Pydantic contracts owned by the sensor service."""

from datetime import datetime
from typing import Optional, Literal

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


class SensorAverageRequest(BaseModel):
    sensorCodes: list[str] = Field(min_length=1, max_length=123)
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class SensorAverageItemResponse(BaseModel):
    sensorPointId: int
    sensorCode: str
    displayName: str
    category: Optional[str] = None
    displayUnit: Optional[str] = None
    location: Optional[str] = None
    readingCount: int
    averageValue: Optional[float] = None
    minimumValue: Optional[float] = None
    maximumValue: Optional[float] = None
    firstTimestamp: Optional[datetime] = None
    lastTimestamp: Optional[datetime] = None


class SensorAveragesResponse(BaseModel):
    datasetType: str = "historical"
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    requestedSensorCount: int
    returnedSensorCount: int
    missingSensorCodes: list[str] = Field(default_factory=list)
    sensors: list[SensorAverageItemResponse]


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


class IndoorConditionsPointResponse(BaseModel):
    timestamp: datetime
    averageTemperatureC: float
    minimumTemperatureC: float
    maximumTemperatureC: float
    contributingSensorCount: int


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
    points: list[IndoorConditionsPointResponse]


class EnergyConsumptionPointResponse(BaseModel):
    timestamp: datetime
    energyWh: float
    energyKwh: float
    averageWatts: Optional[float] = None
    durationHours: float
    previousCumulativeWh: float
    currentCumulativeWh: float
    count: int = 1


class EnergyConsumptionResponse(BaseModel):
    datasetType: str = "historical"
    interval: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    pointCount: int
    sensor: ReadingSensorResponse
    sourceUnit: str
    energyUnit: str = "Wh"
    demandUnit: str = "W"
    counterDirection: Literal["increasing", "decreasing"]
    skippedCounterChanges: int = 0
    points: list[EnergyConsumptionPointResponse]
