"""Official MOF-China Government Bond Yield Curve adapter."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from platform_data.models import Observation
from platform_data.runtime import build_retry_session

CHINABOND_HISTORY_URL = "https://yield.chinabond.com.cn/cbweb-czb-web/czb/historyQuery"
TENOR_FIELDS = {"2y": "twoYear", "10y": "tenYear", "30y": "thirtyYear"}


@dataclass(frozen=True)
class ChinaBondRequest:
    tenor: str
    start_date: str
    end_date: str


def parse_chinabond_payload(payload: object, tenor: str) -> list[Observation]:
    if tenor not in TENOR_FIELDS:
        raise ValueError(f"unsupported ChinaBond tenor: {tenor}")
    if not isinstance(payload, dict) or not isinstance(payload.get("heList"), list):
        raise TypeError("unexpected ChinaBond history payload")
    field = TENOR_FIELDS[tenor]
    observations: list[Observation] = []
    for row in payload["heList"]:
        if (
            not isinstance(row, dict)
            or row.get("qxmc") != "ChinaBond Government Bond Yield Curve"
        ):
            continue
        observed_on = str(row.get("workTime") or "")
        raw_value = row.get(field)
        if not observed_on or raw_value in (None, ""):
            continue
        observations.append(Observation(date=observed_on, value=float(raw_value)))
    return sorted(observations, key=lambda item: item.date)


def fetch_chinabond_yield(
    request: ChinaBondRequest,
    *,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> tuple[list[Observation], str]:
    if request.tenor not in TENOR_FIELDS:
        raise ValueError(f"unsupported ChinaBond tenor: {request.tenor}")
    client = session or build_retry_session()
    response = client.get(
        CHINABOND_HISTORY_URL,
        params={
            "startDate": request.start_date,
            "endDate": request.end_date,
            "gjqx": request.tenor.removesuffix("y"),
            "locale": "en_US",
            "qxmc": "1",
        },
        timeout=timeout,
        headers={
            "User-Agent": "platform-data/0.1 (+https://github.com/wuxingyuenan5-lgtm/platform-data)"
        },
    )
    response.raise_for_status()
    observations = parse_chinabond_payload(response.json(), request.tenor)
    if not observations:
        raise RuntimeError(f"ChinaBond returned no usable {request.tenor} observations")
    return observations, response.url
