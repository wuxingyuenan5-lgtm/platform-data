from platform_data.pipelines.global_m2 import _china_page, _month


def test_month_normalizes_provider_periods():
    assert _month("2026.7") == "2026-07"
    assert _month("202607") == "2026-07"
    assert _month("2026-07-31") == "2026-07"


def test_china_page_extracts_akshare_upstream_payload():
    text = 'callback(({config:{},count:"1",data:[["2026.7","3555077.24","7.70"]]}));'
    count, rows = _china_page(text)
    assert count == 1
    assert rows[0][1] == "3555077.24"
