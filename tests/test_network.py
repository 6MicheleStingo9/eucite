"""Checks against the real Cellar. Excluded by default; run with ``pytest -m network``.

They guard the two facts the acquisition layer is built on, because both can
change upstream without notice.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from eucite.cache import LockEntry, SourceLock
from eucite.canonical import canonicalize
from eucite.cellar import CellarClient, celex_url
from eucite.sources import Manifestation, SourceKey

LOCK = SourceLock.load(Path(__file__).resolve().parent.parent / "sources.lock.json")

pytestmark = pytest.mark.network


def test_formex_is_negotiated_as_a_zip_bundle() -> None:
    with CellarClient() as client:
        payload = client.fetch(SourceKey("32026R1744", "eng", Manifestation.FORMEX))
    assert "/resource/cellar/" in payload.final_url


def test_single_document_formex_request_still_fails() -> None:
    """The request that misled the first spike. If this starts returning 200,
    ADR-0001 should be reviewed."""
    response = httpx.get(
        celex_url("32026R1744"),
        headers={"Accept": "application/xml;type=fmx4", "Accept-Language": "eng"},
        follow_redirects=True,
        timeout=60,
    )
    assert response.status_code == 404


@pytest.mark.parametrize("entry", LOCK.entries, ids=lambda e: str(e.key))
def test_what_cellar_serves_today_matches_the_locked_canonical_form(entry: LockEntry) -> None:
    """Drift detection in miniature: the committed canonical hash must still hold."""
    with CellarClient() as client:
        payload = client.fetch(entry.key)
    assert canonicalize(entry.manifestation, payload.content).sha256 == entry.canonical_sha256
