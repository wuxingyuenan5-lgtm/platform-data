from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from platform_data.models import Observation
from platform_data.runtime import build_retry_session

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def fetch_yahoo_chart(
    symbol: str, *, timeout: float = 20.0, session: requests.Session | None = None
) -> tuple[list[Observation], str]:
    url = YAHOO_CHART_URL.format(symbol=symbol)
    client = session or build_retry_session()
    response = client.get(
        url,
        params={"range": "2y", "interval": "1d", "events": "history"},
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 platform-data/0.1"},
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    results = payload.get("chart", {}).get("result") or []
    if not results:
        raise RuntimeError(f"Yahoo chart returned no result for {symbol}")
    result = results[0]
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators", {})
    adjusted = (indicators.get("adjclose") or [{}])[0].get("adjclose")
    values = adjusted or (indicators.get("quote") or [{}])[0].get("close") or []
    observations = [
        Observation(
            date=datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
            value=float(value),
        )
        for timestamp, value in zip(timestamps, values, strict=False)
        if value is not None
    ]
    if not observations:
        raise RuntimeError(f"Yahoo chart returned no usable observations for {symbol}")
    return observations, str(response.url)
