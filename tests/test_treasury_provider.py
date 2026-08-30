from platform_data.providers.treasury import parse_par_yield_csv


def test_parse_treasury_10y_csv():
    sample = "Date,3 Mo,2 Yr,10 Yr,30 Yr\n08/27/2026,3.84,4.20,4.67,5.19\n08/28/2026,3.90,4.34,4.73,5.22\n"
    observations = parse_par_yield_csv(sample, "10y")

    assert [item.date for item in observations] == ["2026-08-27", "2026-08-28"]
    assert [item.value for item in observations] == [4.67, 4.73]


def test_parse_treasury_rejects_unknown_tenor():
    sample = "Date,10 Yr\n08/28/2026,4.73\n"

    try:
        parse_par_yield_csv(sample, "99y")
    except ValueError as exc:
        assert "unsupported Treasury tenor" in str(exc)
    else:
        raise AssertionError("expected ValueError")
