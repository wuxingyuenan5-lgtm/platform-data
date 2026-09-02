from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from platform_data.models import CanonicalSeries, Observation
from platform_data.providers.fred import FredSeriesRequest, fetch_fred_series
from platform_data.quality import validate_observations
from platform_data.runtime import is_observation_stale, preserve_volatile_fields_when_materially_unchanged
from platform_data.storage.files import write_json_if_changed


@dataclass(frozen=True)
class FredMacroDefinition:
    series_id: str
    label: str
    source_id: str
    unit: str
    frequency: str
    stale_days: int
    transform: str = "level"


FRED_MACRO_SERIES = (
    FredMacroDefinition("vix", "Cboe Volatility Index", "VIXCLS", "index", "daily_business_day", 7),
    FredMacroDefinition("dff", "Effective Federal Funds Rate", "DFF", "percent", "daily", 7),
    FredMacroDefinition("sofr", "Secured Overnight Financing Rate", "SOFR", "percent", "daily_business_day", 7),
    FredMacroDefinition("us_10y_real_yield", "U.S. 10Y Real Yield", "DFII10", "percent", "daily_business_day", 7),
    FredMacroDefinition("us_10y_breakeven", "U.S. 10Y Breakeven Inflation", "T10YIE", "percent", "daily_business_day", 7),
    FredMacroDefinition("us_cpi", "U.S. Consumer Price Index", "CPIAUCSL", "index", "monthly", 75),
    FredMacroDefinition("us_pce", "U.S. PCE Price Index", "PCEPI", "index", "monthly", 75),
    FredMacroDefinition("us_unrate", "U.S. Unemployment Rate", "UNRATE", "percent", "monthly", 75),
    FredMacroDefinition("us_m2", "U.S. M2 Money Stock", "M2SL", "usd_billion", "monthly", 75),
    FredMacroDefinition("walcl", "Federal Reserve Total Assets", "WALCL", "usd_million", "weekly", 14),
    FredMacroDefinition("wdtgal", "U.S. Treasury General Account", "WDTGAL", "usd_million", "weekly", 14),
    FredMacroDefinition("rrp", "Overnight Reverse Repurchase Agreements", "RRPONTSYD", "usd_billion", "daily_business_day", 7),
    FredMacroDefinition("us_real_gdp_yoy", "U.S. Real GDP YoY", "GDPC1", "percent", "quarterly", 200, "yoy"),
    FredMacroDefinition("us_indpro_yoy", "U.S. Industrial Production YoY", "INDPRO", "percent", "monthly", 75, "yoy"),
    FredMacroDefinition("us_initial_claims_4w", "U.S. Initial Claims 4W MA", "IC4WSA", "persons", "weekly", 14),
    FredMacroDefinition("us_cfnai", "Chicago Fed National Activity Index", "CFNAI", "index", "monthly", 75),
    FredMacroDefinition("us_cfnai_ma3", "Chicago Fed National Activity Index 3M MA", "CFNAIMA3", "index", "monthly", 75),
    FredMacroDefinition("us_core_cpi_yoy", "U.S. Core CPI YoY", "CPILFESL", "percent", "monthly", 75, "yoy"),
    FredMacroDefinition("us_cpi_yoy", "U.S. CPI YoY", "CPIAUCSL", "percent", "monthly", 75, "yoy"),
    FredMacroDefinition("us_pce_yoy", "U.S. PCE Price Index YoY", "PCEPI", "percent", "monthly", 75, "yoy"),
    FredMacroDefinition("us_core_pce_yoy", "U.S. Core PCE YoY", "PCEPILFE", "percent", "monthly", 75, "yoy"),
    FredMacroDefinition("us_ppi_yoy", "U.S. PPI Final Demand YoY", "PPIFIS", "percent", "monthly", 75, "yoy"),
    FredMacroDefinition("us_5y_breakeven", "U.S. 5Y Breakeven Inflation", "T5YIE", "percent", "daily_business_day", 7),
    FredMacroDefinition("us_5y5y_forward", "U.S. 5Y5Y Forward Inflation", "T5YIFR", "percent", "daily_business_day", 7),
    FredMacroDefinition("fed_target_lower", "Federal Funds Target Lower", "DFEDTARL", "percent", "daily", 7),
    FredMacroDefinition("fed_target_upper", "Federal Funds Target Upper", "DFEDTARU", "percent", "daily", 7),
    FredMacroDefinition("iorb", "Interest on Reserve Balances", "IORB", "percent", "daily", 7),
    FredMacroDefinition("on_rrp_award", "ON RRP Award Rate", "RRPONTSYAWARD", "percent", "daily", 7),
    FredMacroDefinition("effr", "Effective Federal Funds Rate", "EFFR", "percent", "daily_business_day", 7),
    FredMacroDefinition("us_hy_oas", "U.S. High Yield Option-Adjusted Spread", "BAMLH0A0HYM2", "percent", "daily_business_day", 7),
)


def _year_over_year(observations: list[Observation], frequency: str) -> list[Observation]:
    lag = 4 if frequency == "quarterly" else 12
    rows: list[Observation] = []
    valid = [item for item in observations if item.value is not None]
    for index in range(lag, len(valid)):
        current = valid[index]
        previous = valid[index - lag]
        if previous.value:
            rows.append(
                Observation(
                    date=current.date,
                    value=(current.value / previous.value - 1) * 100,
                )
            )
    return rows


def _publish_series(
    definition: FredMacroDefinition, observations: list[Observation], source_url: str, repo_root: Path
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    flags = validate_observations(observations)
    fatal = {"empty_series", "non_monotonic_dates", "duplicate_dates", "non_finite_value", "invalid_observation_date", "future_observation_date"}
    if fatal.intersection(flags):
        raise RuntimeError(f"FRED quality validation failed for {definition.source_id}: {flags}")
    latest = observations[-1]
    stale = is_observation_stale(latest.date, max_age_days=definition.stale_days, today=now.date())
    if stale:
        flags.append("stale_latest_observation")
    series = CanonicalSeries(
        seriesId=definition.series_id,
        label=definition.label,
        status="stale" if stale else "ready",
        latestValue=latest.value,
        unit=definition.unit,
        frequency=definition.frequency,
        timezone="America/New_York",
        source="fred",
        upstreamSource="Federal Reserve Bank of St. Louis / source agency",
        sourceSeriesId=definition.source_id,
        sourceUrl=source_url,
        observationDate=latest.date,
        asOf=latest.date,
        retrievedAt=now.isoformat().replace("+00:00", "Z"),
        isStale=stale,
        methodologyVersion="fred_public_csv_v1",
        qualityFlags=flags,
        rightsScope="internal_research_with_attribution",
        observations=observations,
    )
    path = repo_root / "public/v1/macro/series" / f"{definition.series_id}.json"
    payload = series.model_dump(mode="json")
    preserve_volatile_fields_when_materially_unchanged(path, payload)
    return {"series_id": definition.series_id, "changed": write_json_if_changed(path, payload), "as_of": latest.date}


def refresh_fred_macro_core(*, root: Path | None = None) -> list[dict[str, object]]:
    repo_root = root or Path.cwd()
    start_date = (datetime.now(timezone.utc).date() - timedelta(days=365 * 12 + 4)).isoformat()
    results = []
    published: dict[str, tuple[FredMacroDefinition, list[Observation], str]] = {}
    for definition in FRED_MACRO_SERIES:
        observations, source_url = fetch_fred_series(
            FredSeriesRequest(series_id=definition.source_id, start_date=start_date)
        )
        if definition.transform == "yoy":
            observations = _year_over_year(observations, definition.frequency)
        results.append(_publish_series(definition, observations, source_url, repo_root))
        published[definition.series_id] = (definition, observations, source_url)
    walcl = published["walcl"][1]
    wdtgal = published["wdtgal"][1]
    rrp = published["rrp"][1]
    tga_by_date = {item.date: item.value for item in wdtgal if item.value is not None}
    rrp_by_date = {item.date: item.value for item in rrp if item.value is not None}
    netliq = [
        Observation(date=item.date, value=item.value - tga_by_date[item.date] - rrp_by_date[item.date] * 1000)
        for item in walcl
        if item.value is not None and item.date in tga_by_date and item.date in rrp_by_date
    ]
    netliq_definition = FredMacroDefinition(
        "net_dollar_liquidity",
        "Net Dollar Liquidity Proxy",
        "WALCL-WDTGAL-RRPONTSYD*1000",
        "usd_million",
        "weekly",
        14,
    )
    results.append(
        _publish_series(
            netliq_definition,
            netliq,
            "https://fred.stlouisfed.org/",
            repo_root,
        )
    )
    return results
