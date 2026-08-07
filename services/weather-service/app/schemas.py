"""Pydantic contracts owned by the weather service."""

from typing import Optional

from pydantic import BaseModel


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
