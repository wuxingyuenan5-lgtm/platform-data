import json
from pathlib import Path

from platform_data.pipelines.commodity_dashboard import build_commodity_dashboard


def test_commodity_dashboard_groups_net_and_percentile_separately(tmp_path: Path):
    source = Path("public/v1/commodity/series/cftc_gold_managed_money_net.json")
    target = tmp_path / source
    target.parent.mkdir(parents=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result = build_commodity_dashboard(root=tmp_path)
    document = json.loads(
        (tmp_path / "public/v1/commodity/dashboard.json").read_text(encoding="utf-8")
    )

    assert result["series"] == 1
    assert (
        document["groups"]["cftcGoldNet"][0]["seriesId"]
        == "cftc_gold_managed_money_net"
    )
    assert document["groups"]["cftcGoldPercentile"] == []
