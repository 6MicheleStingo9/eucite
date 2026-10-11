"""Scaffolding is wired correctly: package imports, CLI runs, help is honest."""

from __future__ import annotations

import pytest

from eucite import DISCLAIMER, __version__
from eucite.__main__ import build_parser, main


def test_version_is_exposed() -> None:
    assert __version__


def test_no_command_prints_help_and_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "eucite" in capsys.readouterr().out


def test_help_carries_the_disclaimer(capsys: pytest.CaptureFixture[str]) -> None:
    """The disclaimer is required in CLI output, not only in the README."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0

    out = capsys.readouterr().out
    assert "Official Journal of the European Union is authentic" in out
    assert "no legal value" in out


# Subcommands implemented so far, each by the step that delivers it (S1, S7, S8).
IMPLEMENTED = {"fetch", "dump"}


def test_parser_advertises_no_unimplemented_command() -> None:
    """``--help`` must never list a subcommand that does not work yet."""
    actions = [a for a in build_parser()._actions if a.dest == "command"]
    assert len(actions) == 1
    assert set(actions[0].choices or ()) == IMPLEMENTED


def test_disclaimer_constant_is_not_empty() -> None:
    assert "authentic" in DISCLAIMER
