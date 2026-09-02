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


def build_macro_market_detail(*, root: Path | None = None) -> dict[str, object]:
    repo_root = root or Path.cwd()
    source_path = repo_root / "public" / "v1" / "macro" / "series" / "us_treasury_10y.json"
    series = CanonicalSeries.model_validate_json(source_path.read_text(encoding="utf-8"))
    metrics = calculate_market_detail_metrics(
        series.observations,
        frequency=series.frequency,
        change_mode="basis_points",
    )
    row_flags = list(dict.fromkeys([*series.qualityFlags, *metrics.pop("qualityFlags")]))
    row = {
        "id": "macro-us10y",
        "name": "美国 10Y",
        "symbol": "US10Y",
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
    payload = _json_value({
        "schemaVersion": "1.0",
        "marketId": "macro",
        "status": series.status,
        "asOf": series.asOf,
        "retrievedAt": series.retrievedAt,
        "rows": [row],
    })
    output_path = repo_root / "public" / "v1" / "macro" / "market-detail.json"
    changed = write_json_if_changed(output_path, payload)
    return {"market_id": "macro", "rows": 1, "as_of": series.asOf, "changed": changed}
