"""FRED provider adapter placeholder.

The provider contract is frozen here. Runtime implementation will fetch only
permitted public series and normalize into the platform schema.
"""

from dataclasses import dataclass


@dataclass
class FredSeriesRequest:
    series_id: str


def provider_name() -> str:
    return "fred"
