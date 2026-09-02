"""Publish official MOF-China Government Bond Yield Curve tenors."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from platform_data.models import CanonicalSeries
from platform_data.providers.chinabond import (
    CHINABOND_HISTORY_URL,
    ChinaBondRequest,
    fetch_chinabond_yield,
)
from platform_data.quality import validate_observations
from platform_data.runtime import (
    is_observation_stale,
    preserve_volatile_fields_when_materially_unchanged,
)
from platform_data.storage.files import write_json_if_changed

TENORS = {
    "2y": ("cn_treasury_2y", "China Government Bond 2Y Yield"),
    "10y": ("cn_treasury_10y", "China Government Bond 10Y Yield"),
    "30y": ("cn_treasury_30y", "China Government Bond 30Y Yield"),
}


def _windows(end_date: date, days: int = 760) -> list[tuple[date, date]]:
    start = end_date - timedelta(days=days)
    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end_date:
        window_end = min(cursor + timedelta(days=364), end_date)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def refresh_chinabond_market_tenors(
    *, root: Path | None = None
) -> list[dict[str, object]]:
    repo_root = root or Path.cwd()
    now = datetime.now(UTC)
    results: list[dict[str, object]] = []
    for tenor, (series_id, label) in TENORS.items():
        path = repo_root / "public/v1/macro/series" / f"{series_id}.json"
        existing = (
            CanonicalSeries.model_validate_json(path.read_text(encoding="utf-8"))
            if path.exists()
            else None
        )
        observations = list(existing.observations) if existing else []
        fetch_windows = (
            [
                (
                    date.fromisoformat(existing.observations[-1].date)
                    - timedelta(days=45),
                    now.date(),
                )
            ]
            if existing and existing.observations
            else _windows(now.date())
        )
        for start, end in fetch_windows:
            rows, _ = fetch_chinabond_yield(
                ChinaBondRequest(
                    tenor=tenor, start_date=start.isoformat(), end_date=end.isoformat()
                )
            )
            observations.extend(rows)
        observations = sorted(
            {item.date: item for item in observations}.values(),
            key=lambda item: item.date,
        )
        flags = validate_observations(observations, min_value=-5, max_value=30)
        fatal = {
            "empty_series",
            "non_monotonic_dates",
            "duplicate_dates",
            "non_finite_value",
            "invalid_observation_date",
            "future_observation_date",
            "below_expected_range",
            "above_expected_range",
        }
        if fatal.intersection(flags):
            raise RuntimeError(
                f"ChinaBond quality validation failed for {tenor}: {flags}"
            )
        latest = observations[-1]
        stale = is_observation_stale(latest.date, max_age_days=7, today=now.date())
        if stale:
            flags.append("stale_latest_observation")
        series = CanonicalSeries(
            seriesId=series_id,
            label=label,
            status="stale" if stale else "ready",
            latestValue=latest.value,
            unit="percent",
            frequency="daily_business_day",
            timezone="Asia/Shanghai",
            source="chinabond",
            upstreamSource="China Central Depository & Clearing / Ministry of Finance",
            sourceSeriesId=f"MOF China Government Bond Yield Curve {tenor}",
            sourceUrl=CHINABOND_HISTORY_URL,
            observationDate=latest.date,
            asOf=latest.date,
            retrievedAt=now.isoformat().replace("+00:00", "Z"),
            isStale=stale,
            methodologyVersion="mof_china_government_bond_yield_curve_v1",
            qualityFlags=flags,
            rightsScope="official_public_data_internal_research",
            observations=observations,
        )
        payload = series.model_dump(mode="json")
        preserve_volatile_fields_when_materially_unchanged(path, payload)
        results.append(
            {
                "series_id": series_id,
                "status": series.status,
                "as_of": series.asOf,
                "latest_value": series.latestValue,
                "changed": write_json_if_changed(path, payload),
            }
        )
    return results
