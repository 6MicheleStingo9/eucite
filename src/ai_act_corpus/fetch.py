"""Acquisition (L0): bring every source into the object store and the lock.

A source already in the lock, whose object is in the store, is not requested
again unless a refresh is asked for. A refresh that returns identical bytes
writes nothing. A refresh that returns different bytes keeps the old object and
moves the lock to the new one: the lock diff is the record of the change.

Whether a byte change is a change in the law is not decided here. That needs the
canonical form (S2) and is the job of drift detection (S9).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ai_act_corpus.cache import LockEntry, ObjectStore, SourceLock, lock_entry
from ai_act_corpus.cellar import CellarClient, CellarError
from ai_act_corpus.sources import SourceKey

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
        if current is not None and store.has(current.sha256) and not refresh:
            results.append(FetchResult(key, Outcome.CACHED, current))
            continue

        try:
            payload = client.fetch(key)
        except CellarError as exc:
            results.append(FetchResult(key, Outcome.FAILED, current, str(exc)))
            continue

        digest, _ = store.put(payload.content)
        if current is not None and current.sha256 == digest:
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
        )
        lock = lock.with_entry(entry)
        outcome = Outcome.FETCHED if current is None else Outcome.CHANGED
        results.append(FetchResult(key, outcome, entry))

    return FetchReport(lock=lock, results=tuple(results))
