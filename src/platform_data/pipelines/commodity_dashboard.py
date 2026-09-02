"""Build the Commodity V1 source-backed dashboard contract."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from platform_data.models import CanonicalSeries
from platform_data.storage.files import write_json_if_changed

COMMODITIES = ("gold", "silver", "copper", "wti", "natural_gas")


def build_commodity_dashboard(*, root: Path | None = None) -> dict[str, object]:
    repo_root = root or Path.cwd()
    groups: dict[str, list[dict[str, object]]] = {}
    all_series: list[CanonicalSeries] = []
    for slug in COMMODITIES:
        title = "".join(part.title() for part in slug.split("_"))
        group_specs = {
            f"cftc{title}Net": [
                f"cftc_{slug}_managed_money_net",
                f"cftc_{slug}_producer_merchant_net",
            ],
            f"cftc{title}Percentile": [f"cftc_{slug}_managed_money_percentile"],
        }
        for group_id, series_ids in group_specs.items():
            group = []
            for series_id in series_ids:
                path = repo_root / "public/v1/commodity/series" / f"{series_id}.json"
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
        raise RuntimeError("no Commodity dashboard series available")
    payload = {
        "schemaVersion": "1.0",
        "status": "ready"
        if all(item.status == "ready" for item in all_series)
        else "partial",
        "asOf": max((item.asOf or "") for item in all_series),
        "groups": groups,
    }
    path = repo_root / "public/v1/commodity/dashboard.json"
    return {
        "changed": write_json_if_changed(path, payload),
        "series": len(all_series),
        "as_of": payload["asOf"],
    }
