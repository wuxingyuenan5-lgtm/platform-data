import json
from datetime import date, timedelta
from pathlib import Path

from platform_data.models import Observation
from platform_data.pipelines.market_detail import build_macro_market_detail
from platform_data.transforms.market_detail import (
    calculate_market_detail_metrics,
    derive_ratio_observations,
)


def _daily_history(days: int = 400) -> list[Observation]:
    start = date(2025, 1, 1)
    return [
        Observation(date=(start + timedelta(days=index)).isoformat(), value=100 + index)
        for index in range(days)
    ]


def test_daily_history_supports_shared_windows_and_52_week_high():
    metrics = calculate_market_detail_metrics(
        _daily_history(), frequency="daily", change_mode="percent"
    )

    assert metrics["close"] == 499
    assert metrics["change1d"] is not None
    assert metrics["change1w"] is not None
    assert metrics["change1m"] is not None
    assert metrics["changeQtd"] is not None
    assert metrics["changeYtd"] is not None
    assert metrics["change1y"] is not None
    assert metrics["high52w"] == 499
    assert metrics["distance52wHigh"] == 0
    assert len(metrics["spark30d"]) == 30


def test_monthly_history_keeps_finer_windows_unavailable():
    observations = [
        Observation(date=f"2025-{month:02d}-28", value=month)
        for month in range(1, 13)
    ] + [Observation(date="2026-01-28", value=13)]

    metrics = calculate_market_detail_metrics(
        observations, frequency="monthly", change_mode="percent"
    )

    assert metrics["change1d"] is None
    assert metrics["change1w"] is None
    assert metrics["change1m"] is not None
    assert metrics["change1y"] is not None


def test_yield_changes_are_basis_points():
    observations = [
        Observation(date="2026-08-28", value=4.73),
        Observation(date="2026-08-31", value=4.75),
    ]
    metrics = calculate_market_detail_metrics(
        observations, frequency="daily_business_day", change_mode="basis_points"
    )

    assert metrics["change1d"] == 2


def test_ratio_uses_exact_date_intersection_without_forward_fill():
    numerator = [
        Observation(date="2026-08-28", value=10),
        Observation(date="2026-08-31", value=12),
    ]
    denominator = [
        Observation(date="2026-08-29", value=2),
        Observation(date="2026-08-31", value=3),
    ]

    assert derive_ratio_observations(numerator, denominator) == [
        Observation(date="2026-08-31", value=4.0)
    ]


def test_real_treasury_history_builds_macro_vertical_slice(tmp_path: Path):
    source = Path("public/v1/macro/series/us_treasury_10y.json")
    target = tmp_path / source
    target.parent.mkdir(parents=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result = build_macro_market_detail(root=tmp_path)
    document = json.loads(
        (tmp_path / "public/v1/macro/market-detail.json").read_text(encoding="utf-8")
    )

    assert result["rows"] == 1
    assert document["rows"][0]["id"] == "macro-us10y"
    assert document["rows"][0]["close"] == 4.75
    assert document["rows"][0]["changeUnit"] == "basis_points"
    assert document["rows"][0]["spark30d"]
