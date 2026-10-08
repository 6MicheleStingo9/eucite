"""Inherited identifiers checked against EUR-Lex (ADR-0002, ADR-0012).

An identifier is *inherited* when it transcribes one the source provides. The
claim is checked, not trusted: every inherited identifier of a level EUR-Lex
names (``art_6``, ``cpt_III.sct_1``, ``anx_XIV``, ``rct_58``, ``cit_1``) must
appear among the identifiers of the XHTML manifestation of the same work, and
every such identifier of the XHTML must belong to a node. Paragraph references
(``006.001A``) are checked where the XHTML carries them; the consolidated
XHTML does not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import lxml.html

from eucite.nodes import Document

__all__ = ["CrossCheck", "crosscheck", "xhtml_identifiers"]

# Identifiers EUR-Lex gives to the levels this project inherits.
EURLEX_ID = re.compile(r"art_\d+[a-z]*|cpt_[IVXLC]+(?:\.sct_\d+)?|anx_[IVXLC]+|rct_\d+|cit_\d+")
# Formex paragraph identifiers, as the XHTML of a published act repeats them.
PARAGRAPH_ID = re.compile(r"\d{3}[A-Z]*\.\d{3}[A-Z]*")


def xhtml_identifiers(content: bytes) -> frozenset[str]:
    """Every ``id`` attribute of the XHTML manifestation."""
    document = lxml.html.document_fromstring(content)
    return frozenset(str(el.get("id")) for el in document.iter() if el.get("id"))


@dataclass(frozen=True)
class CrossCheck:
    checked: int
    missing: tuple[str, ...]
    """Inherited identifiers the XHTML does not have."""
    unmatched: tuple[str, ...]
    """EUR-Lex identifiers of the XHTML that no node inherits."""
    unchecked: int
    """Paragraph references not checkable: the XHTML carries none."""

    @property
    def ok(self) -> bool:
        return not self.missing and not self.unmatched


def crosscheck(document: Document, identifiers: frozenset[str]) -> CrossCheck:
    paragraphs_available = any(PARAGRAPH_ID.fullmatch(i) for i in identifiers)
    refs = [n.source_ref for n in document.nodes if n.id_provenance == "inherited" and n.source_ref]
    refs = [r for r in refs if r != document.act]
    checkable = [r for r in refs if EURLEX_ID.fullmatch(r) or paragraphs_available]
    missing = tuple(r for r in checkable if r not in identifiers)
    inherited = set(refs)
    unmatched = tuple(
        sorted(i for i in identifiers if EURLEX_ID.fullmatch(i) and i not in inherited)
    )
    return CrossCheck(
        checked=len(checkable),
        missing=missing,
        unmatched=unmatched,
        unchecked=len(refs) - len(checkable),
    )
