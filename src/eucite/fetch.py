"""Acquisition (L0): bring every source into the object store and the lock.

A source already in the lock, whose object is in the store, is not requested
again unless a refresh is asked for. A refresh that returns identical bytes
writes nothing. A refresh that returns different bytes keeps the old object and
moves the lock to the new one: the lock diff is the record of the change.

Every entry also records the hash of the payload's canonical form (ADR-0006).
When a refresh brings different bytes with the same canonical hash, the change
is reported as presentation only. Deciding what that means for the build is the
job of drift detection (S9).
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from lxml import etree

from eucite.cache import LockEntry, ObjectStore, SourceLock, lock_entry
from eucite.canonical import CANONICAL_VERSION, canonicalize
from eucite.cellar import CellarClient, CellarError
from eucite.formex import BundleError
from eucite.sources import SourceKey

__all__ = ["FetchReport", "FetchResult", "Outcome", "fetch_sources"]


class Outcome(StrEnum):
    CACHED = "cached"
    """In the lock and in the store: no request made."""
    FETCHED = "fetched"
    """Not in the lock before: downloaded and recorded."""
    VERIFIED = "verified"
    """Downloaded again; identical to the locked bytes."""
    CHANGED = "changed"
    """Downloaded again; different from the locked bytes. The lock moved."""
    FAILED = "failed"


@dataclass(frozen=True)
class FetchResult:
    key: SourceKey
    outcome: Outcome
    entry: LockEntry | None = None
    error: str | None = None
    presentation_only: bool | None = None
    """For ``CHANGED``: whether the canonical form is unchanged."""


@dataclass(frozen=True)
class FetchReport:
    lock: SourceLock
    results: tuple[FetchResult, ...]

    @property
    def failed(self) -> tuple[FetchResult, ...]:
        return tuple(r for r in self.results if r.outcome is Outcome.FAILED)

    @property
    def requests(self) -> int:
        return sum(1 for r in self.results if r.outcome is not Outcome.CACHED)


class CanonicalisationError(Exception):
    pass


def _canonical(key: SourceKey, content: bytes) -> str:
    try:
        return canonicalize(key.manifestation, content).sha256
    except (BundleError, ValueError, SyntaxError, etree.LxmlError, zipfile.BadZipFile) as exc:
        raise CanonicalisationError(f"{key}: cannot canonicalise: {exc}") from exc


def _with_canonical(entry: LockEntry, store: ObjectStore) -> LockEntry:
    """Fill or refresh the canonical hash from the stored payload, without network."""
    if entry.canonical_sha256 is not None and entry.canonical_version == CANONICAL_VERSION:
        return entry
    digest = _canonical(entry.key, store.get(entry.sha256))
    return entry.model_copy(
        update={"canonical_sha256": digest, "canonical_version": CANONICAL_VERSION}
    )


def fetch_sources(
    keys: Iterable[SourceKey],
    *,
    client: CellarClient,
    store: ObjectStore,
    lock: SourceLock,
    refresh: bool = False,
) -> FetchReport:
    """Acquire ``keys``; return the updated lock and what happened to each key.

    A failure on one source does not stop the others: their results are still
    worth keeping, and the report lists every failure.
    """
    results: list[FetchResult] = []
    for key in keys:
        current = lock.get(key)
        try:
            if current is not None and store.has(current.sha256) and not refresh:
                current = _with_canonical(current, store)
                lock = lock.with_entry(current)
                results.append(FetchResult(key, Outcome.CACHED, current))
                continue

            payload = client.fetch(key)
            canonical = _canonical(key, payload.content)
        except (CellarError, CanonicalisationError) as exc:
            results.append(FetchResult(key, Outcome.FAILED, current, str(exc)))
            continue

        digest, _ = store.put(payload.content)
        if current is not None and current.sha256 == digest:
            current = _with_canonical(current, store)
            lock = lock.with_entry(current)
            results.append(FetchResult(key, Outcome.VERIFIED, current))
            continue

        entry = lock_entry(
            key,
            request_url=payload.request_url,
            final_url=payload.final_url,
            content_type=payload.content_type,
            sha256=digest,
            size=len(payload.content),
            retrieved_at=payload.retrieved_at,
            etag=payload.etag,
            last_modified=payload.last_modified,
            canonical_sha256=canonical,
            canonical_version=CANONICAL_VERSION,
        )
        lock = lock.with_entry(entry)
        if current is None:
            results.append(FetchResult(key, Outcome.FETCHED, entry))
        else:
            previous = _with_canonical(current, store) if store.has(current.sha256) else current
            same = previous.canonical_sha256 == canonical
            results.append(FetchResult(key, Outcome.CHANGED, entry, presentation_only=same))

    return FetchReport(lock=lock, results=tuple(results))
