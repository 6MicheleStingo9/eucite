"""Canonical form of a payload (ADR-0006).

The canonical form answers one question: *did the content change, or only its
presentation?* Bytes cannot answer it. Cellar regenerates manifestations for
reasons that have nothing to do with the law — the consolidated text was
regenerated on 11 August 2026 without any new amending act — and a byte
comparison would raise an alarm every time.

The form is a sequence of JSON lines, one per block of content, in document
order, preceded by a header that names the canonicalisation version. Its
SHA-256 is the canonical hash. Being line-oriented, two canonical forms can be
diffed, so a reported change can be shown, not only signalled.

What is kept and what is discarded follows one rule: **in doubt, it is
content.** Only what is known to be presentation or publication metadata is
discarded, by an explicit list. An element or attribute nobody has classified is
kept, so a change in it is reported. A false alarm costs a review; a missed
change defeats the purpose.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import lxml.html
from lxml import etree

from eucite.formex import Element, FormexBundle, read_bundle
from eucite.sources import Manifestation

__all__ = [
    "CANONICAL_VERSION",
    "CanonicalForm",
    "canonicalize",
    "canonicalize_formex",
    "canonicalize_xhtml",
    "normalize_text",
]

CANONICAL_VERSION = 1
"""Bumped whenever the rules below change. Hashes of different versions are
never compared: the version is part of the hashed content."""


# -- text ------------------------------------------------------------------------

# Characters that carry no content.
_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"))
# Typographic variants of the same character.
_TYPOGRAPHIC = str.maketrans(
    {
        **dict.fromkeys("\u2018\u2019\u201a\u201b\u2032", "'"),
        **dict.fromkeys("\u201c\u201d\u201e\u201f\u2033\u00ab\u00bb", '"'),
        **dict.fromkeys("\u2010\u2011\u2012\u2013\u2014\u2015\u2212", "-"),
        "\u2026": "...",
    }
)
_SPACE = re.compile(r"\s+")
_SPACE_BEFORE_CLOSING = re.compile(r" ([,.;:!?)\]])")
_SPACE_AFTER_OPENING = re.compile(r"([(\[]) ")


def normalize_text(text: str) -> str:
    """Normalise text so that only differences of content survive.

    Unicode NFC; invisible characters removed; typographic quotes, apostrophes
    and dashes folded to their ASCII form; every run of whitespace (including
    non-breaking and thin spaces) collapsed to one space; no space before
    closing punctuation or after an opening bracket.
    """
    text = unicodedata.normalize("NFC", text).translate(_INVISIBLE).translate(_TYPOGRAPHIC)
    text = _SPACE.sub(" ", text).strip()
    text = _SPACE_BEFORE_CLOSING.sub(r"\1", text)
    return _SPACE_AFTER_OPENING.sub(r"\1", text)


# -- the form ----------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalForm:
    manifestation: Manifestation
    lines: tuple[str, ...]
    schema: str | None = None
    """Declared schema of the source. Recorded, not hashed: a schema upgrade
    that changes nothing else is presentation."""

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text().encode("utf-8")).hexdigest()


def _line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _header(manifestation: Manifestation) -> str:
    return _line({"canonical": CANONICAL_VERSION, "manifestation": manifestation.value})


def _record(depth: int | None, tag: str, attrs: dict[str, str], text: str) -> str:
    record: dict[str, Any] = {"t": tag}
    if depth is not None:
        record["d"] = depth
    if attrs:
        record["a"] = attrs
    if text:
        record["x"] = text
    return _line(record)


# -- Formex ------------------------------------------------------------------------

# Subtrees that describe the publication or its production, not the act.
FORMEX_DROP = frozenset({"BIB.INSTANCE", "INFO.CONSLEG", "INFO.PROD"})
# Elements whose text belongs to the enclosing block. Their attributes repeat
# the text (DATE@ISO, REF.DOC.OJ@PAGE.FIRST) or are presentation (HT@TYPE).
FORMEX_INLINE = frozenset(
    {"HT", "DATE", "REF.DOC", "REF.DOC.OJ", "LINK", "FT", "IE", "NO.P", "NO.PARAG", "TXT"}
)
# Labels ("(a)", "1.") are separated from the text that follows them.
FORMEX_LABELS = frozenset({"NO.P", "NO.PARAG"})
# Quotation boundaries: kept as a quotation mark, whatever character was used.
FORMEX_QUOTES = frozenset({"QUOT.START", "QUOT.END"})
# Superscript and subscript change meaning ("10²⁵" is not "1025"): kept as markup.
_HT_MARKUP = {"SUP": ("^{", "}"), "SUB": ("_{", "}")}
# Processing instructions that are pagination. Every other one is content: the
# consolidated text records its amendments as CLG.MDFO / CLG.MDFC pairs.
FORMEX_DROP_PIS = frozenset({"PAGE"})
_PSEUDO_ATTR = re.compile(r'([\w.]+)=(["\'])(.*?)\2')
# Attributes that are generated numbering, cross-file links or schema location.
FORMEX_DROP_ATTRS = frozenset(
    {
        "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation",
        "ID.TITLE",
        "REF.TITLE",
        "NO.SEQ",
        "NOTE.ID",
        "NUMBERING",
        "NUMBERING.CONTINUED",
        "NUMBER.ORG",
        "FILEREF",
    }
)


def _attrs(el: Element) -> dict[str, str]:
    return {k: v for k, v in sorted(el.attrib.items()) if k not in FORMEX_DROP_ATTRS}


def _collect(el: Element, segments: list[list[str]], blocks: list[Element]) -> None:
    """Gather the text of ``el`` and the blocks nested in it, in document order.

    ``segments[i]`` is the text that precedes ``blocks[i]``; the last segment is
    the text after the last block. Keeping them apart preserves order: the ";"
    that follows a quoted block stays after it.
    """
    segments[-1].append(el.text or "")
    for child in el:
        tag = child.tag
        if _is_pi(child):
            if child.target not in FORMEX_DROP_PIS:
                blocks.append(child)
                segments.append([])
        elif tag in FORMEX_DROP:
            pass
        elif tag in FORMEX_QUOTES:
            segments[-1].append('"')
        elif tag in FORMEX_INLINE:
            before, after = ("", "")
            if tag == "HT":
                before, after = _HT_MARKUP.get(child.get("TYPE", ""), ("", ""))
            segments[-1].append(before)
            _collect(child, segments, blocks)
            segments[-1].append(" " if tag in FORMEX_LABELS else after)
        else:
            blocks.append(child)
            segments.append([])
        segments[-1].append(child.tail or "")


def _is_pi(node: Element) -> bool:
    return node.tag is etree.ProcessingInstruction


def _walk_formex(el: Element, depth: int, bundle: FormexBundle) -> Iterator[str]:
    if _is_pi(el):
        attrs = {k: v for k, _, v in _PSEUDO_ATTR.findall(el.text or "")}
        yield _record(depth, f"?{el.target}", dict(sorted(attrs.items())), "")
        return
    if el.tag in FORMEX_DROP:
        return
    if el.tag == "INCL.ELEMENT":
        yield _record(depth, el.tag, _attrs(el), "")
        included = bundle.included(el.get("FILEREF", ""))
        if included is None:
            yield _record(depth + 1, "#missing", {}, "")
        else:
            yield from _walk_formex(included, depth + 1, bundle)
        return
    segments: list[list[str]] = [[]]
    blocks: list[Element] = []
    _collect(el, segments, blocks)
    yield _record(depth, el.tag, _attrs(el), normalize_text("".join(segments[0])))
    for block, after in zip(blocks, segments[1:], strict=True):
        yield from _walk_formex(block, depth + 1, bundle)
        tail = normalize_text("".join(after))
        if tail:
            yield _record(depth, "#tail", {}, tail)


def canonicalize_formex(content: bytes) -> CanonicalForm:
    bundle = read_bundle(content)
    lines = [_header(Manifestation.FORMEX)]
    for doc in bundle.documents:
        attrs = {"role": doc.role, "seq": doc.seq}
        if doc.kind:
            attrs["kind"] = doc.kind
        lines.append(_record(0, "#document", attrs, ""))
        lines.extend(_walk_formex(doc.root, 1, bundle))
    return CanonicalForm(Manifestation.FORMEX, tuple(lines), schema=bundle.schema)


# -- XHTML -------------------------------------------------------------------------

XHTML_DROP = frozenset({"head", "script", "style", "noscript", "template"})
XHTML_BLOCKS = frozenset(
    {
        "address", "article", "aside", "blockquote", "body", "caption", "dd", "div", "dl",
        "dt", "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header",
        "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table", "tbody", "td",
        "tfoot", "th", "thead", "tr", "ul",
    }
)  # fmt: skip
# Identifiers this project consumes: EUR-Lex subdivisions (art_6, cpt_III.sct_1,
# rct_58) and Formex paragraph numbers (006.003). Generated ones (id-<uuid>,
# d1e123-1-1, file-derived note anchors) are presentation.
_STRUCTURAL_ID = re.compile(
    r"^[a-z]{2,5}_[A-Za-z0-9]+(?:\.[a-z]{2,5}_[A-Za-z0-9]+)*$|^\d{3}\.\d{3}[A-Z]*$"
)


def _is_marker(el: Element) -> bool:
    return "modref" in (el.get("class") or "").split()


def _collect_html(el: Element, segments: list[list[str]], blocks: list[Element]) -> None:
    segments[-1].append(el.text or "")
    for child in el:
        if not isinstance(child.tag, str):
            pass
        elif child.tag in XHTML_DROP:
            pass
        elif (
            child.tag in XHTML_BLOCKS
            or _is_marker(child)
            or _STRUCTURAL_ID.match(child.get("id") or "")
        ):
            blocks.append(child)
            segments.append([])
        else:
            _collect_html(child, segments, blocks)
        segments[-1].append(child.tail or "")


def _walk_xhtml(el: Element) -> Iterator[str]:
    if el.tag in XHTML_DROP:
        return
    ident = el.get("id") or ""
    if _STRUCTURAL_ID.match(ident):
        yield _record(None, "id", {"v": ident}, "")
    if _is_marker(el):
        yield _record(None, "marker", {}, normalize_text(el.text_content()))
        return
    segments: list[list[str]] = [[]]
    blocks: list[Element] = []
    _collect_html(el, segments, blocks)
    text = normalize_text("".join(segments[0]))
    if text:
        yield _record(None, "text", {}, text)
    for block, after in zip(blocks, segments[1:], strict=True):
        yield from _walk_xhtml(block)
        tail = normalize_text("".join(after))
        if tail:
            yield _record(None, "text", {}, tail)


def canonicalize_xhtml(content: bytes) -> CanonicalForm:
    """Structural identifiers, amendment markers and text, in document order.

    Nesting and classes are not kept: in this manifestation they are layout. The
    identifiers and markers are what this project reads from it (ADR-0001).
    """
    document = lxml.html.document_fromstring(content)
    body = document.find("body")
    lines = [_header(Manifestation.XHTML)]
    if body is not None:
        lines.extend(_walk_xhtml(body))
    return CanonicalForm(Manifestation.XHTML, tuple(lines))


def canonicalize(manifestation: Manifestation, content: bytes) -> CanonicalForm:
    if manifestation is Manifestation.FORMEX:
        return canonicalize_formex(content)
    return canonicalize_xhtml(content)
