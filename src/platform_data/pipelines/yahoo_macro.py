from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from platform_data.models import CanonicalSeries, Observation
from platform_data.providers.yahoo_chart import fetch_yahoo_chart
from platform_data.quality import validate_observations
from platform_data.runtime import is_observation_stale, preserve_volatile_fields_when_materially_unchanged
from platform_data.storage.files import write_json_if_changed
from platform_data.transforms.market_detail import derive_ratio_observations


@dataclass(frozen=True)
class YahooMacroDefinition:
    series_id: str
    label: str
    symbol: str
    unit: str
    currency: str | None


YAHOO_MACRO_SERIES = (
    YahooMacroDefinition("dxy", "U.S. Dollar Index", "DX-Y.NYB", "index", None),
    YahooMacroDefinition("usdcnh", "USD/CNH", "CNH=X", "fx_rate", "CNH"),
    YahooMacroDefinition("tlt", "iShares 20+ Year Treasury Bond ETF", "TLT", "price", "USD"),
    YahooMacroDefinition("hyg", "iShares iBoxx High Yield Corporate Bond ETF", "HYG", "price", "USD"),
    YahooMacroDefinition("lqd", "iShares iBoxx Investment Grade Corporate Bond ETF", "LQD", "price", "USD"),
)


def refresh_yahoo_macro_market(*, root: Path | None = None) -> list[dict[str, object]]:
    repo_root = root or Path.cwd()
    now = datetime.now(timezone.utc)
    results = []
    published: dict[str, list[Observation]] = {}
    for definition in YAHOO_MACRO_SERIES:
        observations, source_url = fetch_yahoo_chart(definition.symbol)
        published[definition.series_id] = observations
        flags = validate_observations(observations)
        latest = observations[-1]
        stale = is_observation_stale(latest.date, max_age_days=7, today=now.date())
        if stale:
            flags.append("stale_latest_observation")
        series = CanonicalSeries(
            seriesId=definition.series_id,
            label=definition.label,
            status="stale" if stale else "ready",
            latestValue=latest.value,
            unit=definition.unit,
            currency=definition.currency,
            frequency="daily_business_day",
            timezone="America/New_York",
            source="yahoo_chart",
            upstreamSource="Yahoo Finance public chart distribution",
            sourceSeriesId=definition.symbol,
            sourceUrl=source_url,
            observationDate=latest.date,
            asOf=latest.date,
            retrievedAt=now.isoformat().replace("+00:00", "Z"),
            isStale=stale,
            methodologyVersion="yahoo_adjusted_close_v1",
            qualityFlags=flags,
            rightsScope="internal_research_public_web_no_sla",
            observations=observations,
        )
        path = repo_root / "public/v1/macro/series" / f"{definition.series_id}.json"
        payload = series.model_dump(mode="json")
        preserve_volatile_fields_when_materially_unchanged(path, payload)
        results.append(
            {"series_id": definition.series_id, "changed": write_json_if_changed(path, payload), "as_of": latest.date}
        )
    ratio_observations = derive_ratio_observations(published["hyg"], published["lqd"])
    latest = ratio_observations[-1]
    ratio = CanonicalSeries(
        seriesId="hyg_lqd_ratio",
        label="HYG / LQD Adjusted Close Ratio",
        status="ready",
        latestValue=latest.value,
        unit="ratio",
        frequency="daily_business_day",
        timezone="America/New_York",
        source="derived",
        upstreamSource="Yahoo Finance HYG and LQD adjusted close",
        sourceSeriesId="HYG/LQD",
        sourceUrl="https://finance.yahoo.com/",
        observationDate=latest.date,
        asOf=latest.date,
        retrievedAt=now.isoformat().replace("+00:00", "Z"),
        methodologyVersion="exact_date_adjusted_close_ratio_v1",
        rightsScope="internal_research_public_web_no_sla",
        observations=ratio_observations,
    )
    ratio_path = repo_root / "public/v1/macro/series/hyg_lqd_ratio.json"
    ratio_payload = ratio.model_dump(mode="json")
    preserve_volatile_fields_when_materially_unchanged(ratio_path, ratio_payload)
    results.append(
        {"series_id": ratio.seriesId, "changed": write_json_if_changed(ratio_path, ratio_payload), "as_of": latest.date}
    )
    return results
