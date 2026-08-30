from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from platform_data.models import Observation


def write_json_if_changed(path: Path, payload: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.write_text(rendered, encoding="utf-8")
    return True


def upsert_history_csv(path: Path, observations: list[Observation]) -> bool:
    """Merge observations by date and write a deterministic two-column CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    merged: dict[str, float | None] = {}

    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                raw = row.get("value", "")
                merged[row["date"]] = None if raw == "" else float(raw)

    for item in observations:
        merged[item.date] = item.value

    lines = ["date,value"]
    for observation_date in sorted(merged):
        value = merged[observation_date]
        rendered_value = "" if value is None else format(value, ".10g")
        lines.append(f"{observation_date},{rendered_value}")
    rendered = "\n".join(lines) + "\n"

    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.write_text(rendered, encoding="utf-8")
    return True
