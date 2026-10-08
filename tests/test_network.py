"""Checks against the real Cellar. Excluded by default; run with ``pytest -m network``.

They guard the two facts the acquisition layer is built on, because both can
change upstream without notice.
"""

from __future__ import annotations

import httpx
import pytest

from ai_act_corpus.cellar import CellarClient, celex_url
from ai_act_corpus.sources import Manifestation, SourceKey

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
