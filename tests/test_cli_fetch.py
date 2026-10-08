"""``eucite fetch`` end to end, against the offline Cellar double."""

from __future__ import annotations

from pathlib import Path

import pytest

import eucite.__main__ as cli
from eucite.cache import SourceLock
from tests.doubles import FakeCellar, make_client


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch, cellar: FakeCellar) -> FakeCellar:
    cellar.serve_all()
    monkeypatch.setattr(cli, "_make_client", lambda: make_client(cellar))
    return cellar


def fetch(tmp_path: Path, *extra: str) -> int:
    return cli.main(
        ["fetch", "--cache", str(tmp_path / "cache"), "--lock", str(tmp_path / "lock.json"), *extra]
    )


def test_fetch_then_fetch_again(
    offline: FakeCellar, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert fetch(tmp_path) == 0
    first = capsys.readouterr().out
    assert first.count("fetched") == 12
    assert "lock updated" in first

    assert fetch(tmp_path) == 0
    second = capsys.readouterr().out
    assert second.count("cached") == 12
    assert "0 requests" in second
    assert "lock unchanged" in second


def test_filters_select_a_subset(offline: FakeCellar, tmp_path: Path) -> None:
    assert fetch(tmp_path, "--work", "32026R1744", "--lang", "ita") == 0
    lock = SourceLock.load(tmp_path / "lock.json")
    assert {(e.celex, e.lang) for e in lock.entries} == {("32026R1744", "ita")}
    assert len(lock.entries) == 2


def test_failure_sets_the_exit_status(
    offline: FakeCellar, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    offline.payloads.clear()
    assert fetch(tmp_path, "--work", "32026R1744", "--manifestation", "fmx4") == 1
    assert "failed" in capsys.readouterr().out


def test_unknown_work_is_rejected_by_the_parser(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        fetch(tmp_path, "--work", "32016R0679")
