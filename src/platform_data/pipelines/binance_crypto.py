"""Publish Binance-only Crypto V1 spot and derivatives series."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from platform_data.models import CanonicalSeries, Observation
from platform_data.providers.binance import (
    fetch_basis_daily,
    fetch_funding_daily,
    fetch_open_interest_daily,
    fetch_spot_daily,
)
from platform_data.quality import validate_observations
from platform_data.runtime import (
    is_observation_stale,
    preserve_volatile_fields_when_materially_unchanged,
)
from platform_data.storage.files import write_json_if_changed

Fetcher = Callable[[str], tuple[list[Observation], str]]
ASSETS = {"btc": "BTCUSDT", "eth": "ETHUSDT"}
SERIES = {
    "spot": (fetch_spot_daily, "price", "binance_spot_daily_close_v1", 2),
    "funding": (
        fetch_funding_daily,
        "percent",
        "binance_usdm_funding_daily_mean_v1",
        2,
    ),
    "open_interest": (
        fetch_open_interest_daily,
        "usd",
        "binance_usdm_oi_daily_last_usd_v1",
        2,
    ),
    "perpetual_basis": (
        fetch_basis_daily,
        "percent",
        "binance_usdm_perpetual_basis_daily_last_v1",
        2,
    ),
}


def _merge_existing(
    path: Path, observations: list[Observation], *, prune_after_latest: bool = False
) -> list[Observation]:
    merged: dict[str, float | None] = {}
    if path.exists():
        existing = CanonicalSeries.model_validate_json(path.read_text(encoding="utf-8"))
        merged.update({item.date: item.value for item in existing.observations})
    merged.update({item.date: item.value for item in observations})
    if prune_after_latest:
        latest_incoming = observations[-1].date
        merged = {day: value for day, value in merged.items() if day <= latest_incoming}
    return [Observation(date=day, value=merged[day]) for day in sorted(merged)]


def refresh_binance_crypto_core(*, root: Path | None = None) -> dict[str, object]:
    repo_root = root or Path.cwd()
    now = datetime.now(UTC)
    changed: list[bool] = []
    dates: list[str] = []
    for asset, symbol in ASSETS.items():
        for metric, (fetcher, unit, methodology, max_age_days) in SERIES.items():
            incoming, source_url = fetcher(symbol)
            series_id = f"binance_{asset}_{metric}"
            path = repo_root / "public/v1/crypto/series" / f"{series_id}.json"
            observations = _merge_existing(
                path, incoming, prune_after_latest=metric == "spot"
            )
            flags = validate_observations(observations)
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
                    f"Binance quality validation failed for {series_id}: {flags}"
                )
            latest = observations[-1]
            stale = is_observation_stale(
                latest.date, max_age_days=max_age_days, today=now.date()
            )
            if stale:
                flags.append("stale_latest_observation")
            flags.extend(
                ["venue_binance", "mode_venue_not_aggregate", "quote_asset_usdt"]
            )
            payload = CanonicalSeries(
                seriesId=series_id,
                label=f"Binance {symbol} {metric.replace('_', ' ').title()}",
                status="stale" if stale else "ready",
                latestValue=latest.value,
                unit=unit,
                currency="USDT" if metric == "spot" else None,
                frequency="daily",
                timezone="UTC",
                source="binance_public_api",
                upstreamSource="Binance",
                sourceSeriesId=symbol,
                sourceUrl=source_url,
                observationDate=latest.date,
                asOf=latest.date,
                retrievedAt=now.isoformat().replace("+00:00", "Z"),
                isStale=stale,
                methodologyVersion=methodology,
                qualityFlags=flags,
                rightsScope="official_public_market_data",
                observations=observations,
            ).model_dump(mode="json")
            preserve_volatile_fields_when_materially_unchanged(path, payload)
            changed.append(write_json_if_changed(path, payload))
            dates.append(latest.date)
    return {"changed": changed, "series": len(changed), "as_of": max(dates)}
