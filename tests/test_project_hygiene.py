"""The legal-hygiene rules of the plan, enforced as tests.

Sections 9.2 and 9.3 of the development plan state two rules: a vocabulary that
must never appear in project materials, and a disclaimer that must always
appear. A rule nobody checks is a rule that erodes, so both are asserted here.

Scope: README.md and the package source — the materials this project writes in
its own voice. ``docs/adr/`` is excluded: an ADR may legitimately need to
discuss why a term is refused, and quoting the normative text is not the same as
speaking in it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

# Section 9.2. These words make a claim this project is not entitled to make:
# they assert a legal conclusion, and the project produces none.
FORBIDDEN = (
    "compliant",
    "certified",
    "guaranteed",
    "legally valid",
    "assessment",
    "risk score",
    "conformity",
)

DISCLAIMER_BLOCK = re.compile(
    r"<!-- disclaimer:start -->(?P<body>.*?)<!-- disclaimer:end -->",
    re.DOTALL,
)


def _materials() -> list[Path]:
    return [README, *sorted((ROOT / "src").rglob("*.py"))]


def _unwrapped(text: str) -> str:
    """Collapse whitespace, so assertions test content and not line wrapping."""
    return " ".join(text.split())


@pytest.mark.parametrize("word", FORBIDDEN)
def test_forbidden_vocabulary_is_absent(word: str) -> None:
    offenders = [
        f"{path.relative_to(ROOT)}:{lineno}"
        for path in _materials()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if word in line.lower()
    ]
    assert not offenders, (
        f"forbidden term {word!r} found in {offenders}. "
        "See section 9.2 of the development plan: this project provides "
        "structure, text and provenance, never conclusions."
    )


def test_readme_carries_the_disclaimer() -> None:
    match = DISCLAIMER_BLOCK.search(README.read_text(encoding="utf-8"))
    assert match is not None, "the delimited disclaimer block is missing from README.md"

    body = _unwrapped(match.group("body"))
    # Both language versions are required: the corpus ships EN and IT.
    assert "Official Journal of the European Union is authentic" in body
    assert "Gazzetta ufficiale dell'Unione europea" in body
    assert "no legal value" in body
    assert "privi di valore giuridico" in body


def test_package_docstring_carries_the_disclaimer() -> None:
    import eucite

    doc = _unwrapped(eucite.__doc__ or "")
    assert "not legal advice" in doc
    assert "no legal value" in doc


def test_data_licence_states_attribution_and_refuses_cc0() -> None:
    """CC0 is not available downstream of CC BY 4.0 material (spike, §C.8)."""
    text = (ROOT / "LICENSE-DATA").read_text(encoding="utf-8")
    assert "CC BY 4.0" in text
    assert "Contains information from EUR-Lex" in text
    assert "CC0" in text and "NOT available" in text
