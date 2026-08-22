"""US Treasury provider contract."""

from dataclasses import dataclass


@dataclass
class TreasurySeriesRequest:
    tenor: str


def provider_name() -> str:
    return "us_treasury"
