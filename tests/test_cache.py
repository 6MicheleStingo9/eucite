"""The object store is write-once; the lock is deterministic."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from eucite.cache import (
    CacheCorruptionError,
    LockEntry,
    ObjectStore,
    SourceLock,
    lock_entry,
    sha256_hex,
)
from eucite.sources import Manifestation, SourceKey
from tests.doubles import FIXED_NOW

KEY_A = SourceKey("32024R1689", "eng", Manifestation.FORMEX)
KEY_B = SourceKey("32024R1689", "ita", Manifestation.FORMEX)


def entry_for(key: SourceKey, content: bytes = b"payload", when: datetime = FIXED_NOW) -> LockEntry:
    return lock_entry(
        key,
        request_url="https://publications.europa.eu/resource/celex/32024R1689",
        final_url="http://publications.europa.eu/resource/cellar/x/zip",
        content_type="application/zip;charset=UTF-8",
        sha256=sha256_hex(content),
        size=len(content),
        retrieved_at=when,
    )


# -- object store ---------------------------------------------------------------


def test_objects_are_addressed_by_content(tmp_path: Path) -> None:
    store = ObjectStore(tmp_path)
    digest, written = store.put(b"payload")
    assert written
    assert store.path_for(digest) == tmp_path / "objects" / digest[:2] / digest
    assert store.get(digest) == b"payload"


def test_objects_are_written_once(tmp_path: Path) -> None:
    store = ObjectStore(tmp_path)
    digest, _ = store.put(b"payload")
    before = store.path_for(digest).stat().st_mtime_ns

    _, written = store.put(b"payload")
    assert not written
    assert store.path_for(digest).stat().st_mtime_ns == before


def test_objects_are_read_only(tmp_path: Path) -> None:
    store = ObjectStore(tmp_path)
    digest, _ = store.put(b"payload")
    assert store.path_for(digest).stat().st_mode & 0o222 == 0


def test_a_tampered_object_is_detected(tmp_path: Path) -> None:
    store = ObjectStore(tmp_path)
    digest, _ = store.put(b"payload")
    path = store.path_for(digest)
    path.chmod(0o644)
    path.write_bytes(b"tampered")

    with pytest.raises(CacheCorruptionError):
        store.get(digest)
    with pytest.raises(CacheCorruptionError):
        store.put(b"payload")


# -- lock -------------------------------------------------------------------------


def test_missing_lock_is_empty(tmp_path: Path) -> None:
    assert SourceLock.load(tmp_path / "absent.json").entries == ()


def test_entries_are_kept_sorted_and_unique_per_source() -> None:
    lock = SourceLock().with_entry(entry_for(KEY_B)).with_entry(entry_for(KEY_A))
    assert [e.key for e in lock.entries] == [KEY_A, KEY_B]

    replaced = lock.with_entry(entry_for(KEY_A, b"newer"))
    assert len(replaced.entries) == 2
    assert replaced.get(KEY_A) == entry_for(KEY_A, b"newer")


def test_lock_round_trips_and_serialises_time_in_utc(tmp_path: Path) -> None:
    path = tmp_path / "sources.lock.json"
    lock = SourceLock().with_entry(entry_for(KEY_A))
    assert lock.save(path)

    assert SourceLock.load(path) == lock
    (raw,) = json.loads(path.read_text())["entries"]
    assert raw["retrieved_at"] == "2026-10-08T10:00:00Z"
    assert path.read_text().endswith("\n")


def test_unchanged_lock_is_not_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "sources.lock.json"
    lock = SourceLock().with_entry(entry_for(KEY_A))
    lock.save(path)
    before = path.stat().st_mtime_ns

    assert not SourceLock.load(path).save(path)
    assert path.stat().st_mtime_ns == before


def test_lock_refuses_malformed_entries() -> None:
    with pytest.raises(ValidationError):
        LockEntry.model_validate({**entry_for(KEY_A).model_dump(), "sha256": "not-a-hash"})
    with pytest.raises(ValidationError):
        entry_for(KEY_A, when=datetime(2026, 10, 8, 10, 0))  # naive time
