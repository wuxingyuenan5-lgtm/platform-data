import json
from pathlib import Path

from platform_data.models import CanonicalSeries, Observation
from platform_data.pipelines.crypto_dashboard import build_crypto_dashboard


def test_crypto_dashboard_keeps_binance_as_explicit_venue(tmp_path: Path):
    path = tmp_path / "public/v1/crypto/series/binance_btc_spot.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        CanonicalSeries(
            seriesId="binance_btc_spot",
            label="Binance BTCUSDT Spot",
            status="ready",
            latestValue=100,
            unit="price",
            frequency="daily",
            source="binance_public_api",
            sourceSeriesId="BTCUSDT",
            observationDate="2026-09-02",
            asOf="2026-09-02",
            methodologyVersion="binance_spot_daily_close_v1",
            qualityFlags=["venue_binance", "mode_venue_not_aggregate"],
            observations=[Observation(date="2026-09-02", value=100)],
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    result = build_crypto_dashboard(root=tmp_path)
    document = json.loads(
        (tmp_path / "public/v1/crypto/dashboard.json").read_text(encoding="utf-8")
    )
    assert result["series"] == 1
    assert (
        document["groups"]["binanceSpot"][0]["qualityFlags"][-1]
        == "mode_venue_not_aggregate"
    )
