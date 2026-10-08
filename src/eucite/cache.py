"""Immutable payload cache and the source lock (ADR-0010).

Two artefacts with different lives:

- The **object store** keeps every payload ever retrieved, addressed by its
  SHA-256. An object is written once, atomically, and never overwritten. It is
  not committed: it holds megabytes of EUR-Lex payloads.
- The **lock** records, for each source, which object is current and where it
  came from. It is small, deterministic and committed, so that a change in what
  Cellar serves shows up as a reviewable diff.

The first feasibility spike counted 306 structural identifiers in a document
that Cellar regenerated three days later; the count is now 284, and the
difference cannot be explained because the bytes were not kept. The store
exists so that this cannot happen again.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from eucite.sources import Manifestation, SourceKey

__all__ = [
    "CacheCorruptionError",
    "LockEntry",
    "ObjectStore",
    "SourceLock",
    "lock_entry",
    "sha256_hex",
]


class CacheCorruptionError(Exception):
    """A stored object no longer matches the hash it is stored under."""


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class ObjectStore:
    """Content-addressed, write-once storage under ``root/objects``."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, sha256: str) -> Path:
        return self.root / "objects" / sha256[:2] / sha256

    def has(self, sha256: str) -> bool:
        return self.path_for(sha256).is_file()

    def put(self, content: bytes) -> tuple[str, bool]:
        """Store ``content``; return its hash and whether anything was written."""
        digest = sha256_hex(content)
        path = self.path_for(digest)
        if path.is_file():
            self.get(digest)  # verifies the existing object
            return digest, False
        _atomic_write(path, content)
        # Read-only is a signal, not a guarantee: the store never rewrites.
        path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        return digest, True

    def get(self, sha256: str) -> bytes:
        content = self.path_for(sha256).read_bytes()
        if sha256_hex(content) != sha256:
            raise CacheCorruptionError(f"object {sha256} does not match its hash")
        return content


class LockEntry(BaseModel):
    """Where the current payload of one source came from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    celex: str
    lang: str
    manifestation: Manifestation
    accept: str
    request_url: str
    final_url: str
    content_type: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)
    retrieved_at: AwareDatetime
    """When these exact bytes were first retrieved. Re-downloading identical
    bytes does not change it."""
    etag: str | None = None
    last_modified: str | None = None
    """Cellar's own validators for the manifestation, as served: when Cellar last
    regenerated it, and a token for conditional requests."""

    @property
    def key(self) -> SourceKey:
        return SourceKey(self.celex, self.lang, self.manifestation)


class SourceLock(BaseModel):
    """The current payload of every source, serialised deterministically."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lock_version: Literal[1] = 1
    entries: tuple[LockEntry, ...] = ()

    def get(self, key: SourceKey) -> LockEntry | None:
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None

    def with_entry(self, entry: LockEntry) -> SourceLock:
        others = [e for e in self.entries if e.key != entry.key]
        return SourceLock(entries=tuple(sorted([*others, entry], key=lambda e: e.key)))

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def load(cls, path: Path) -> SourceLock:
        if not path.exists():
            return cls()
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, path: Path) -> bool:
        """Write the lock if its content changed; return whether it was written."""
        text = self.to_json()
        if path.exists() and path.read_text(encoding="utf-8") == text:
            return False
        _atomic_write(path, text.encode("utf-8"))
        return True


def lock_entry(
    key: SourceKey,
    *,
    request_url: str,
    final_url: str,
    content_type: str,
    sha256: str,
    size: int,
    retrieved_at: datetime,
    etag: str | None = None,
    last_modified: str | None = None,
) -> LockEntry:
    return LockEntry(
        celex=key.celex,
        lang=key.lang,
        manifestation=key.manifestation,
        accept=key.accept,
        request_url=request_url,
        final_url=final_url,
        content_type=content_type,
        sha256=sha256,
        size=size,
        retrieved_at=retrieved_at,
        etag=etag,
        last_modified=last_modified,
    )
