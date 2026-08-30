from typing import Literal

from pydantic import BaseModel, Field


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


class CanonicalSeries(BaseModel):
    """Shared canonical contract for versioned dashboard time series."""

    schemaVersion: str = "1.0"
    seriesId: str
    label: str
    status: DataStatus
    latestValue: float | None = None
    unit: str
    currency: str | None = None
    frequency: str
    timezone: str = "UTC"
    source: str
    upstreamSource: str | None = None
    sourceSeriesId: str | None = None
    sourceUrl: str | None = None
    observationDate: str | None = None
    asOf: str | None = None
    retrievedAt: str | None = None
    isStale: bool = False
    methodologyVersion: str
    qualityFlags: list[str] = Field(default_factory=list)
    rightsScope: str | None = None
    observations: list[Observation] = Field(default_factory=list)


class MacroSeries(CanonicalSeries):
    """Backward-compatible alias for existing macro consumers."""
