"""Build the frozen five-region Global M2 methodology proxy."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from io import StringIO
from pathlib import Path

import requests

from platform_data.models import CanonicalSeries, Observation
from platform_data.providers.fred import FredSeriesRequest, fetch_fred_series
from platform_data.quality import validate_observations
from platform_data.runtime import (
    build_retry_session,
    preserve_volatile_fields_when_materially_unchanged,
)
from platform_data.storage.files import write_json_if_changed

ECB_DATA_URL = "https://data-api.ecb.europa.eu/service/data"
BOJ_URL = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
BOE_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
CHINA_MONEY_URL = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
USER_AGENT = "platform-data/0.1 (+https://github.com/wuxingyuenan5-lgtm/platform-data)"


def _month(value: str | int) -> str:
    text = str(value)
    if "." in text:
        year, month = text.split(".", 1)
    elif "-" in text:
        year, month = text[:7].split("-", 1)
    else:
        year, month = text[:4], text[4:6]
    return f"{int(year):04d}-{int(month):02d}"


def _csv_values(text: str) -> list[tuple[str, float]]:
    return [
        (row["TIME_PERIOD"], float(row["OBS_VALUE"]))
        for row in csv.DictReader(StringIO(text.lstrip("\ufeff")))
        if row.get("TIME_PERIOD") and row.get("OBS_VALUE")
    ]


def _get(session: requests.Session, url: str, **kwargs: object) -> requests.Response:
    response = session.get(
        url, timeout=30, headers={"User-Agent": USER_AGENT}, **kwargs
    )
    response.raise_for_status()
    return response


def _fetch_ecb_monthly_m2(
    session: requests.Session, start_date: str
) -> dict[str, float]:
    key = "M.U2.Y.V.M20.X.1.U2.2300.Z01.E"
    response = _get(
        session,
        f"{ECB_DATA_URL}/BSI/{key}",
        params={"startPeriod": start_date[:7], "format": "csvdata"},
    )
    return {
        _month(period): value / 1_000_000
        for period, value in _csv_values(response.text)
    }


def _fetch_boj_m2(session: requests.Session, start_date: str) -> dict[str, float]:
    response = _get(
        session,
        BOJ_URL,
        params={
            "format": "json",
            "lang": "en",
            "db": "MD02",
            "startDate": start_date[:7].replace("-", ""),
            "code": "MAM1NAM2M2MO",
        },
    )
    payload = response.json()
    result = payload["RESULTSET"][0]
    if result["UNIT"] != "100 million yen":
        raise RuntimeError(f"unexpected BOJ M2 unit: {result['UNIT']}")
    dates = result["VALUES"]["SURVEY_DATES"]
    values = result["VALUES"]["VALUES"]
    return {
        _month(period): float(value) / 10_000
        for period, value in zip(dates, values)
        if value is not None
    }


def _fetch_boe_m4(session: requests.Session, start_date: str) -> dict[str, float]:
    response = _get(
        session,
        BOE_URL,
        params={
            "CodeVer": "new",
            "xml.x": "yes",
            "Datefrom": date.fromisoformat(start_date).strftime("%d/%b/%Y"),
            "Dateto": "now",
            "SeriesCodes": "LPMAUYM",
            "VPD": "Y",
            "VFD": "N",
        },
    )
    if (
        "in sterling millions" not in response.text
        or "not seasonally adjusted" not in response.text
    ):
        raise RuntimeError("unexpected BoE LPMAUYM metadata")
    rows = re.findall(r'TIME="([^"]+)"[^>]+OBS_VALUE="([^"]+)"', response.text)
    return {_month(period): float(value) / 1_000_000 for period, value in rows}


def _china_page(text: str) -> tuple[int, list[list[object]]]:
    decoded = text.encode("latin1").decode("gb18030") if "count:" not in text else text
    count_match = re.search(r'count:"(\d+)"', decoded)
    marker = ",data:"
    start = decoded.rfind(marker)
    end = decoded.rfind("]}")
    if not count_match or start < 0 or end < 0:
        raise RuntimeError("unexpected AKShare/Sina money-supply response")
    rows = json.loads(decoded[start + len(marker) : end + 1])
    return int(count_match.group(1)), rows


def _fetch_china_m2(session: requests.Session, start_date: str) -> dict[str, float]:
    results: dict[str, float] = {}
    offset = 0
    count = 1
    while offset < count:
        response = _get(
            session,
            CHINA_MONEY_URL,
            params={
                "cate": "fininfo",
                "event": "1",
                "from": str(offset),
                "num": "31",
                "condition": "",
            },
        )
        response.encoding = "gb18030"
        count, rows = _china_page(response.text)
        for row in rows:
            month = _month(str(row[0]))
            if month >= start_date[:7] and row[1] is not None:
                results[month] = float(row[1]) / 10_000
        if rows and min(_month(str(row[0])) for row in rows) < start_date[:7]:
            break
        offset += 31
    benchmark = results.get("2026-07")
    if benchmark is None or abs(benchmark - 355.51) > 0.02:
        raise RuntimeError("China M2 failed frozen PBOC 2026-07 benchmark validation")
    return results


def _fetch_ecb_monthly_usd_fx(
    session: requests.Session, currency: str, start_date: str
) -> dict[str, float]:
    currencies = ["USD"] if currency == "EUR" else ["USD", currency]
    daily: dict[str, dict[str, float]] = {}
    for item in currencies:
        response = _get(
            session,
            f"{ECB_DATA_URL}/EXR/D.{item}.EUR.SP00.A",
            params={"startPeriod": start_date, "format": "csvdata"},
        )
        daily[item] = dict(_csv_values(response.text))
    monthly: dict[str, list[float]] = defaultdict(list)
    for observed_on, usd_per_eur in daily["USD"].items():
        if currency == "EUR":
            monthly[_month(observed_on)].append(usd_per_eur)
        elif observed_on in daily[currency]:
            monthly[_month(observed_on)].append(
                usd_per_eur / daily[currency][observed_on]
            )
    return {
        month: sum(values) / len(values) for month, values in monthly.items() if values
    }


def _publish(series: CanonicalSeries, root: Path) -> bool:
    path = root / "public/v1/macro/series" / f"{series.seriesId}.json"
    payload = series.model_dump(mode="json")
    preserve_volatile_fields_when_materially_unchanged(path, payload)
    return write_json_if_changed(path, payload)


def refresh_global_m2(
    *, root: Path | None = None, session: requests.Session | None = None
) -> dict[str, object]:
    repo_root = root or Path.cwd()
    client = session or build_retry_session()
    now = datetime.now(UTC)
    start_date = (now.date() - timedelta(days=366 * 11)).replace(day=1).isoformat()
    us_rows, _ = fetch_fred_series(
        FredSeriesRequest(series_id="M2NS", start_date=start_date), session=client
    )
    local = {
        "us": {
            _month(item.date): float(item.value) / 1_000
            for item in us_rows
            if item.value is not None
        },
        "cn": _fetch_china_m2(client, start_date),
        "eu": _fetch_ecb_monthly_m2(client, start_date),
        "jp": _fetch_boj_m2(client, start_date),
        "gb": _fetch_boe_m4(client, start_date),
    }
    fx = {
        "us": {month: 1.0 for month in local["us"]},
        "cn": _fetch_ecb_monthly_usd_fx(client, "CNY", start_date),
        "eu": _fetch_ecb_monthly_usd_fx(client, "EUR", start_date),
        "jp": _fetch_ecb_monthly_usd_fx(client, "JPY", start_date),
        "gb": _fetch_ecb_monthly_usd_fx(client, "GBP", start_date),
    }
    common = sorted(
        set.intersection(*(set(local[key]) & set(fx[key]) for key in local))
    )
    if len(common) < 120:
        raise RuntimeError(f"Global M2 common-month coverage too short: {len(common)}")
    component_values = {
        key: [
            Observation(date=f"{month}-01", value=local[key][month] * fx[key][month])
            for month in common
        ]
        for key in local
    }
    observations = [
        Observation(
            date=f"{month}-01",
            value=sum(local[key][month] * fx[key][month] for key in local),
        )
        for month in common
    ]
    flags = validate_observations(observations)
    if flags:
        raise RuntimeError(f"Global M2 quality validation failed: {flags}")
    latest = observations[-1]
    level = CanonicalSeries(
        seriesId="global_m2_proxy",
        label="Global M2 Proxy",
        status="ready",
        latestValue=latest.value,
        unit="usd_trillion",
        currency="USD",
        frequency="monthly",
        source="methodology_proxy",
        upstreamSource="Federal Reserve / PBOC-validated AKShare adapter / ECB / BOJ / Bank of England",
        sourceSeriesId="M2NS + CN M2 + ECB BSI M2 + BOJ M2 + BoE M4",
        sourceUrl="https://data-api.ecb.europa.eu/",
        observationDate=latest.date,
        asOf=latest.date,
        retrievedAt=now.isoformat().replace("+00:00", "Z"),
        methodologyVersion="global_m2_five_region_monthly_fx_v1",
        qualityFlags=[
            "proxy_methodology_based",
            "common_month_intersection",
            "ecb_daily_fx_monthly_average",
        ],
        rightsScope="internal_research_with_attribution",
        observations=observations,
    )
    yoy = [
        Observation(
            date=observations[index].date,
            value=(observations[index].value / observations[index - 12].value - 1)
            * 100,
        )
        for index in range(12, len(observations))
        if observations[index].value is not None and observations[index - 12].value
    ]
    yoy_series = level.model_copy(
        update={
            "seriesId": "global_m2_proxy_yoy",
            "label": "Global M2 Proxy YoY",
            "latestValue": yoy[-1].value,
            "unit": "percent",
            "observationDate": yoy[-1].date,
            "asOf": yoy[-1].date,
            "observations": yoy,
        }
    )
    component_labels = {
        "us": "United States M2 in USD",
        "cn": "China M2 in USD",
        "eu": "Euro Area M2 in USD",
        "jp": "Japan M2 in USD",
        "gb": "United Kingdom M4 in USD",
    }
    component_series = [
        level.model_copy(
            update={
                "seriesId": f"global_m2_{key}_component",
                "label": label,
                "latestValue": component_values[key][-1].value,
                "observations": component_values[key],
                "qualityFlags": [
                    "global_m2_component",
                    "ecb_daily_fx_monthly_average",
                ],
            }
        )
        for key, label in component_labels.items()
    ]
    component_share_series = [
        level.model_copy(
            update={
                "seriesId": f"global_m2_{key}_share",
                "label": f"{label} Share",
                "latestValue": component_values[key][-1].value / latest.value * 100,
                "unit": "percent",
                "observations": [
                    Observation(
                        date=item.date,
                        value=item.value / observations[index].value * 100,
                    )
                    for index, item in enumerate(component_values[key])
                ],
                "qualityFlags": ["global_m2_component_share"],
            }
        )
        for key, label in component_labels.items()
    ]
    published = [level, yoy_series, *component_series, *component_share_series]
    return {
        "changed": [_publish(item, repo_root) for item in published],
        "months": len(observations),
        "as_of": latest.date,
        "latest_usd_trillion": latest.value,
    }
