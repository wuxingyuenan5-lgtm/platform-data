from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from platform_data.models import CanonicalSeries
from platform_data.storage.files import write_json_if_changed
from platform_data.transforms.market_detail import calculate_market_detail_metrics


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


MACRO_TREASURY_ROWS = (
    ("us_treasury_2y", "macro-us2y", "美国 2Y", "US2Y"),
    ("us_treasury_10y", "macro-us10y", "美国 10Y", "US10Y"),
    ("us_treasury_30y", "macro-us30y", "美国 30Y", "US30Y"),
)
MACRO_FRED_ROWS = (
    ("net_dollar_liquidity", "macro-netliq", "美元净流动性", "NETLIQ", "absolute"),
    ("us_m2", "macro-m2sl", "美国 M2", "M2SL", "absolute"),
    ("walcl", "macro-walcl", "美联储总资产", "WALCL", "absolute"),
    ("wdtgal", "macro-wdtgal", "TGA 余额", "WDTGAL", "absolute"),
    ("rrp", "macro-rrp", "逆回购余额", "RRPONTSYD", "absolute"),
    ("dff", "macro-dff", "联邦基金利率", "DFF", "basis_points"),
    ("sofr", "macro-sofr", "SOFR", "SOFR", "basis_points"),
    ("us_10y_real_yield", "macro-dfii10", "美国 10Y 实际利率", "DFII10", "basis_points"),
    ("us_10y_breakeven", "macro-t10yie", "美国 10Y 通胀预期", "T10YIE", "basis_points"),
    ("us_cpi", "macro-cpi", "美国 CPI", "CPIAUCSL", "percent"),
    ("us_pce", "macro-pce", "美国 PCE", "PCEPI", "percent"),
    ("us_unrate", "macro-unrate", "美国失业率", "UNRATE", "basis_points"),
    ("vix", "macro-vix", "VIX 波动率", "VIX", "percent"),
)
MACRO_YAHOO_ROWS = (
    ("dxy", "macro-dxy", "美元指数", "DXY"),
    ("usdcnh", "macro-usdcnh", "离岸人民币", "USDCNH"),
    ("tlt", "macro-tlt", "长久期美债 ETF", "TLT"),
    ("hyg", "macro-hyg", "高收益债 ETF", "HYG"),
)


def build_macro_market_detail(*, root: Path | None = None) -> dict[str, object]:
    repo_root = root or Path.cwd()
    rows: list[dict[str, object]] = []
    series_documents: list[CanonicalSeries] = []
    for series_id, row_id, name, symbol in MACRO_TREASURY_ROWS:
        source_path = repo_root / "public" / "v1" / "macro" / "series" / f"{series_id}.json"
        if not source_path.exists():
            continue
        series = CanonicalSeries.model_validate_json(source_path.read_text(encoding="utf-8"))
        series_documents.append(series)
        metrics = calculate_market_detail_metrics(
            series.observations,
            frequency=series.frequency,
            change_mode="basis_points",
        )
        row_flags = list(dict.fromkeys([*series.qualityFlags, *metrics.pop("qualityFlags")]))
        rows.append(
            {
                "id": row_id,
                "name": name,
                "symbol": symbol,
                "status": series.status,
                "unit": series.unit,
                "changeUnit": "basis_points",
                "frequency": series.frequency,
                "timezone": series.timezone,
                "observationDate": series.observationDate,
                "asOf": series.asOf,
                "source": series.source,
                "sourceUrl": series.sourceUrl,
                "methodologyVersion": "market_detail_windows_v1",
                "qualityFlags": row_flags,
                **metrics,
            }
        )
    for series_id, row_id, name, symbol, change_mode in MACRO_FRED_ROWS:
        source_path = repo_root / "public" / "v1" / "macro" / "series" / f"{series_id}.json"
        if not source_path.exists():
            continue
        series = CanonicalSeries.model_validate_json(source_path.read_text(encoding="utf-8"))
        series_documents.append(series)
        metrics = calculate_market_detail_metrics(
            series.observations,
            frequency=series.frequency,
            change_mode=change_mode,
        )
        row_flags = list(dict.fromkeys([*series.qualityFlags, *metrics.pop("qualityFlags")]))
        rows.append(
            {
                "id": row_id,
                "name": name,
                "symbol": symbol,
                "status": series.status,
                "unit": series.unit,
                "changeUnit": change_mode,
                "frequency": series.frequency,
                "timezone": series.timezone,
                "observationDate": series.observationDate,
                "asOf": series.asOf,
                "source": series.source,
                "sourceUrl": series.sourceUrl,
                "methodologyVersion": "market_detail_windows_v1",
                "qualityFlags": row_flags,
                **metrics,
            }
        )
    for series_id, row_id, name, symbol in MACRO_YAHOO_ROWS:
        source_path = repo_root / "public" / "v1" / "macro" / "series" / f"{series_id}.json"
        if not source_path.exists():
            continue
        series = CanonicalSeries.model_validate_json(source_path.read_text(encoding="utf-8"))
        series_documents.append(series)
        metrics = calculate_market_detail_metrics(
            series.observations, frequency=series.frequency, change_mode="percent"
        )
        row_flags = list(dict.fromkeys([*series.qualityFlags, *metrics.pop("qualityFlags")]))
        rows.append(
            {
                "id": row_id, "name": name, "symbol": symbol, "status": series.status,
                "unit": series.unit, "changeUnit": "percent", "frequency": series.frequency,
                "timezone": series.timezone, "observationDate": series.observationDate,
                "asOf": series.asOf, "source": series.source, "sourceUrl": series.sourceUrl,
                "methodologyVersion": "market_detail_windows_v1", "qualityFlags": row_flags,
                **metrics,
            }
        )
    if not rows:
        raise RuntimeError("no approved macro market-detail canonical series found")
    latest_series = max(series_documents, key=lambda item: item.asOf or "")
    payload = _json_value({
        "schemaVersion": "1.0",
        "marketId": "macro",
        "status": "ready" if all(item.status == "ready" for item in series_documents) else "partial",
        "asOf": latest_series.asOf,
        "retrievedAt": latest_series.retrievedAt,
        "rows": rows,
    })
    output_path = repo_root / "public" / "v1" / "macro" / "market-detail.json"
    changed = write_json_if_changed(output_path, payload)
    return {"market_id": "macro", "rows": len(rows), "as_of": latest_series.asOf, "changed": changed}
