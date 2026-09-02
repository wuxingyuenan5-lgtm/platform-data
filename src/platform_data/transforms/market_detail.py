from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from platform_data.models import Observation

ChangeMode = Literal["percent", "basis_points", "absolute"]


@dataclass(frozen=True)
class DatedValue:
    date: date
    value: Decimal


def _valid_points(observations: list[Observation]) -> list[DatedValue]:
    points = [
        DatedValue(date.fromisoformat(item.date), Decimal(str(item.value)))
        for item in observations
        if item.value is not None
    ]
    return sorted(points, key=lambda item: item.date)


def _months_before(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _last_on_or_before(points: list[DatedValue], target: date) -> DatedValue | None:
    return next((point for point in reversed(points) if point.date <= target), None)


def _change(current: Decimal, previous: Decimal, mode: ChangeMode) -> Decimal | None:
    if mode == "basis_points":
        return (current - previous) * Decimal("100")
    if mode == "absolute":
        return current - previous
    if previous == 0:
        return None
    return (current / previous - Decimal("1")) * Decimal("100")


def calculate_market_detail_metrics(
    observations: list[Observation],
    *,
    frequency: str,
    change_mode: ChangeMode,
) -> dict[str, object]:
    """Calculate display metrics from one canonical history without forward filling.

    Window anchors use the last real observation on or before each calendar boundary.
    Short windows that are finer than the source frequency remain unavailable.
    """

    points = _valid_points(observations)
    if not points:
        return {
            "close": None,
            "change1d": None,
            "change1w": None,
            "change1m": None,
            "changeQtd": None,
            "changeYtd": None,
            "change1y": None,
            "high52w": None,
            "distance52wHigh": None,
            "spark30d": [],
            "qualityFlags": ["empty_history"],
        }

    latest = points[-1]
    result: dict[str, object] = {"close": latest.value}
    short_window_allowed = {
        "change1d": frequency in {"daily", "daily_business_day", "continuous"},
        "change1w": frequency in {"daily", "daily_business_day", "continuous", "weekly"},
        "change1m": frequency
        in {"daily", "daily_business_day", "continuous", "weekly", "monthly"},
    }
    targets = {
        "change1d": latest.date - timedelta(days=1),
        "change1w": latest.date - timedelta(days=7),
        "change1m": _months_before(latest.date, 1),
        "changeQtd": date(latest.date.year, ((latest.date.month - 1) // 3) * 3 + 1, 1)
        - timedelta(days=1),
        "changeYtd": date(latest.date.year, 1, 1) - timedelta(days=1),
        "change1y": _months_before(latest.date, 12),
    }
    for field, target in targets.items():
        if field in short_window_allowed and not short_window_allowed[field]:
            result[field] = None
            continue
        anchor = _last_on_or_before(points[:-1], target)
        result[field] = _change(latest.value, anchor.value, change_mode) if anchor else None

    year_start = latest.date - timedelta(days=364)
    has_full_year = points[0].date <= year_start
    year_points = [point for point in points if point.date >= year_start]
    if has_full_year and year_points:
        high = max(point.value for point in year_points)
        result["high52w"] = high
        result["distance52wHigh"] = _change(latest.value, high, "percent")
        flags: list[str] = []
    else:
        result["high52w"] = None
        result["distance52wHigh"] = None
        flags = ["insufficient_52w_history"]

    spark_start = latest.date - timedelta(days=29)
    result["spark30d"] = [point.value for point in points if point.date >= spark_start]
    result["qualityFlags"] = flags
    return result


def align_series_by_date(
    numerator: list[Observation], denominator: list[Observation]
) -> list[tuple[str, Decimal, Decimal]]:
    """Return exact-date intersections for cross-asset calculations."""

    left = {point.date.isoformat(): point.value for point in _valid_points(numerator)}
    right = {point.date.isoformat(): point.value for point in _valid_points(denominator)}
    return [(key, left[key], right[key]) for key in sorted(left.keys() & right.keys())]


def derive_ratio_observations(
    numerator: list[Observation], denominator: list[Observation]
) -> list[Observation]:
    rows: list[Observation] = []
    for observed_on, left, right in align_series_by_date(numerator, denominator):
        if right != 0:
            rows.append(Observation(date=observed_on, value=float(left / right)))
    return rows
