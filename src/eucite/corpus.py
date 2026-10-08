"""Documents of the corpus, read from the cache the lock describes.

Parsing is a function of the locked bytes only: the same lock gives the same
documents, on any machine that has the objects (``eucite fetch --frozen``).
"""

from __future__ import annotations

from eucite.cache import ObjectStore, SourceLock
from eucite.nodes import Document, Provenance
from eucite.parse import parse_formex
from eucite.sources import Manifestation, SourceKey

__all__ = ["load_document", "locked_payload"]


def locked_payload(key: SourceKey, *, store: ObjectStore, lock: SourceLock) -> bytes:
    """The bytes the lock records for ``key``, verified against their hash."""
    entry = lock.get(key)
    if entry is None:
        raise KeyError(f"{key} is not in the lock")
    return store.get(entry.sha256)


def load_document(celex: str, language: str, *, store: ObjectStore, lock: SourceLock) -> Document:
    """Parse the locked Formex manifestation of a work in one language."""
    key = SourceKey(celex, language, Manifestation.FORMEX)
    content = locked_payload(key, store=store, lock=lock)
    entry = lock.get(key)
    assert entry is not None
    provenance = Provenance(
        source_work=entry.celex,
        manifestation=entry.manifestation.value,
        accept=entry.accept,
        accept_language=entry.lang,
        url=entry.final_url,
        retrieved_at=entry.retrieved_at,
        source_sha256=entry.sha256,
        canonical_sha256=entry.canonical_sha256,
        canonical_version=entry.canonical_version,
    )
    return parse_formex(content, work=celex, language=language, provenance=provenance)
