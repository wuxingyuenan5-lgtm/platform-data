import json
from pathlib import Path

from platform_data.pipelines.macro_dashboard import build_macro_dashboard


def test_macro_dashboard_builds_frozen_topic_groups(tmp_path: Path):
    source = Path("public/v1/macro/series/us_real_gdp_yoy.json")
    target = tmp_path / source
    target.parent.mkdir(parents=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result = build_macro_dashboard(root=tmp_path)
    document = json.loads((tmp_path / "public/v1/macro/dashboard.json").read_text(encoding="utf-8"))

    assert result["series"] == 1
    assert document["groups"]["growthProduction"][0]["seriesId"] == "us_real_gdp_yoy"
    assert "rateCorridor" in document["groups"]
