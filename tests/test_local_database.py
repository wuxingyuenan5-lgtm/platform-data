from __future__ import annotations

import json
from pathlib import Path

import duckdb

from platform_data.local_database import sync_local_database


def test_sync_local_database_preserves_decimal_and_metadata(tmp_path: Path):
    path = tmp_path / "public/v1/macro/series/test_series.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "seriesId": "test_series",
                "label": "Test Series",
                "status": "ready",
                "unit": "percent",
                "frequency": "daily",
                "timezone": "UTC",
                "source": "test",
                "observationDate": "2026-09-02",
                "asOf": "2026-09-02",
                "retrievedAt": "2026-09-03T00:00:00Z",
                "isStale": False,
                "methodologyVersion": "test_v1",
                "qualityFlags": [],
                "rightsScope": "test",
                "observations": [{"date": "2026-09-02", "value": "1.234567890123"}],
            }
        ),
        encoding="utf-8",
    )

    result = sync_local_database(tmp_path)
    assert result["series"] == 1
    with duckdb.connect(result["database"], read_only=True) as connection:
        assert connection.execute("SELECT domain FROM series_metadata").fetchone() == ("macro",)
        assert str(connection.execute("SELECT value FROM observations").fetchone()[0]) == "1.234567890123"
