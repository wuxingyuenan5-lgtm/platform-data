from platform_data.providers.binance import (
    parse_basis,
    parse_funding,
    parse_open_interest,
    parse_spot_klines,
)


def test_binance_daily_parsers_preserve_frozen_methodology():
    day1 = 1788220800000
    day2 = 1788307200000
    now = datetime.fromtimestamp((day2 + 2 * 86_400_000) / 1000, UTC)
    spot = parse_spot_klines(
        [
            [day2, "0", "0", "0", "20", "0", day2 + 86_400_000 - 1],
            [day1, "0", "0", "0", "10", "0", day1 + 86_400_000 - 1],
        ],
        now=now,
    )
    funding = parse_funding(
        [
            {"fundingTime": day1, "fundingRate": "0.0001"},
            {"fundingTime": day1 + 8 * 3600 * 1000, "fundingRate": "0.0003"},
        ]
    )
    oi = parse_open_interest(
        [
            {"timestamp": day1, "sumOpenInterestValue": "100"},
            {"timestamp": day1 + 3600 * 1000, "sumOpenInterestValue": "120"},
        ]
    )
    basis = parse_basis(
        [
            {"timestamp": day1, "basisRate": "0.001"},
            {"timestamp": day1 + 3600 * 1000, "basisRate": "-0.002"},
        ]
    )
    assert [item.value for item in spot] == [10, 20]
    assert funding[0].value == 0.02
    assert oi[0].value == 120
    assert basis[0].value == -0.2


def test_spot_parser_excludes_open_daily_candle():
    day1 = 1788220800000
    day2 = 1788307200000
    now = datetime.fromtimestamp((day2 + 3600_000) / 1000, UTC)
    spot = parse_spot_klines(
        [
            [day1, "0", "0", "0", "10", "0", day1 + 86_400_000 - 1],
            [day2, "0", "0", "0", "99", "0", day2 + 86_400_000 - 1],
        ],
        now=now,
    )
    assert [(item.date, item.value) for item in spot] == [("2026-09-01", 10)]


from datetime import UTC, datetime
