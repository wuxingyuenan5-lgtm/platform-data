from pathlib import Path

import pytest

from platform_data.models import Observation
from platform_data.pipelines import eia_commodity
from platform_data.pipelines.eia_commodity import refresh_eia_commodity_core
from platform_data.providers.eia import EiaSeries, fetch_eia_series, parse_eia_series


class FakeResponse:
    url = "https://api.eia.gov/v2/seriesid/PET.WCESTUS1.W?api_key=secret-value"

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "response": {
                "units": "MBBL",
                "data": [{"period": "2026-08-21", "value": 1}],
            }
        }


class FakeSession:
    def __init__(self):
        self.params = None

    def get(self, _url, *, params, **_kwargs):
        self.params = params
        return FakeResponse()


def test_parse_eia_series_orders_weekly_observations_and_skips_missing_values():
    observations, unit = parse_eia_series(
        {
            "response": {
                "units": "MBBL",
                "data": [
                    {"period": "2026-08-21", "value": "428910"},
                    {"period": "2026-08-14", "value": 428815},
                    {"period": "2026-08-07", "value": None},
                ],
            }
        }
    )
    assert [item.date for item in observations] == ["2026-08-14", "2026-08-21"]
    assert observations[-1].value == 428910
    assert unit == "MBBL"


def test_eia_refresh_fails_closed_without_api_key(tmp_path: Path):
    with pytest.raises(RuntimeError, match="EIA_API_KEY is not configured"):
        refresh_eia_commodity_core(root=tmp_path, api_key="")


def test_eia_fetch_passes_key_only_as_request_parameter_and_never_returns_it():
    session = FakeSession()
    result = fetch_eia_series("PET.WCESTUS1.W", api_key="secret-value", session=session)
    assert session.params["api_key"] == "secret-value"
    assert "secret-value" not in result.source_url


def test_eia_refresh_publishes_four_official_series(tmp_path: Path, monkeypatch):
    def fake_fetch(series_id: str, *, api_key: str):
        assert api_key == "configured-key"
        return EiaSeries(
            observations=[
                Observation(date="2026-08-14", value=100),
                Observation(date="2026-08-21", value=101),
            ],
            source_url=f"https://api.eia.gov/v2/seriesid/{series_id}",
            unit="MBBL",
        )

    monkeypatch.setattr(eia_commodity, "fetch_eia_series", fake_fetch)
    result = refresh_eia_commodity_core(root=tmp_path, api_key="configured-key")
    assert result["series"] == 4
    files = list((tmp_path / "public/v1/commodity/series").glob("eia_*.json"))
    assert len(files) == 4
    assert "configured-key" not in files[0].read_text(encoding="utf-8")
