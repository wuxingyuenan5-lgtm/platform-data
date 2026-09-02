from platform_data.models import Observation
from platform_data.pipelines.cftc_commodity import rolling_percentile
from platform_data.providers.cftc import parse_cftc_rows


def test_cftc_explicit_code_and_net_position_mapping():
    rows = [
        {
            "report_date_as_yyyy_mm_dd": "2026-08-25T00:00:00.000",
            "cftc_contract_market_code": "088691",
            "m_money_positions_long_all": "200",
            "m_money_positions_short_all": "75",
            "prod_merc_positions_long": "30",
            "prod_merc_positions_short": "160",
        }
    ]
    parsed = parse_cftc_rows(rows, "088691")
    assert parsed[0].managed_money_net == 125
    assert parsed[0].producer_merchant_net == -130


def test_cftc_rolling_percentile_is_deterministic():
    observations = [
        Observation(date=f"2026-01-{index:02d}", value=value)
        for index, value in enumerate([10, 30, 20, 40], start=1)
    ]
    result = rolling_percentile(observations, window=3)
    assert [item.value for item in result] == [100, 100, 2 / 3 * 100, 100]
