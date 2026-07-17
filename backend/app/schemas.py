from datetime import datetime
from typing import Optional

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


class ReadingPointResponse(BaseModel):
    timestamp: datetime
    value: Optional[float] = None
    rawValue: Optional[float] = None


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
