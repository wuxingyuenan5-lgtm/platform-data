import json
from datetime import date

from platform_data.runtime import (
    build_retry_session,
    is_observation_stale,
    preserve_volatile_fields_when_materially_unchanged,
)


def test_retry_session_has_finite_retry_policy():
    session = build_retry_session(total_retries=2, backoff_factor=0.1)
    adapter = session.get_adapter("https://example.com")

    assert adapter.max_retries.total == 2
    assert adapter.max_retries.connect == 2
    assert adapter.max_retries.read == 2
    assert 429 in adapter.max_retries.status_forcelist
    assert 503 in adapter.max_retries.status_forcelist


def test_is_observation_stale_uses_explicit_threshold():
    today = date(2026, 8, 30)

    assert is_observation_stale("2026-08-23", max_age_days=7, today=today) is False
    assert is_observation_stale("2026-08-22", max_age_days=7, today=today) is True


def test_preserve_retrieved_at_when_material_payload_is_unchanged(tmp_path):
    path = tmp_path / "series.json"
    path.write_text(
        json.dumps(
            {
                "seriesId": "example",
                "status": "ready",
                "latestValue": 1.0,
                "retrievedAt": "2026-08-29T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    payload = {
        "seriesId": "example",
        "status": "ready",
        "latestValue": 1.0,
        "retrievedAt": "2026-08-30T00:00:00Z",
    }
    preserve_volatile_fields_when_materially_unchanged(path, payload)

    assert payload["retrievedAt"] == "2026-08-29T00:00:00Z"


def test_retrieved_at_changes_when_material_payload_changes(tmp_path):
    path = tmp_path / "series.json"
    path.write_text(
        json.dumps(
            {
                "seriesId": "example",
                "status": "ready",
                "latestValue": 1.0,
                "retrievedAt": "2026-08-29T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    payload = {
        "seriesId": "example",
        "status": "ready",
        "latestValue": 2.0,
        "retrievedAt": "2026-08-30T00:00:00Z",
    }
    preserve_volatile_fields_when_materially_unchanged(path, payload)

    assert payload["retrievedAt"] == "2026-08-30T00:00:00Z"
