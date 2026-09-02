from __future__ import annotations

from pathlib import Path

from platform_data.models import CanonicalSeries
from platform_data.storage.files import write_json_if_changed

DASHBOARD_GROUPS = {
    "growthProduction": ["us_real_gdp_yoy", "us_indpro_yoy"],
    "growthLabor": ["us_initial_claims_4w"],
    "growthActivity": ["us_cfnai", "us_cfnai_ma3"],
    "actualInflation": ["us_cpi_yoy", "us_core_cpi_yoy", "us_pce_yoy", "us_core_pce_yoy"],
    "upstreamInflation": ["us_ppi_yoy"],
    "marketInflation": ["us_5y_breakeven", "us_10y_breakeven", "us_5y5y_forward"],
    "rateCorridor": ["fed_target_lower", "fed_target_upper", "iorb", "on_rrp_award", "effr", "sofr"],
}


def build_macro_dashboard(*, root: Path | None = None) -> dict[str, object]:
    repo_root = root or Path.cwd()
    groups: dict[str, list[dict[str, object]]] = {}
    all_series: list[CanonicalSeries] = []
    for group_id, series_ids in DASHBOARD_GROUPS.items():
        group = []
        for series_id in series_ids:
            path = repo_root / "public/v1/macro/series" / f"{series_id}.json"
            if not path.exists():
                continue
            series = CanonicalSeries.model_validate_json(path.read_text(encoding="utf-8"))
            all_series.append(series)
            group.append(series.model_dump(mode="json"))
        groups[group_id] = group
    if not all_series:
        raise RuntimeError("no macro dashboard series available")
    payload = {
        "schemaVersion": "1.0",
        "status": "ready" if all(item.status == "ready" for item in all_series) else "partial",
        "asOf": max((item.asOf or "") for item in all_series),
        "groups": groups,
    }
    path = repo_root / "public/v1/macro/dashboard.json"
    return {"changed": write_json_if_changed(path, payload), "series": len(all_series), "as_of": payload["asOf"]}
