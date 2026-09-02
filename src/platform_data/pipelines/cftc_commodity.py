"""Publish the frozen five-market CFTC positioning core."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from platform_data.models import CanonicalSeries, Observation
from platform_data.providers.cftc import CFTC_DISAGGREGATED_URL, fetch_cftc_positions
from platform_data.quality import validate_observations
from platform_data.runtime import (
    is_observation_stale,
    preserve_volatile_fields_when_materially_unchanged,
)
from platform_data.storage.files import write_json_if_changed

CONTRACTS = {
    "gold": ("Gold", "088691"),
    "silver": ("Silver", "084691"),
    "copper": ("Copper", "085692"),
    "wti": ("WTI Crude Oil", "067651"),
    "natural_gas": ("Natural Gas", "023651"),
}
PERCENTILE_WINDOW = 260


def rolling_percentile(
    observations: list[Observation], window: int = PERCENTILE_WINDOW
) -> list[Observation]:
    output: list[Observation] = []
    for index, current in enumerate(observations):
        values = [
            item.value
            for item in observations[max(0, index - window + 1) : index + 1]
            if item.value is not None
        ]
        if current.value is None or not values:
            continue
        output.append(
            Observation(
                date=current.date,
                value=sum(value <= current.value for value in values)
                / len(values)
                * 100,
            )
        )
    return output


def _publish(
    *,
    root: Path,
    series_id: str,
    label: str,
    unit: str,
    source_code: str,
    observations: list[Observation],
    now: datetime,
    extra_flags: list[str] | None = None,
) -> bool:
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
        raise RuntimeError(f"CFTC quality validation failed for {series_id}: {flags}")
    latest = observations[-1]
    stale = is_observation_stale(latest.date, max_age_days=10, today=now.date())
    if stale:
        flags.append("stale_latest_observation")
    flags.extend(extra_flags or [])
    series = CanonicalSeries(
        seriesId=series_id,
        label=label,
        status="stale" if stale else "ready",
        latestValue=latest.value,
        unit=unit,
        frequency="weekly",
        timezone="America/New_York",
        source="cftc_pre",
        upstreamSource="U.S. Commodity Futures Trading Commission",
        sourceSeriesId=source_code,
        sourceUrl=CFTC_DISAGGREGATED_URL,
        observationDate=latest.date,
        asOf=latest.date,
        retrievedAt=now.isoformat().replace("+00:00", "Z"),
        isStale=stale,
        methodologyVersion="cftc_disaggregated_futures_only_v1",
        qualityFlags=list(dict.fromkeys(flags)),
        rightsScope="official_public_data",
        observations=observations,
    )
    path = root / "public/v1/commodity/series" / f"{series_id}.json"
    payload = series.model_dump(mode="json")
    preserve_volatile_fields_when_materially_unchanged(path, payload)
    return write_json_if_changed(path, payload)


def refresh_cftc_commodity_core(*, root: Path | None = None) -> dict[str, object]:
    repo_root = root or Path.cwd()
    now = datetime.now(UTC)
    changed: list[bool] = []
    latest_dates: list[str] = []
    for slug, (label, code) in CONTRACTS.items():
        rows, _ = fetch_cftc_positions(code)
        managed = [
            Observation(date=item.report_date, value=item.managed_money_net)
            for item in rows
        ]
        commercial = [
            Observation(date=item.report_date, value=item.producer_merchant_net)
            for item in rows
        ]
        percentile = rolling_percentile(managed)
        changed.extend(
            [
                _publish(
                    root=repo_root,
                    series_id=f"cftc_{slug}_managed_money_net",
                    label=f"CFTC {label} Managed Money Net",
                    unit="contracts",
                    source_code=code,
                    observations=managed,
                    now=now,
                ),
                _publish(
                    root=repo_root,
                    series_id=f"cftc_{slug}_producer_merchant_net",
                    label=f"CFTC {label} Producer/Merchant Net",
                    unit="contracts",
                    source_code=code,
                    observations=commercial,
                    now=now,
                ),
                _publish(
                    root=repo_root,
                    series_id=f"cftc_{slug}_managed_money_percentile",
                    label=f"CFTC {label} Managed Money Net 5Y Percentile",
                    unit="percentile",
                    source_code=code,
                    observations=percentile,
                    now=now,
                    extra_flags=["rolling_260_week_percentile"],
                ),
            ]
        )
        latest_dates.append(rows[-1].report_date)
    return {
        "changed": changed,
        "series": len(changed),
        "as_of": max(latest_dates),
        "contracts": {slug: code for slug, (_, code) in CONTRACTS.items()},
    }
