"""CFTC Public Reporting Environment Disaggregated Futures Only adapter."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from platform_data.runtime import build_retry_session

CFTC_DISAGGREGATED_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
CFTC_POSITION_FIELDS = (
    "report_date_as_yyyy_mm_dd,cftc_contract_market_code,"
    "m_money_positions_long_all,m_money_positions_short_all,"
    "prod_merc_positions_long,prod_merc_positions_short"
)


@dataclass(frozen=True)
class CftcPosition:
    report_date: str
    managed_money_net: int
    producer_merchant_net: int


def parse_cftc_rows(rows: object, expected_code: str) -> list[CftcPosition]:
    if not isinstance(rows, list):
        raise TypeError("unexpected CFTC PRE response")
    parsed: list[CftcPosition] = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("cftc_contract_market_code") != expected_code
        ):
            continue
        try:
            parsed.append(
                CftcPosition(
                    report_date=str(row["report_date_as_yyyy_mm_dd"])[:10],
                    managed_money_net=int(row["m_money_positions_long_all"])
                    - int(row["m_money_positions_short_all"]),
                    producer_merchant_net=int(row["prod_merc_positions_long"])
                    - int(row["prod_merc_positions_short"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(parsed, key=lambda item: item.report_date)


def fetch_cftc_positions(
    contract_code: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> tuple[list[CftcPosition], str]:
    client = session or build_retry_session()
    response = client.get(
        CFTC_DISAGGREGATED_URL,
        params={
            "$select": CFTC_POSITION_FIELDS,
            "$where": f"cftc_contract_market_code='{contract_code}'",
            "$order": "report_date_as_yyyy_mm_dd",
            "$limit": "5000",
        },
        timeout=timeout,
        headers={
            "User-Agent": "platform-data/0.1 (+https://github.com/wuxingyuenan5-lgtm/platform-data)"
        },
    )
    response.raise_for_status()
    positions = parse_cftc_rows(response.json(), contract_code)
    if not positions:
        raise RuntimeError(f"CFTC PRE returned no positions for {contract_code}")
    return positions, response.url
