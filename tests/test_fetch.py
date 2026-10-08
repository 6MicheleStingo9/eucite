"""Acquisition: what is requested, what is written, and when.

The definition of done of S1 is asserted here: a second fetch makes no request
and writes nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eucite.cache import ObjectStore, SourceLock, sha256_hex
from eucite.canonical import CANONICAL_VERSION
from eucite.fetch import FetchReport, Outcome, fetch_sources
from eucite.sources import Manifestation, SourceKey, all_sources
from tests.doubles import (
    FakeCellar,
    formex_act,
    formex_bundle,
    formex_zip,
    make_client,
    payload_for,
)

Snapshot = dict[str, tuple[int, int]]


def snapshot(root: Path) -> Snapshot:
    """Every file under ``root`` with its size and modification time."""
    return {
        str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def run(
    cellar: FakeCellar, root: Path, *, refresh: bool = False, frozen: bool = False
) -> FetchReport:
    lock_path = root / "sources.lock.json"
    report = fetch_sources(
        all_sources(),
        client=make_client(cellar),
        store=ObjectStore(root / "cache"),
        lock=SourceLock.load(lock_path),
        refresh=refresh,
        frozen=frozen,
    )
    if not frozen:
        report.lock.save(lock_path)
    return report


def empty_cache(root: Path) -> None:
    for p in sorted((root / "cache").rglob("*"), reverse=True):
        if p.is_file():
            p.chmod(0o644)
            p.unlink()


def outcomes(report: FetchReport) -> set[Outcome]:
    return {r.outcome for r in report.results}


@pytest.fixture
def served(cellar: FakeCellar) -> FakeCellar:
    cellar.serve_all()
    return cellar


def test_first_fetch_acquires_every_source(served: FakeCellar, tmp_path: Path) -> None:
    report = run(served, tmp_path)

    assert outcomes(report) == {Outcome.FETCHED}
    assert len(served.requests) == 12
    lock = SourceLock.load(tmp_path / "sources.lock.json")
    assert [e.key for e in lock.entries] == all_sources()
    assert all(ObjectStore(tmp_path / "cache").has(e.sha256) for e in lock.entries)


def test_second_fetch_makes_no_request_and_writes_nothing(
    served: FakeCellar, tmp_path: Path
) -> None:
    """Definition of done of S1."""
    run(served, tmp_path)
    before, requests_before = snapshot(tmp_path), len(served.requests)

    report = run(served, tmp_path)

    assert outcomes(report) == {Outcome.CACHED}
    assert report.requests == 0
    assert len(served.requests) == requests_before
    assert snapshot(tmp_path) == before


def test_refresh_with_identical_bytes_writes_nothing(served: FakeCellar, tmp_path: Path) -> None:
    run(served, tmp_path)
    before = snapshot(tmp_path)

    report = run(served, tmp_path, refresh=True)

    assert outcomes(report) == {Outcome.VERIFIED}
    assert report.requests == 12
    assert snapshot(tmp_path) == before


def test_refresh_with_new_bytes_moves_the_lock_and_keeps_the_old_object(
    served: FakeCellar, tmp_path: Path
) -> None:
    run(served, tmp_path)
    changed = SourceKey("02024R1689-20260727", "ita", Manifestation.XHTML)
    old = SourceLock.load(tmp_path / "sources.lock.json").get(changed)
    served.serve(changed, payload_for(changed, revision=1))

    report = run(served, tmp_path, refresh=True)

    by_key = {r.key: r.outcome for r in report.results}
    assert by_key.pop(changed) is Outcome.CHANGED
    assert set(by_key.values()) == {Outcome.VERIFIED}
    new = SourceLock.load(tmp_path / "sources.lock.json").get(changed)
    assert old is not None and new is not None
    assert new.sha256 != old.sha256
    assert ObjectStore(tmp_path / "cache").has(old.sha256)


def test_fresh_clone_restores_the_cache_from_the_lock(served: FakeCellar, tmp_path: Path) -> None:
    """The lock is committed, the cache is not: a clone starts with a lock only."""
    run(served, tmp_path)
    lock_before = (tmp_path / "sources.lock.json").read_text()
    empty_cache(tmp_path)

    report = run(served, tmp_path)

    assert outcomes(report) == {Outcome.VERIFIED}
    assert (tmp_path / "sources.lock.json").read_text() == lock_before


def test_frozen_fetch_restores_exactly_the_locked_sources(
    served: FakeCellar, tmp_path: Path
) -> None:
    run(served, tmp_path)
    empty_cache(tmp_path)

    report = run(served, tmp_path, frozen=True)

    assert outcomes(report) == {Outcome.VERIFIED}
    lock = SourceLock.load(tmp_path / "sources.lock.json")
    assert all(ObjectStore(tmp_path / "cache").has(e.sha256) for e in lock.entries)


def test_frozen_fetch_fails_on_bytes_that_differ_from_the_lock(
    served: FakeCellar, tmp_path: Path
) -> None:
    run(served, tmp_path)
    empty_cache(tmp_path)
    changed = SourceKey("32026R1744", "eng", Manifestation.FORMEX)
    served.serve(changed, payload_for(changed, revision=1))
    lock_before = (tmp_path / "sources.lock.json").read_text()

    report = run(served, tmp_path, frozen=True)

    [failure] = report.failed
    assert failure.key == changed
    assert "differ from the lock" in (failure.error or "")
    assert report.lock.get(changed) == SourceLock.load(tmp_path / "sources.lock.json").get(changed)
    assert (tmp_path / "sources.lock.json").read_text() == lock_before
    store = ObjectStore(tmp_path / "cache")
    assert not store.has(sha256_hex(payload_for(changed, revision=1)))


def test_frozen_fetch_does_not_request_what_the_lock_lacks(
    served: FakeCellar, tmp_path: Path
) -> None:
    report = run(served, tmp_path, frozen=True)

    assert outcomes(report) == {Outcome.FAILED}
    assert served.requests == []
    assert all("not in the lock" in (r.error or "") for r in report.results)


def test_one_failure_does_not_stop_the_others(cellar: FakeCellar, tmp_path: Path) -> None:
    cellar.serve_all()
    missing = SourceKey("32026R1744", "eng", Manifestation.FORMEX)
    del cellar.payloads[(missing.celex, missing.accept, missing.lang)]

    report = run(cellar, tmp_path)

    (failure,) = report.failed
    assert failure.key == missing
    assert failure.error is not None and "404" in failure.error
    assert len(SourceLock.load(tmp_path / "sources.lock.json").entries) == 11


# -- canonical form (ADR-0006) -------------------------------------------------------

CONSOLIDATED = SourceKey("02024R1689-20260727", "ita", Manifestation.FORMEX)


def test_every_entry_records_its_canonical_hash(served: FakeCellar, tmp_path: Path) -> None:
    run(served, tmp_path)
    for entry in SourceLock.load(tmp_path / "sources.lock.json").entries:
        assert entry.canonical_sha256 is not None
        assert entry.canonical_version == CANONICAL_VERSION


def test_canonical_hashes_are_filled_in_without_network(served: FakeCellar, tmp_path: Path) -> None:
    """A lock written before the canonical form existed is completed from the cache."""
    run(served, tmp_path)
    lock_path = tmp_path / "sources.lock.json"
    old = SourceLock.load(lock_path)
    stripped = SourceLock(
        entries=tuple(
            e.model_copy(update={"canonical_sha256": None, "canonical_version": None})
            for e in old.entries
        )
    )
    stripped.save(lock_path)
    requests = len(served.requests)

    report = run(served, tmp_path)

    assert report.requests == 0 and len(served.requests) == requests
    assert SourceLock.load(lock_path) == old


def test_a_change_of_presentation_only_is_recognised(served: FakeCellar, tmp_path: Path) -> None:
    act = formex_act("<ENACTING.TERMS><P>same text</P></ENACTING.TERMS>")
    served.serve(CONSOLIDATED, formex_bundle(act))
    run(served, tmp_path)
    served.serve(CONSOLIDATED, formex_bundle(act, date_time=(2027, 1, 1, 0, 0, 0)))

    report = run(served, tmp_path, refresh=True)

    (result,) = [r for r in report.results if r.key == CONSOLIDATED]
    assert result.outcome is Outcome.CHANGED
    assert result.presentation_only is True


def test_a_change_of_content_is_not_presentation(served: FakeCellar, tmp_path: Path) -> None:
    served.serve(CONSOLIDATED, formex_bundle(formex_act("<P>old text</P>")))
    run(served, tmp_path)
    served.serve(CONSOLIDATED, formex_bundle(formex_act("<P>new text</P>")))

    report = run(served, tmp_path, refresh=True)

    (result,) = [r for r in report.results if r.key == CONSOLIDATED]
    assert result.outcome is Outcome.CHANGED
    assert result.presentation_only is False


def test_a_payload_that_cannot_be_canonicalised_is_a_failure(
    served: FakeCellar, tmp_path: Path
) -> None:
    """A zip that passes the envelope check but has no usable descriptor."""
    served.serve(CONSOLIDATED, formex_zip())

    report = run(served, tmp_path)

    (failure,) = report.failed
    assert failure.key == CONSOLIDATED
    assert failure.error is not None and "canonicalise" in failure.error
