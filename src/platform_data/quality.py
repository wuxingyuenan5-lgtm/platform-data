from __future__ import annotations

import math
from datetime import date

from platform_data.models import Observation


def validate_observations(
    observations: list[Observation],
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> list[str]:
    """Return quality flags; an empty list means the series passed checks."""

    flags: list[str] = []
    if not observations:
        return ["empty_series"]

    dates = [item.date for item in observations]
    if dates != sorted(dates):
        flags.append("non_monotonic_dates")
    if len(dates) != len(set(dates)):
        flags.append("duplicate_dates")

    for item in observations:
        if item.value is None:
            continue
        if not math.isfinite(item.value):
            flags.append("non_finite_value")
            break
        if min_value is not None and item.value < min_value:
            flags.append("below_expected_range")
            break
        if max_value is not None and item.value > max_value:
            flags.append("above_expected_range")
            break

    try:
        latest = date.fromisoformat(observations[-1].date)
        if latest > date.today():
            flags.append("future_observation_date")
    except ValueError:
        flags.append("invalid_observation_date")

    return flags
