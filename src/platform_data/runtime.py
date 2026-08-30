from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_retry_session(
    *,
    total_retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> requests.Session:
    """Return a requests session with finite retries for transient failures."""

    retry = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        status=total_retries,
        allowed_methods=frozenset({"GET", "HEAD"}),
        status_forcelist=status_forcelist,
        backoff_factor=backoff_factor,
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def is_observation_stale(observation_date: str, *, max_age_days: int, today: date | None = None) -> bool:
    """Return whether an ISO observation date exceeds a frequency-aware age threshold."""

    current = today or date.today()
    observed = date.fromisoformat(observation_date)
    return (current - observed).days > max_age_days


def preserve_volatile_fields_when_materially_unchanged(
    path: Path,
    payload: dict[str, Any],
    *,
    volatile_fields: tuple[str, ...] = ("retrievedAt",),
) -> None:
    """Preserve volatile metadata when all material fields are unchanged.

    This keeps scheduled refreshes from creating Git noise when the upstream
    observation set and status are unchanged.
    """

    if not path.exists():
        return
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    comparable_keys = set(payload) - set(volatile_fields)
    if not all(existing.get(key) == payload.get(key) for key in comparable_keys):
        return

    for field in volatile_fields:
        if field in existing:
            payload[field] = existing[field]
