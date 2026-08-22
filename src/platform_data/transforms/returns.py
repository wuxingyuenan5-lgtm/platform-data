"""Market detail return calculations."""

from typing import Iterable


def pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return (current / previous - 1) * 100


def latest_window(values: Iterable[float], window: int) -> list[float]:
    data = list(values)
    return data[-window:]
