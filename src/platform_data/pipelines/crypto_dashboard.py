"""Build the Crypto V1 source-backed dashboard contract."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from platform_data.models import CanonicalSeries
from platform_data.storage.files import write_json_if_changed

GROUPS = {
    "binanceSpot": ["binance_btc_spot", "binance_eth_spot"],
    "binanceFunding": ["binance_btc_funding", "binance_eth_funding"],
    "binanceOpenInterest": [
        "binance_btc_open_interest",
        "binance_eth_open_interest",
    ],
    "binancePerpetualBasis": [
        "binance_btc_perpetual_basis",
        "binance_eth_perpetual_basis",
    ],
}


def build_crypto_dashboard(*, root: Path | None = None) -> dict[str, object]:
    repo_root = root or Path.cwd()
    groups: dict[str, list[dict[str, object]]] = {}
    all_series: list[CanonicalSeries] = []
    for group_id, series_ids in GROUPS.items():
        group = []
        for series_id in series_ids:
            path = repo_root / "public/v1/crypto/series" / f"{series_id}.json"
            if not path.exists():
                continue
            series = CanonicalSeries.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            all_series.append(series)
            document = series.model_dump(mode="json")
            cutoff = date.fromisoformat(
                series.observationDate or series.observations[-1].date
            ) - timedelta(days=5 * 366)
            document["observations"] = [
                item.model_dump(mode="json")
                for item in series.observations
                if date.fromisoformat(item.date) >= cutoff
            ]
            group.append(document)
        groups[group_id] = group
    if not all_series:
        raise RuntimeError("no Crypto dashboard series available")
    payload = {
        "schemaVersion": "1.0",
        "status": "ready"
        if all(item.status == "ready" for item in all_series)
        else "partial",
        "asOf": max((item.asOf or "") for item in all_series),
        "groups": groups,
    }
    path = repo_root / "public/v1/crypto/dashboard.json"
    return {
        "changed": write_json_if_changed(path, payload),
        "series": len(all_series),
        "as_of": payload["asOf"],
    }
