from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from platform_data.models import CanonicalSeries
from platform_data.providers.treasury import TreasurySeriesRequest, fetch_par_yield_series
from platform_data.quality import validate_observations
from platform_data.storage.files import upsert_history_csv, write_json_if_changed


SERIES_ID = "us_treasury_10y"
LABEL = "U.S. Treasury 10Y Par Yield"
METHODOLOGY_VERSION = "treasury_par_yield_curve_v1"


def _preserve_retrieved_at_when_materially_unchanged(path: Path, payload: dict[str, object]) -> None:
    """Avoid a daily Git diff when only the fetch timestamp changed."""

    if not path.exists():
        return
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    comparable_keys = set(payload) - {"retrievedAt"}
    if all(existing.get(key) == payload.get(key) for key in comparable_keys):
        previous_retrieved_at = existing.get("retrievedAt")
        if previous_retrieved_at:
            payload["retrievedAt"] = previous_retrieved_at


def refresh_treasury_10y(*, root: Path | None = None, year: int | None = None) -> dict[str, object]:
    """Fetch, validate, publish and persist the U.S. Treasury 10Y series."""

    repo_root = root or Path.cwd()
    now = datetime.now(timezone.utc)
    request = TreasurySeriesRequest(tenor="10y", year=year)
    observations, source_url = fetch_par_yield_series(request)

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
    latest_date = date.fromisoformat(latest.date)
    age_days = (now.date() - latest_date).days
    is_stale = age_days > 7
    if is_stale:
        flags.append("stale_latest_observation")

    series = CanonicalSeries(
        seriesId=SERIES_ID,
        label=LABEL,
        status="stale" if is_stale else "ready",
        latestValue=latest.value,
        unit="percent",
        currency=None,
        frequency="daily_business_day",
        timezone="America/New_York",
        source="us_treasury",
        upstreamSource="U.S. Department of the Treasury",
        sourceSeriesId="10 Yr",
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

    json_path = repo_root / "public" / "v1" / "macro" / "series" / f"{SERIES_ID}.json"
    history_year = int(observations[-1].date[:4])
    history_path = repo_root / "history" / SERIES_ID / f"{history_year}.csv"

    payload = series.model_dump(mode="json")
    _preserve_retrieved_at_when_materially_unchanged(json_path, payload)
    json_changed = write_json_if_changed(json_path, payload)
    history_changed = upsert_history_csv(history_path, observations)

    return {
        "series_id": SERIES_ID,
        "status": series.status,
        "as_of": series.asOf,
        "latest_value": series.latestValue,
        "json_changed": json_changed,
        "history_changed": history_changed,
        "source_url": source_url,
    }
