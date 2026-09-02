"""Publish the frozen EIA weekly petroleum inventory core."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from platform_data.models import CanonicalSeries
from platform_data.providers.eia import fetch_eia_series
from platform_data.quality import validate_observations
from platform_data.runtime import (
    is_observation_stale,
    preserve_volatile_fields_when_materially_unchanged,
)
from platform_data.storage.files import write_json_if_changed


@dataclass(frozen=True)
class EiaInventoryDefinition:
    series_id: str
    canonical_id: str
    label: str


EIA_INVENTORIES = (
    EiaInventoryDefinition(
        "PET.WCESTUS1.W",
        "eia_us_commercial_crude_stocks",
        "U.S. Commercial Crude Stocks",
    ),
    EiaInventoryDefinition(
        "PET.W_EPC0_SAX_YCUOK_MBBL.W",
        "eia_cushing_crude_stocks",
        "Cushing Crude Stocks",
    ),
    EiaInventoryDefinition(
        "PET.WGTSTUS1.W", "eia_us_motor_gasoline_stocks", "U.S. Motor Gasoline Stocks"
    ),
    EiaInventoryDefinition(
        "PET.WDISTUS1.W", "eia_us_distillate_stocks", "U.S. Distillate Fuel Oil Stocks"
    ),
)


def refresh_eia_commodity_core(
    *, root: Path | None = None, api_key: str | None = None
) -> dict[str, object]:
    key = api_key if api_key is not None else os.getenv("EIA_API_KEY", "")
    if not key.strip():
        raise RuntimeError(
            "EIA_API_KEY is not configured; refusing to publish placeholder data"
        )
    repo_root = root or Path.cwd()
    now = datetime.now(UTC)
    changed: list[bool] = []
    as_of: list[str] = []
    for definition in EIA_INVENTORIES:
        fetched = fetch_eia_series(definition.series_id, api_key=key)
        flags = validate_observations(fetched.observations)
        fatal = {
            "empty_series",
            "non_monotonic_dates",
            "duplicate_dates",
            "non_finite_value",
            "invalid_observation_date",
            "future_observation_date",
        }
        if fatal.intersection(flags):
            raise RuntimeError(
                f"EIA quality validation failed for {definition.series_id}: {flags}"
            )
        latest = fetched.observations[-1]
        stale = is_observation_stale(latest.date, max_age_days=10, today=now.date())
        if stale:
            flags.append("stale_latest_observation")
        payload = CanonicalSeries(
            seriesId=definition.canonical_id,
            label=definition.label,
            status="stale" if stale else "ready",
            latestValue=latest.value,
            unit="thousand_barrels",
            frequency="weekly",
            timezone="America/New_York",
            source="eia_api_v2",
            upstreamSource="U.S. Energy Information Administration",
            sourceSeriesId=definition.series_id,
            sourceUrl=fetched.source_url,
            observationDate=latest.date,
            asOf=latest.date,
            retrievedAt=now.isoformat().replace("+00:00", "Z"),
            isStale=stale,
            methodologyVersion="eia_weekly_petroleum_inventory_v1",
            qualityFlags=flags,
            rightsScope="official_public_data",
            observations=fetched.observations,
        ).model_dump(mode="json")
        path = (
            repo_root / "public/v1/commodity/series" / f"{definition.canonical_id}.json"
        )
        preserve_volatile_fields_when_materially_unchanged(path, payload)
        changed.append(write_json_if_changed(path, payload))
        as_of.append(latest.date)
    return {"changed": changed, "series": len(changed), "as_of": max(as_of)}
