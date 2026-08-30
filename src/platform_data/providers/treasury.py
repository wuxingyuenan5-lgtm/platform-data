"""U.S. Treasury official daily par-yield provider."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO

import requests

from platform_data.models import Observation
from platform_data.runtime import build_retry_session


TREASURY_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?_format=csv&field_tdr_date_value={year}"
    "&page=&type=daily_treasury_yield_curve"
)

TENOR_COLUMNS = {
    "3m": "3 Mo",
    "2y": "2 Yr",
    "10y": "10 Yr",
    "30y": "30 Yr",
}


@dataclass(frozen=True)
class TreasurySeriesRequest:
    tenor: str
    year: int | None = None


def provider_name() -> str:
    return "us_treasury"


def source_url(year: int) -> str:
    return TREASURY_CSV_URL.format(year=year)


def parse_par_yield_csv(csv_text: str, tenor: str) -> list[Observation]:
    """Parse one tenor from Treasury's official CSV distribution."""

    column = TENOR_COLUMNS.get(tenor.lower())
    if column is None:
        raise ValueError(f"unsupported Treasury tenor: {tenor}")

    reader = csv.DictReader(StringIO(csv_text.lstrip("\ufeff")))
    observations: list[Observation] = []

    for row in reader:
        raw_date = (row.get("Date") or "").strip()
        raw_value = (row.get(column) or "").strip()
        if not raw_date or not raw_value or raw_value.upper() == "N/A":
            continue
        try:
            iso_date = datetime.strptime(raw_date, "%m/%d/%Y").date().isoformat()
            value = float(raw_value)
        except (ValueError, TypeError):
            continue
        observations.append(Observation(date=iso_date, value=value))

    observations.sort(key=lambda item: item.date)
    return observations


def fetch_par_yield_series(
    request: TreasurySeriesRequest,
    *,
    timeout: float = 20.0,
    session: requests.Session | None = None,
) -> tuple[list[Observation], str]:
    """Fetch and parse an official Treasury par-yield series."""

    year = request.year or datetime.now(timezone.utc).year
    url = source_url(year)
    client = session or build_retry_session()
    response = client.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "platform-data/0.1 (+https://github.com/wuxingyuenan5-lgtm/platform-data)"},
    )
    response.raise_for_status()
    observations = parse_par_yield_csv(response.text, request.tenor)
    if not observations:
        raise RuntimeError(f"Treasury returned no usable observations for {request.tenor} in {year}")
    return observations, url
