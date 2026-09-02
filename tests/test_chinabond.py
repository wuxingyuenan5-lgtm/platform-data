from datetime import date

from platform_data.pipelines.chinabond_macro import _windows
from platform_data.providers.chinabond import parse_chinabond_payload


def test_chinabond_maps_exact_frozen_tenors():
    payload = {
        "heList": [
            {
                "workTime": "2026-09-01",
                "twoYear": "1.24",
                "tenYear": "1.68",
                "thirtyYear": "2.14",
                "qxmc": "ChinaBond Government Bond Yield Curve",
            }
        ]
    }
    assert parse_chinabond_payload(payload, "2y")[0].value == 1.24
    assert parse_chinabond_payload(payload, "10y")[0].value == 1.68
    assert parse_chinabond_payload(payload, "30y")[0].value == 2.14


def test_chinabond_windows_respect_official_one_year_limit():
    windows = _windows(date(2026, 9, 2), days=760)
    assert all((end - start).days <= 364 for start, end in windows)
    assert windows[-1][1] == date(2026, 9, 2)
