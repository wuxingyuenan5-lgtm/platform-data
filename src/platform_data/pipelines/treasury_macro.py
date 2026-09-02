from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from platform_data.models import CanonicalSeries
from platform_data.providers.treasury import TreasurySeriesRequest, fetch_par_yield_series
from platform_data.quality import validate_observations
from platform_data.runtime import (
    is_observation_stale,
    preserve_volatile_fields_when_materially_unchanged,
)
from platform_data.storage.files import upsert_history_csv, write_json_if_changed


METHODOLOGY_VERSION = "treasury_par_yield_curve_v1"
TENOR_METADATA = {
    "2y": ("us_treasury_2y", "U.S. Treasury 2Y Par Yield", "2 Yr"),
    "10y": ("us_treasury_10y", "U.S. Treasury 10Y Par Yield", "10 Yr"),
    "30y": ("us_treasury_30y", "U.S. Treasury 30Y Par Yield", "30 Yr"),
}


def refresh_treasury_10y(*, root: Path | None = None, year: int | None = None) -> dict[str, object]:
    return refresh_treasury_tenor("10y", root=root, year=year)


def refresh_treasury_tenor(
    tenor: str, *, root: Path | None = None, year: int | None = None
) -> dict[str, object]:
    """Fetch, validate and publish one approved Treasury tenor with sufficient history."""

    repo_root = root or Path.cwd()
    now = datetime.now(timezone.utc)
    if tenor not in TENOR_METADATA:
        raise ValueError(f"unsupported published Treasury tenor: {tenor}")
    series_id, label, source_series_id = TENOR_METADATA[tenor]
    target_year = year or now.year
    years = [target_year] if year is not None else [target_year - 1, target_year]
    observations = []
    source_urls: list[str] = []
    for fetch_year in years:
        fetched, fetched_url = fetch_par_yield_series(
            TreasurySeriesRequest(tenor=tenor, year=fetch_year)
        )
        observations.extend(fetched)
        source_urls.append(fetched_url)
    observations = sorted({item.date: item for item in observations}.values(), key=lambda item: item.date)
    source_url = source_urls[-1]

    flags = validate_observations(observations, min_value=-5.0, max_value=30.0)
    fatal_flags = {
        "empty_series",
        "non_monotonic_dates",
        "duplicate_dates",
        "non_finite_value",
        "invalid_observation_date",
        "future_observation_date",
        "below_expected_range",
        "above_expected_range",
    }
    if fatal_flags.intersection(flags):
        raise RuntimeError(f"Treasury quality validation failed: {flags}")

    latest = observations[-1]
    is_stale = is_observation_stale(latest.date, max_age_days=7, today=now.date())
    if is_stale:
        flags.append("stale_latest_observation")

    series = CanonicalSeries(
        seriesId=series_id,
        label=label,
        status="stale" if is_stale else "ready",
        latestValue=latest.value,
        unit="percent",
        currency=None,
        frequency="daily_business_day",
        timezone="America/New_York",
        source="us_treasury",
        upstreamSource="U.S. Department of the Treasury",
        sourceSeriesId=source_series_id,
        sourceUrl=source_url,
        observationDate=latest.date,
        asOf=latest.date,
        retrievedAt=now.isoformat().replace("+00:00", "Z"),
        isStale=is_stale,
        methodologyVersion=METHODOLOGY_VERSION,
        qualityFlags=flags,
        rightsScope="official_public_data",
        observations=observations,
    )

    json_path = repo_root / "public" / "v1" / "macro" / "series" / f"{series_id}.json"

    payload = series.model_dump(mode="json")
    preserve_volatile_fields_when_materially_unchanged(json_path, payload)
    json_changed = write_json_if_changed(json_path, payload)
    history_changed = False
    for history_year in sorted({int(item.date[:4]) for item in observations}):
        history_path = repo_root / "history" / series_id / f"{history_year}.csv"
        year_observations = [item for item in observations if int(item.date[:4]) == history_year]
        history_changed = upsert_history_csv(history_path, year_observations) or history_changed

    return {
        "series_id": series_id,
        "status": series.status,
        "as_of": series.asOf,
        "latest_value": series.latestValue,
        "json_changed": json_changed,
        "history_changed": history_changed,
        "source_url": source_url,
    }


def refresh_treasury_market_tenors(
    *, root: Path | None = None, year: int | None = None
) -> list[dict[str, object]]:
    return [
        refresh_treasury_tenor(tenor, root=root, year=year)
        for tenor in ("2y", "10y", "30y")
    ]
