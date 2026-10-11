"""``eucite dump`` end to end, on the synthetic corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

import eucite.__main__ as cli
from eucite.sources import Manifestation, SourceKey
from tests import synthetic


def dump(root: Path, *extra: str) -> int:
    return cli.main(
        ["dump", "--cache", str(root / "cache"), "--lock", str(root / "lock.json"), *extra]
    )


def corpus(root: Path, override: synthetic.Override | None = None) -> None:
    _, lock = synthetic.corpus(root, override)
    lock.save(root / "lock.json")


def test_dump_writes_the_dataset_and_reports_the_checks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus(tmp_path)
    assert dump(tmp_path, "--out", str(tmp_path / "dist")) == 0
    out = capsys.readouterr().out
    assert out.count(" nodes  sha256:") == 6
    assert "36 inherited identifiers found in EUR-Lex" in out
    assert "3 works with their languages in parity" in out
    assert (tmp_path / "dist" / "manifest.json").is_file()


def test_check_passes_on_a_fresh_dataset_and_fails_after_a_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus(tmp_path)
    out = tmp_path / "dist"
    assert dump(tmp_path, "--out", str(out)) == 0
    assert dump(tmp_path, "--out", str(out), "--check") == 0
    assert capsys.readouterr().out.endswith("identical\n")

    (out / "README.md").write_text("edited")
    assert dump(tmp_path, "--out", str(out), "--check") == 1
    assert "differs   README.md: differs" in capsys.readouterr().out


def test_a_failed_check_writes_nothing_and_says_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def extra_point(key: SourceKey) -> bytes | None:
        if key == SourceKey("32026R1744", "ita", Manifestation.FORMEX):
            return synthetic.formex("ita", {"a": "x;", "b": "y;", "c": "z."})
        return None

    corpus(tmp_path, extra_point)
    assert dump(tmp_path, "--out", str(tmp_path / "dist")) == 1
    assert "presence differs" in capsys.readouterr().err
    assert not (tmp_path / "dist").exists()


def test_archive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    corpus(tmp_path)
    archive = tmp_path / "eucite-dataset-t.1.tar.gz"
    args = ["--out", str(tmp_path / "dist"), "--dataset-version", "t.1", "--archive", str(archive)]
    assert dump(tmp_path, *args) == 0
    assert archive.is_file()
    assert f"wrote {archive}  sha256:" in capsys.readouterr().out


def test_check_and_archive_exclude_each_other(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        dump(tmp_path, "--check", "--archive", str(tmp_path / "a.tar.gz"))
