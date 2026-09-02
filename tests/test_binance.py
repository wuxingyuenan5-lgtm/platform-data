from datetime import UTC, datetime
from types import SimpleNamespace

from platform_data.providers.binance import (
    _fetch_json_via_doh,
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


def test_futures_dns_fallback_uses_verified_doh(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "platform_data.providers.binance.shutil.which", lambda _name: "curl"
    )

    def fake_run(args, **_kwargs):
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr("platform_data.providers.binance.subprocess.run", fake_run)
    payload, source_url = _fetch_json_via_doh(
        "https://fapi.binance.com/fapi/v1/fundingRate",
        params={"symbol": "BTCUSDT"},
        headers={"User-Agent": "test"},
        timeout=5,
    )
    assert payload == []
    assert "--doh-url" in captured["args"]
    assert "https://cloudflare-dns.com/dns-query" in captured["args"]
    assert source_url.endswith("symbol=BTCUSDT")
