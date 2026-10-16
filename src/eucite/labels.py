"""From printed labels and source identifiers to identifier numbers (ADR-0002).

A label is what the text prints: ``(a)``, ``a)``, ``3.1.``, ``14 bis)``,
``Article 4a``, ``CAPO III``. A number is what the identifier uses: ``a``,
``3-1``, ``14a``, ``4a``, ``III``. The mapping is deterministic, and a label
that matches no rule is never guessed: :class:`LabelError` names it.

Italian multiplicatives become letters, as EUR-Lex does for articles
(``Articolo 4 bis`` is ``art_4a``) and as Formex does for paragraphs in every
language (``006.001A``).
"""

from __future__ import annotations

import re

__all__ = [
    "MULTIPLICATIVES",
    "LabelError",
    "annex_number",
    "annex_section",
    "article_number",
    "division_number",
    "identifier_number",
    "label_value",
    "point_number",
]


class LabelError(ValueError):
    """A label that no rule recognises."""


# Latin multiplicatives, in order: bis is the first insertion, so "a".
MULTIPLICATIVES = (
    "bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "novies", "decies",
)  # fmt: skip
_LETTER = {word: chr(ord("a") + i) for i, word in enumerate(MULTIPLICATIVES)}
_MULT = "|".join(MULTIPLICATIVES)

# The words that introduce a label, per level, in the languages of the corpus.
CHAPTER_WORDS = frozenset({"chapter", "capo"})
SECTION_WORDS = frozenset({"section", "sezione"})
ARTICLE_WORDS = frozenset({"article", "articolo"})
ANNEX_WORDS = frozenset({"annex", "allegato"})

_ROMAN = re.compile(r"[IVXLC]+")
_VALUE = re.compile(rf"(?P<base>\d+|[a-z]+)(?:\s*(?P<mult>{_MULT})|(?P<suffix>[a-z]+))?")
_DOTTED = re.compile(r"\d+(?:\.\d+)+")


def _clean(label: str) -> str:
    return " ".join(label.split())


def _value(value: str, label: str) -> str:
    """``14 bis`` → ``14a``; ``b ter`` → ``bb``; ``14a`` → ``14a``; ``3.1`` → ``3-1``."""
    if _DOTTED.fullmatch(value):
        return value.replace(".", "-")
    match = _VALUE.fullmatch(value)
    if match is None:
        raise LabelError(f"unrecognised label {label!r}")
    base, mult, suffix = match.group("base", "mult", "suffix")
    if base.isdigit():
        base = str(int(base))
    elif suffix:
        # "ba" is one letter label, not "b" + "a"; only numbers take a suffix.
        return base + suffix
    return base + (_LETTER[mult] if mult else suffix or "")


def label_value(value: str) -> str:
    """Number of a bare label value, as a citation writes it: ``14 bis`` → ``14a``,
    ``b ter`` → ``bb``, ``4a`` → ``4a``, ``iv`` → ``iv``, ``3.1`` → ``3-1``."""
    return _value(_clean(value).lower(), value)


def point_number(label: str) -> str:
    """Number of a point, recital or annex group from its printed label.

    ``(a)`` and ``a)`` → ``a``; ``(iv)`` → ``iv``; ``(1)``, ``1)``, ``1.`` → ``1``;
    ``3.1.`` → ``3-1``; ``a.`` → ``a``; ``(14a)`` and ``14 bis)`` → ``14a``;
    ``b bis)`` → ``ba``.
    """
    text = _clean(label)
    for pattern in (r"\((?P<v>[^()]+)\)", r"(?P<v>[^()]+)\)", r"(?P<v>[^()]+?)\."):
        match = re.fullmatch(pattern, text)
        if match:
            return _value(match.group("v").strip().lower(), label)
    raise LabelError(f"unrecognised label {label!r}")


def identifier_number(identifier: str) -> str:
    """Number from a Formex ``IDENTIFIER``: last component, zeros stripped.

    ``006`` → ``6``; ``004A`` → ``4a``; ``006.001A`` → ``1a``.
    """
    match = re.fullmatch(r"(?:\d{3}[A-Z]*\.)*0*(?P<n>\d+)(?P<s>[A-Z]*)", identifier)
    if match is None:
        raise LabelError(f"unrecognised Formex identifier {identifier!r}")
    return match.group("n") + match.group("s").lower()


def _worded(label: str, words: frozenset[str], number: str) -> str:
    text = _clean(label)
    match = re.fullmatch(rf"(?P<word>\w+)\s+(?P<n>{number})", text)
    if match is None or match.group("word").lower() not in words:
        raise LabelError(f"unrecognised label {label!r}")
    return match.group("n")


def article_number(label: str) -> str:
    """``Article 4a`` and ``Articolo 4 bis`` → ``4a``."""
    value = _worded(label, ARTICLE_WORDS, rf"\d+(?:\s*(?:{_MULT})|[a-z])?")
    return _value(value, label)


def division_number(label: str, *, nested: bool) -> str:
    """``CHAPTER III`` → ``III``; ``SECTION 1`` → ``1`` (a division inside a chapter)."""
    if nested:
        return _worded(label, SECTION_WORDS, r"\d+")
    return _worded(label, CHAPTER_WORDS, _ROMAN.pattern)


def annex_number(label: str) -> str:
    """``ANNEX III`` and ``ALLEGATO III`` → ``III``."""
    return _worded(label, ANNEX_WORDS, _ROMAN.pattern)


_ANNEX_SECTION = re.compile(r"(?P<word>\w+)\s+(?P<n>[A-Z]|\d+)(?:\s*[.\-\u2013\u2014:]\s*|\s+|$)")


def annex_section(title: str) -> tuple[str, str, str]:
    """Split the title of an annex group into label, number and heading.

    ``Section A. List of …`` → (``Section A``, ``a``, ``List of …``);
    ``Sezione A - Informazioni …`` → (``Sezione A``, ``a``, ``Informazioni …``);
    ``Section 1`` → (``Section 1``, ``1``, ``""``).
    """
    text = _clean(title)
    match = _ANNEX_SECTION.match(text)
    if match is None or match.group("word").lower() not in SECTION_WORDS:
        raise LabelError(f"unrecognised annex section title {title!r}")
    label = f"{match.group('word')} {match.group('n')}"
    return label, match.group("n").lower(), text[match.end() :]
