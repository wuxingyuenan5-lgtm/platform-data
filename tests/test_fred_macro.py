from pathlib import Path

from platform_data.models import Observation
from platform_data.pipelines.fred_macro import FredMacroDefinition, _publish_series, _year_over_year
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


def test_year_over_year_uses_frequency_lag():
    observations = [Observation(date=f"2025-{month:02d}-01", value=100 + month) for month in range(1, 13)]
    observations.append(Observation(date="2026-01-01", value=111.1))

    result = _year_over_year(observations, "monthly")

    assert len(result) == 1
    assert round(result[0].value or 0, 2) == 10.0
