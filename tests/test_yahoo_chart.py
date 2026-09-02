from platform_data.providers.yahoo_chart import fetch_yahoo_chart


class _Response:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/TLT?range=2y"

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "chart": {
                "result": [
                    {
                        "timestamp": [1788278400, 1788364800],
                        "indicators": {"adjclose": [{"adjclose": [88.5, None]}]},
                    }
                ]
            }
        }


class _Session:
    def get(self, *_args, **_kwargs):
        return _Response()


def test_yahoo_chart_uses_adjusted_close_and_skips_missing_values():
    observations, source_url = fetch_yahoo_chart("TLT", session=_Session())

    assert len(observations) == 1
    assert observations[0].value == 88.5
    assert "TLT" in source_url
