"""Binance public Spot and USD-M Futures market-data adapter."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlparse

import requests

from platform_data.models import Observation
from platform_data.runtime import build_retry_session

SPOT_KLINES_URL = "https://data-api.binance.vision/api/v3/klines"
FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
OPEN_INTEREST_URL = "https://fapi.binance.com/futures/data/openInterestHist"
BASIS_URL = "https://fapi.binance.com/futures/data/basis"
DNS_OVER_HTTPS_URL = "https://cloudflare-dns.com/dns-query"


def _utc_date(timestamp_ms: object) -> str:
    return datetime.fromtimestamp(int(timestamp_ms) / 1000, UTC).date().isoformat()


def _daily_reduce(
    rows: object,
    *,
    timestamp: Callable[[object], object],
    value: Callable[[object], float],
    mode: str,
) -> list[Observation]:
    if not isinstance(rows, list):
        raise TypeError("unexpected Binance response")
    grouped: dict[str, list[float]] = {}
    for row in rows:
        try:
            grouped.setdefault(_utc_date(timestamp(row)), []).append(value(row))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    observations = []
    for day in sorted(grouped):
        values = grouped[day]
        reduced = sum(values) / len(values) if mode == "mean" else values[-1]
        observations.append(Observation(date=day, value=reduced))
    return observations


def parse_spot_klines(
    rows: object, *, now: datetime | None = None
) -> list[Observation]:
    if not isinstance(rows, list):
        raise TypeError("unexpected Binance response")
    cutoff_ms = int((now or datetime.now(UTC)).timestamp() * 1000)
    closed_rows = [
        row
        for row in rows
        if isinstance(row, list) and len(row) > 6 and int(row[6]) <= cutoff_ms
    ]
    return _daily_reduce(
        closed_rows,
        timestamp=lambda row: row[0],
        value=lambda row: float(row[4]),
        mode="last",
    )


def parse_funding(rows: object) -> list[Observation]:
    return _daily_reduce(
        rows,
        timestamp=lambda row: row["fundingTime"],
        value=lambda row: float(row["fundingRate"]) * 100,
        mode="mean",
    )


def parse_open_interest(rows: object) -> list[Observation]:
    return _daily_reduce(
        rows,
        timestamp=lambda row: row["timestamp"],
        value=lambda row: float(row["sumOpenInterestValue"]),
        mode="last",
    )


def parse_basis(rows: object) -> list[Observation]:
    return _daily_reduce(
        rows,
        timestamp=lambda row: row["timestamp"],
        value=lambda row: float(row["basisRate"]) * 100,
        mode="last",
    )


def _fetch(
    url: str,
    params: dict[str, str],
    parser: Callable[[object], list[Observation]],
    *,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> tuple[list[Observation], str]:
    client = session or build_retry_session()
    headers = {
        "User-Agent": "platform-data/0.1 (+https://github.com/wuxingyuenan5-lgtm/platform-data)"
    }
    try:
        response = client.get(url, params=params, timeout=timeout, headers=headers)
        response.raise_for_status()
        payload = response.json()
        source_url = response.url
    except requests.RequestException:
        payload, source_url = _fetch_json_via_doh(
            url, params=params, headers=headers, timeout=timeout
        )
    observations = parser(payload)
    if not observations:
        raise RuntimeError(f"Binance returned no observations for {params}")
    return observations, source_url


def _fetch_json_via_doh(
    url: str,
    *,
    params: dict[str, str],
    headers: dict[str, str],
    timeout: float,
) -> tuple[object, str]:
    host = urlparse(url).hostname
    if host != "fapi.binance.com":
        raise RuntimeError("DNS-over-HTTPS fallback is restricted to Binance Futures")
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl is required for verified DNS-over-HTTPS fallback")
    prepared_url = requests.Request("GET", url, params=params).prepare().url
    if prepared_url is None:
        raise RuntimeError("failed to prepare Binance request URL")
    result = subprocess.run(
        [
            curl,
            "--silent",
            "--show-error",
            "--fail",
            "--max-time",
            str(timeout),
            "--doh-url",
            DNS_OVER_HTTPS_URL,
            "--header",
            f"User-Agent: {headers['User-Agent']}",
            prepared_url,
        ],
        capture_output=True,
        text=True,
        timeout=timeout + 5,
        check=False,
    )
    if result.returncode == 0:
        return json.loads(result.stdout), prepared_url
    raise RuntimeError(
        f"verified Binance DNS fallback failed: {result.stderr.strip()}"
    )


def fetch_spot_daily(symbol: str, **kwargs) -> tuple[list[Observation], str]:
    return _fetch(
        SPOT_KLINES_URL,
        {"symbol": symbol, "interval": "1d", "limit": "1000"},
        parse_spot_klines,
        **kwargs,
    )


def fetch_funding_daily(symbol: str, **kwargs) -> tuple[list[Observation], str]:
    return _fetch(
        FUNDING_URL,
        {"symbol": symbol, "limit": "1000"},
        parse_funding,
        **kwargs,
    )


def fetch_open_interest_daily(symbol: str, **kwargs) -> tuple[list[Observation], str]:
    return _fetch(
        OPEN_INTEREST_URL,
        {"symbol": symbol, "period": "1h", "limit": "500"},
        parse_open_interest,
        **kwargs,
    )


def fetch_basis_daily(symbol: str, **kwargs) -> tuple[list[Observation], str]:
    return _fetch(
        BASIS_URL,
        {
            "pair": symbol,
            "contractType": "PERPETUAL",
            "period": "1h",
            "limit": "500",
        },
        parse_basis,
        **kwargs,
    )
