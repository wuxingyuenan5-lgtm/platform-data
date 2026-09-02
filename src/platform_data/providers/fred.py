"""FRED public CSV distribution adapter for approved macro series."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO

import requests

from platform_data.models import Observation
from platform_data.runtime import build_retry_session

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start_date}"


@dataclass(frozen=True)
class FredSeriesRequest:
    series_id: str
    start_date: str


def provider_name() -> str:
    return "fred"


def parse_fred_csv(csv_text: str, series_id: str) -> list[Observation]:
    reader = csv.DictReader(StringIO(csv_text.lstrip("\ufeff")))
    observations: list[Observation] = []
    for row in reader:
        observed_on = (row.get("observation_date") or row.get("DATE") or "").strip()
        raw_value = (row.get(series_id) or "").strip()
        if not observed_on or not raw_value or raw_value == ".":
            continue
        try:
            observations.append(Observation(date=observed_on, value=float(raw_value)))
        except ValueError:
            continue
    observations.sort(key=lambda item: item.date)
    return observations


def fetch_fred_series(
    request: FredSeriesRequest,
    *,
    timeout: float = 20.0,
    session: requests.Session | None = None,
) -> tuple[list[Observation], str]:
    url = FRED_CSV_URL.format(series_id=request.series_id, start_date=request.start_date)
    client = session or build_retry_session()
    response = client.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "platform-data/0.1 (+https://github.com/wuxingyuenan5-lgtm/platform-data)"},
    )
    response.raise_for_status()
    observations = parse_fred_csv(response.text, request.series_id)
    if not observations:
        raise RuntimeError(f"FRED returned no usable observations for {request.series_id}")
    return observations, url
