"""The Cellar client: negotiation, redirects, retries, and what it refuses."""

from __future__ import annotations

import httpx
import pytest

from ai_act_corpus.cellar import (
    CellarError,
    NegotiationError,
    NotAvailableError,
    RetryPolicy,
    TransientError,
    UnexpectedContentError,
    celex_url,
    validate_payload,
)
from ai_act_corpus.sources import Manifestation, SourceKey
from tests.doubles import FIXED_NOW, FakeCellar, formex_zip, make_client, xhtml

FORMEX = SourceKey("32026R1744", "ita", Manifestation.FORMEX)
XHTML = SourceKey("32026R1744", "ita", Manifestation.XHTML)


def ok(content: bytes, media_type: str = "application/zip;charset=UTF-8") -> httpx.Response:
    return httpx.Response(200, content=content, headers={"Content-Type": media_type})


# -- negotiation ----------------------------------------------------------------


def test_every_request_carries_both_negotiation_headers(cellar: FakeCellar) -> None:
    """Without Accept-Language Cellar answers 400, easily mistaken for absence."""
    cellar.serve(FORMEX, formex_zip())
    make_client(cellar).fetch(FORMEX)

    (request,) = cellar.requests
    assert request.headers["Accept"] == "application/zip;mtype=fmx4"
    assert request.headers["Accept-Language"] == "ita"
    assert request.headers["User-Agent"].startswith("ai-act-corpus/")


def test_corrigendum_celex_is_percent_encoded() -> None:
    assert celex_url("32024R1689R(01)").endswith("/celex/32024R1689R%2801%29")


def test_redirect_to_the_manifestation_is_followed_and_recorded() -> None:
    manifestation_url = "http://publications.europa.eu/resource/cellar/b459c07f.0006.02/zip"

    def handler(request: httpx.Request) -> httpx.Response:
        if "/resource/celex/" in request.url.path:
            return httpx.Response(303, headers={"Location": manifestation_url})
        return ok(formex_zip())

    payload = make_client(handler).fetch(FORMEX)
    assert payload.request_url == celex_url("32026R1744")
    assert payload.final_url == manifestation_url
    assert payload.retrieved_at == FIXED_NOW


# -- waiting and retrying -------------------------------------------------------


def test_polls_while_cellar_prepares_the_bundle(cellar: FakeCellar, sleeps: list[float]) -> None:
    cellar.scripted = [
        httpx.Response(202, headers={"Retry-After": "3"}),
        httpx.Response(202),
        ok(formex_zip()),
    ]
    make_client(cellar, sleeps=sleeps).fetch(FORMEX)
    assert sleeps == [3.0, 4.0]  # Retry-After first, then the policy's backoff
    assert len(cellar.requests) == 3


def test_gives_up_when_the_bundle_never_arrives(cellar: FakeCellar) -> None:
    cellar.scripted = [httpx.Response(202) for _ in range(10)]
    client = make_client(cellar, retry=RetryPolicy(accepted_polls=2))
    with pytest.raises(TransientError, match="202"):
        client.fetch(FORMEX)
    assert len(cellar.requests) == 3


def test_retries_transient_statuses_honouring_retry_after(
    cellar: FakeCellar, sleeps: list[float]
) -> None:
    cellar.scripted = [
        httpx.Response(503),
        httpx.Response(429, headers={"Retry-After": "7"}),
        ok(formex_zip()),
    ]
    make_client(cellar, sleeps=sleeps).fetch(FORMEX)
    assert sleeps == [2.0, 7.0]


def test_retries_transport_errors(cellar: FakeCellar, sleeps: list[float]) -> None:
    cellar.scripted = [httpx.ConnectError("connection reset"), ok(formex_zip())]
    make_client(cellar, sleeps=sleeps).fetch(FORMEX)
    assert len(cellar.requests) == 2
    assert sleeps == [2.0]


def test_gives_up_after_the_configured_attempts(cellar: FakeCellar, sleeps: list[float]) -> None:
    cellar.scripted = [httpx.Response(503) for _ in range(10)]
    client = make_client(cellar, sleeps=sleeps, retry=RetryPolicy(attempts=3))
    with pytest.raises(TransientError, match="3 attempts"):
        client.fetch(FORMEX)
    assert len(cellar.requests) == 3
    assert sleeps == [2.0, 4.0]


def test_backoff_is_capped() -> None:
    policy = RetryPolicy(base_delay=2.0, max_delay=10.0)
    assert [policy.delay(n) for n in (1, 2, 3, 4)] == [2.0, 4.0, 8.0, 10.0]
    assert policy.delay(1, retry_after=3600) == 10.0


# -- what is not retried --------------------------------------------------------


def test_404_means_not_available_and_is_not_retried(cellar: FakeCellar) -> None:
    with pytest.raises(NotAvailableError):
        make_client(cellar).fetch(FORMEX)
    assert len(cellar.requests) == 1


@pytest.mark.parametrize("status", [400, 406])
def test_malformed_request_is_a_distinct_error(cellar: FakeCellar, status: int) -> None:
    cellar.scripted = [httpx.Response(status)]
    with pytest.raises(NegotiationError):
        make_client(cellar).fetch(FORMEX)
    assert len(cellar.requests) == 1


def test_unexpected_status_is_an_error(cellar: FakeCellar) -> None:
    cellar.scripted = [httpx.Response(418)]
    with pytest.raises(CellarError, match="418"):
        make_client(cellar).fetch(FORMEX)


def test_wrong_media_type_is_refused(cellar: FakeCellar) -> None:
    """A 200 carrying an HTML error page is not a payload."""
    cellar.scripted = [ok(b"<html>maintenance</html>", "text/html")]
    with pytest.raises(UnexpectedContentError, match="application/zip"):
        make_client(cellar).fetch(FORMEX)


def test_cellar_validators_are_recorded(cellar: FakeCellar) -> None:
    headers = {
        "Content-Type": "application/zip",
        "ETag": '"Czp-20260724032420040"',
        "Last-Modified": "Fri, 24 Jul 2026 01:24:20 GMT",
    }
    cellar.scripted = [httpx.Response(200, content=formex_zip(), headers=headers)]
    payload = make_client(cellar).fetch(FORMEX)
    assert payload.etag == '"Czp-20260724032420040"'
    assert payload.last_modified == "Fri, 24 Jul 2026 01:24:20 GMT"


def test_xhtml_payload_is_accepted(cellar: FakeCellar) -> None:
    cellar.serve(XHTML, xhtml('<p class="modref">▼M1</p>'))
    payload = make_client(cellar).fetch(XHTML)
    assert payload.content_type.startswith("application/xhtml+xml")


# -- payload validation ---------------------------------------------------------


def test_a_well_formed_bundle_is_valid() -> None:
    validate_payload(Manifestation.FORMEX, formex_zip())


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"", "empty"),
        (b"PK not really a zip", "not a zip"),
        (formex_zip({}), "empty"),
        (formex_zip({"X.doc.xml": b"", "../escape.xml": b""}), "unsafe"),
        (formex_zip({"X.doc.xml": b"", "/abs.xml": b""}), "unsafe"),
        (formex_zip({"X.doc.xml": b"", "scan.pdf": b""}), "unexpected member"),
        (formex_zip({"X.0001.xml": b"<ACT/>"}), "descriptor"),
    ],
)
def test_malformed_bundles_are_refused(content: bytes, reason: str) -> None:
    with pytest.raises(UnexpectedContentError, match=reason):
        validate_payload(Manifestation.FORMEX, content)


def test_bundle_limits_are_enforced() -> None:
    bundle = formex_zip({"X.doc.xml": b"<DOC/>", "X.0001.xml": b"x" * 1000})
    with pytest.raises(UnexpectedContentError, match="members"):
        validate_payload(Manifestation.FORMEX, bundle, max_members=1)
    with pytest.raises(UnexpectedContentError, match="size limit"):
        validate_payload(Manifestation.FORMEX, bundle, max_uncompressed=100)


@pytest.mark.parametrize("content", [b"", b"plain text, not a document"])
def test_xhtml_without_a_document_is_refused(content: bytes) -> None:
    with pytest.raises(UnexpectedContentError):
        validate_payload(Manifestation.XHTML, content)
