from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import duckdb


def sync_local_database(root: Path) -> dict[str, object]:
    """Atomically rebuild the queryable DuckDB mirror from canonical serving JSON."""

    serving_root = root / "public" / "v1"
    documents = sorted(serving_root.glob("*/series/*.json"))
    if not documents:
        raise RuntimeError(f"no canonical series found below {serving_root}")

    database_path = root / "hedge_board.duckdb"
    staging_path = root / "hedge_board.staging.duckdb"
    if staging_path.exists():
        staging_path.unlink()

    connection = duckdb.connect(str(staging_path))
    try:
        connection.execute("BEGIN TRANSACTION")
        connection.execute(
            """
            CREATE TABLE series_metadata (
                series_id VARCHAR PRIMARY KEY,
                domain VARCHAR NOT NULL,
                label VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                unit VARCHAR,
                frequency VARCHAR,
                timezone VARCHAR,
                source VARCHAR,
                source_series_id VARCHAR,
                source_url VARCHAR,
                observation_date DATE,
                as_of VARCHAR,
                retrieved_at TIMESTAMPTZ,
                is_stale BOOLEAN NOT NULL,
                methodology_version VARCHAR,
                quality_flags JSON,
                rights_scope VARCHAR,
                canonical_path VARCHAR NOT NULL
            );
            CREATE TABLE observations (
                series_id VARCHAR NOT NULL,
                observation_date DATE NOT NULL,
                value DECIMAL(38, 12),
                PRIMARY KEY (series_id, observation_date)
            );
            """
        )
        observation_count = 0
        for path in documents:
            payload = json.loads(path.read_text(encoding="utf-8"))
            series_id = str(payload["seriesId"])
            domain = path.parents[1].name
            connection.execute(
                """
                INSERT INTO series_metadata VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    series_id,
                    domain,
                    payload.get("label", series_id),
                    payload.get("status", "error"),
                    payload.get("unit"),
                    payload.get("frequency"),
                    payload.get("timezone"),
                    payload.get("source"),
                    payload.get("sourceSeriesId"),
                    payload.get("sourceUrl"),
                    payload.get("observationDate"),
                    payload.get("asOf"),
                    payload.get("retrievedAt"),
                    bool(payload.get("isStale", True)),
                    payload.get("methodologyVersion"),
                    json.dumps(payload.get("qualityFlags", []), ensure_ascii=False),
                    payload.get("rightsScope"),
                    str(path.relative_to(root)),
                ],
            )
            rows = [
                (
                    series_id,
                    item["date"],
                    Decimal(str(item["value"])) if item.get("value") is not None else None,
                )
                for item in payload.get("observations", [])
            ]
            if rows:
                connection.executemany("INSERT INTO observations VALUES (?, ?, ?)", rows)
                observation_count += len(rows)
        connection.execute(
            "CREATE INDEX observations_date_idx ON observations(observation_date)"
        )
        connection.execute("COMMIT")
        connection.execute("CHECKPOINT")
    finally:
        connection.close()

    staging_path.replace(database_path)
    return {
        "database": str(database_path),
        "series": len(documents),
        "observations": observation_count,
        "synced_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
