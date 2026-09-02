from pathlib import Path

from platform_data.models import Observation
from platform_data.pipelines.fred_macro import FredMacroDefinition, _publish_series
from platform_data.providers.fred import parse_fred_csv


def test_parse_fred_csv_skips_missing_values():
    sample = "observation_date,SOFR\n2026-08-28,3.65\n2026-08-31,.\n2026-09-01,3.68\n"

    assert parse_fred_csv(sample, "SOFR") == [
        Observation(date="2026-08-28", value=3.65),
        Observation(date="2026-09-01", value=3.68),
    ]


def test_publish_fred_series_keeps_provenance(tmp_path: Path):
    definition = FredMacroDefinition("sofr", "SOFR", "SOFR", "percent", "daily", 7)

    result = _publish_series(
        definition,
        [Observation(date="2026-09-01", value=3.68)],
        "https://fred.example/sofr",
        tmp_path,
    )

    assert result["series_id"] == "sofr"
    payload = (tmp_path / "public/v1/macro/series/sofr.json").read_text(encoding="utf-8")
    assert '"source": "fred"' in payload
    assert '"sourceSeriesId": "SOFR"' in payload
