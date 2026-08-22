from pydantic import BaseModel
from typing import Literal, Any

DataStatus = Literal[
    "ready",
    "partial",
    "degraded",
    "stale",
    "no_data",
    "not_configured",
    "error",
]

class Observation(BaseModel):
    date: str
    value: float | None

class MacroSeries(BaseModel):
    schemaVersion: str = "1.0"
    seriesId: str
    label: str
    status: DataStatus
    source: str
    sourceSeriesId: str | None = None
    sourceUrl: str | None = None
    frequency: str
    unit: str
    timezone: str = "UTC"
    asOf: str | None = None
    retrievedAt: str | None = None
    isStale: bool = False
    methodologyVersion: str
    qualityFlags: list[str] = []
    observations: list[Observation] = []
