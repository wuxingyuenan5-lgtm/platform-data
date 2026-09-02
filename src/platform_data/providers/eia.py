"""EIA API v2 weekly petroleum inventory adapter."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from platform_data.models import Observation
from platform_data.runtime import build_retry_session

EIA_SERIES_URL = "https://api.eia.gov/v2/seriesid/{series_id}"


@dataclass(frozen=True)
class EiaSeries:
    observations: list[Observation]
    source_url: str
    unit: str | None


def parse_eia_series(payload: object) -> tuple[list[Observation], str | None]:
    if not isinstance(payload, dict) or not isinstance(payload.get("response"), dict):
        raise TypeError("unexpected EIA API response")
    response = payload["response"]
    rows = response.get("data")
    if not isinstance(rows, list):
        raise TypeError("unexpected EIA API data")
    observations: list[Observation] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            period = str(row["period"])
            value = float(row["value"])
        except (KeyError, TypeError, ValueError):
            continue
        observations.append(Observation(date=period[:10], value=value))
    observations.sort(key=lambda item: item.date)
    units = response.get("units")
    unit = units if isinstance(units, str) else None
    return observations, unit


def fetch_eia_series(
    series_id: str,
    *,
    api_key: str,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> EiaSeries:
    if not api_key.strip():
        raise ValueError("EIA_API_KEY is required")
    client = session or build_retry_session()
    url = EIA_SERIES_URL.format(series_id=series_id)
    response = client.get(
        url,
        params={
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": "5000",
        },
        timeout=timeout,
        headers={
            "User-Agent": "platform-data/0.1 (+https://github.com/wuxingyuenan5-lgtm/platform-data)"
        },
    )
    response.raise_for_status()
    observations, unit = parse_eia_series(response.json())
    if not observations:
        raise RuntimeError(f"EIA returned no observations for {series_id}")
    return EiaSeries(observations=observations, source_url=url, unit=unit)
