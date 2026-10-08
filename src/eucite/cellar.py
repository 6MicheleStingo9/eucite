"""Client for the Publications Office's Cellar repository.

Cellar serves every manifestation of a work behind one CELEX URI, chosen by
content negotiation. Two details make the difference between a working request
and a misleading one:

- ``Accept-Language`` is mandatory. Without it Cellar answers 400, which is easy
  to mistake for an unavailable format.
- A 404 means the manifestation does not exist *for that request*. The first
  feasibility spike concluded that Formex did not exist because it asked for the
  wrong media type (ADR-0001). This client therefore keeps "not available"
  (404) distinct from "malformed request" (400, 406).

The client validates what it receives before returning it: a response that
declares the wrong media type, or a Formex bundle that is not a well-formed zip,
is an error, never a payload.
"""

from __future__ import annotations

import io
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from types import TracebackType
from urllib.parse import quote

import httpx

from eucite import __version__
from eucite.sources import Manifestation, SourceKey

__all__ = [
    "CELLAR_CELEX_BASE",
    "CellarClient",
    "CellarError",
    "NegotiationError",
    "NotAvailableError",
    "Payload",
    "RetryPolicy",
    "TransientError",
    "UnexpectedContentError",
    "validate_payload",
]

CELLAR_CELEX_BASE = "https://publications.europa.eu/resource/celex/"
USER_AGENT = f"eucite/{__version__} (python-httpx)"

# Limits for a Formex bundle. The largest one in the corpus (the base act) holds
# 16 files and about 0.8 MB uncompressed; these bounds leave ample room while
# refusing anything that is clearly not a Formex bundle.
MAX_BUNDLE_MEMBERS = 500
MAX_BUNDLE_UNCOMPRESSED = 100 * 1024 * 1024

_RETRYABLE = frozenset({429, 500, 502, 503, 504})


class CellarError(Exception):
    """Base class for every acquisition failure."""


class NotAvailableError(CellarError):
    """Cellar has no such manifestation for this work and language (404)."""


class NegotiationError(CellarError):
    """Cellar rejected the request itself (400, 406): a bug in the request."""


class TransientError(CellarError):
    """Retries were exhausted on errors that may succeed later."""


class UnexpectedContentError(CellarError):
    """The response was successful but is not what was asked for."""


@dataclass(frozen=True)
class RetryPolicy:
    """How long to keep trying.

    ``attempts`` bounds the retries on transient failures (timeouts, 429, 5xx).
    ``accepted_polls`` separately bounds the polls while Cellar answers 202,
    which it can do while it assembles a bundle.
    """

    attempts: int = 5
    base_delay: float = 2.0
    max_delay: float = 60.0
    accepted_polls: int = 10

    def delay(self, attempt: int, retry_after: float | None = None) -> float:
        """Seconds to wait before the next try; ``attempt`` counts from 1."""
        if retry_after is not None:
            return min(retry_after, self.max_delay)
        return float(min(self.base_delay * 2 ** (attempt - 1), self.max_delay))


@dataclass(frozen=True)
class Payload:
    """A validated response, with what is needed to record its provenance."""

    key: SourceKey
    request_url: str
    final_url: str
    content_type: str
    content: bytes
    retrieved_at: datetime
    etag: str | None = None
    last_modified: str | None = None


def celex_url(celex: str) -> str:
    # Corrigenda have parentheses in their CELEX number ("32024R1689R(01)").
    return CELLAR_CELEX_BASE + quote(celex, safe="")


def _media_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None  # an HTTP date: fall back to the policy's own backoff


def validate_payload(
    manifestation: Manifestation,
    content: bytes,
    *,
    max_members: int = MAX_BUNDLE_MEMBERS,
    max_uncompressed: int = MAX_BUNDLE_UNCOMPRESSED,
) -> None:
    """Raise :class:`UnexpectedContentError` unless ``content`` is plausible.

    This is a sanity check on the envelope, not parsing. A Formex bundle must be
    a zip of XML files with safe relative names, a descriptor, and a bounded
    uncompressed size; nothing is extracted to disk. An XHTML document must be a
    non-empty HTML document.
    """
    if not content:
        raise UnexpectedContentError(f"empty {manifestation} payload")

    if manifestation is Manifestation.XHTML:
        head = content[:4096].decode("utf-8", errors="replace").lower()
        if "<html" not in head:
            raise UnexpectedContentError("XHTML payload does not contain an <html> element")
        return

    try:
        bundle = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise UnexpectedContentError(f"Formex payload is not a zip: {exc}") from exc
    with bundle:
        members = bundle.infolist()
        if not members:
            raise UnexpectedContentError("Formex bundle is empty")
        if len(members) > max_members:
            raise UnexpectedContentError(f"Formex bundle has {len(members)} members")
        if sum(m.file_size for m in members) > max_uncompressed:
            raise UnexpectedContentError("Formex bundle exceeds the uncompressed size limit")
        for m in members:
            path = PurePosixPath(m.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in m.filename:
                raise UnexpectedContentError(f"unsafe member name in Formex bundle: {m.filename!r}")
            if m.is_dir() or path.suffix != ".xml":
                raise UnexpectedContentError(f"unexpected member in Formex bundle: {m.filename!r}")
        if not any(".doc." in m.filename for m in members):
            raise UnexpectedContentError("Formex bundle has no descriptor (*.doc.xml)")


class CellarClient:
    """Fetches manifestations from Cellar by content negotiation."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        retry: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = client or httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0))
        self._client.follow_redirects = True
        self._client.headers["User-Agent"] = USER_AGENT
        self._retry = retry or RetryPolicy()
        self._sleep = sleep
        self._clock = clock

    def __enter__(self) -> CellarClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fetch(self, key: SourceKey) -> Payload:
        url = celex_url(key.celex)
        headers = {"Accept": key.accept, "Accept-Language": key.lang}
        failures = 0
        polls = 0
        while True:
            try:
                response = self._client.get(url, headers=headers)
            except httpx.TransportError as exc:
                failures += 1
                if failures >= self._retry.attempts:
                    raise TransientError(f"{key}: {failures} attempts failed: {exc}") from exc
                self._sleep(self._retry.delay(failures))
                continue

            status = response.status_code
            if status == 200:
                return self._accept(key, url, response)
            if status == 202:
                polls += 1
                if polls > self._retry.accepted_polls:
                    raise TransientError(f"{key}: still 202 after {polls - 1} polls")
                self._sleep(self._retry.delay(polls, _retry_after(response)))
                continue
            if status == 404:
                raise NotAvailableError(f"{key}: Cellar has no such manifestation (404)")
            if status in (400, 406):
                raise NegotiationError(f"{key}: Cellar rejected the request ({status})")
            if status in _RETRYABLE:
                failures += 1
                if failures >= self._retry.attempts:
                    raise TransientError(f"{key}: {failures} attempts failed, last {status}")
                self._sleep(self._retry.delay(failures, _retry_after(response)))
                continue
            raise CellarError(f"{key}: unexpected HTTP status {status}")

    def _accept(self, key: SourceKey, url: str, response: httpx.Response) -> Payload:
        content_type = response.headers.get("Content-Type", "")
        if _media_type(content_type) != key.manifestation.media_type:
            raise UnexpectedContentError(
                f"{key}: expected {key.manifestation.media_type}, got {content_type!r}"
            )
        content = response.content
        try:
            validate_payload(key.manifestation, content)
        except UnexpectedContentError as exc:
            raise UnexpectedContentError(f"{key}: {exc}") from exc
        return Payload(
            key=key,
            request_url=url,
            final_url=str(response.url),
            content_type=content_type,
            content=content,
            retrieved_at=self._clock(),
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )
