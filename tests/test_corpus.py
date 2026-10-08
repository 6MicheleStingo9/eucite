"""The parser on the real corpus: the six locked Formex manifestations.

These tests read the sources from the local cache, as the lock pins them. They
are skipped where the cache lacks them, and fail instead when
``EUCITE_REQUIRE_DATA`` is set: the CI job ``data`` restores the cache with
``eucite fetch --frozen`` and sets it.

Three checks do not rely on the parser's own logic:

- the inherited identifiers are compared with those of the XHTML, an
  independent rendering by the Publications Office;
- the words of each article, annex, recital and citation are compared with the
  words of the source element, extracted by a separate walk that only removes
  footnotes and deleted ranges;
- the counts are those measured for ADR-0002 (S4), less what the consolidated
  text deletes.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest
from lxml import etree

from eucite.cache import ObjectStore, SourceLock
from eucite.corpus import load_document, locked_payload
from eucite.crosscheck import crosscheck, xhtml_identifiers
from eucite.formex import Element, FormexBundle, read_bundle
from eucite.nodes import Document
from eucite.sources import LANGUAGES, WORKS, Manifestation, SourceKey
from tests.invariants import assert_composition, assert_tree

pytestmark = pytest.mark.data

ROOT = Path(__file__).resolve().parent.parent
LOCK = SourceLock.load(ROOT / "sources.lock.json")
STORE = ObjectStore(ROOT / "cache")
SOURCES = [(w.celex, lang) for w in WORKS for lang in LANGUAGES]


def payload(celex: str, lang: str, manifestation: Manifestation) -> bytes:
    key = SourceKey(celex, lang, manifestation)
    entry = LOCK.get(key)
    if entry is None or not STORE.has(entry.sha256):
        message = f"{key} is not in the local cache: run `eucite fetch --frozen`"
        if os.environ.get("EUCITE_REQUIRE_DATA"):
            pytest.fail(message)
        pytest.skip(message)
    return locked_payload(key, store=STORE, lock=LOCK)


@cache
def _document(celex: str, lang: str) -> Document:
    return load_document(celex, lang, store=STORE, lock=LOCK)


def document(celex: str, lang: str) -> Document:
    payload(celex, lang, Manifestation.FORMEX)  # skips if absent
    return _document(celex, lang)


# Node counts by type. Articles to points match the S4 measurement (ADR-0002):
# 1 866 in the consolidated text, of which the 7 below the deleted Article 10(5)
# are no longer part of it; 1 665 in the base act.
COUNTS = {
    "02024R1689-20260727": {
        "act": 1, "chapter": 13, "section": 45, "article": 119, "paragraph": 553,
        "subparagraph": 666, "point": 711, "indent": 16, "annex": 14, "table": 6,
    },
    "32024R1689": {
        "act": 1, "citation": 7, "recital": 180, "chapter": 13, "section": 35, "article": 113,
        "paragraph": 500, "subparagraph": 585, "point": 656, "indent": 16, "annex": 13,
    },
    "32026R1744": {
        "act": 1, "citation": 7, "recital": 47, "article": 4, "subparagraph": 4, "point": 101,
        "indent": 3,
    },
}  # fmt: skip


@pytest.mark.parametrize(("celex", "lang"), SOURCES)
def test_counts(celex: str, lang: str) -> None:
    doc = document(celex, lang)
    assert Counter(n.type.value for n in doc.nodes) == COUNTS[celex]
    in_articles = [n for n in doc.nodes if n.id.split("/")[-1].startswith("art_")]
    expected = {"02024R1689-20260727": 1866 - 7, "32024R1689": 1665, "32026R1744": 109}
    assert len([n for n in in_articles if n.type.value != "indent"]) == expected[celex]


@pytest.mark.parametrize(("celex", "lang"), SOURCES)
def test_tree_and_composition(celex: str, lang: str) -> None:
    doc = document(celex, lang)
    assert_tree(doc)
    assert_composition(doc)


@pytest.mark.parametrize(("celex", "lang"), SOURCES)
def test_inherited_identifiers_exist_in_eurlex(celex: str, lang: str) -> None:
    doc = document(celex, lang)
    check = crosscheck(doc, xhtml_identifiers(payload(celex, lang, Manifestation.XHTML)))
    assert check.ok, (check.missing, check.unmatched)
    checked = {"02024R1689-20260727": 162, "32024R1689": 842, "32026R1744": 58}
    assert check.checked == checked[celex]


def test_the_deleted_provisions_of_the_consolidated_text() -> None:
    for lang in LANGUAGES:
        doc = document("02024R1689-20260727", lang)
        assert [n.id.split("/")[1] for n in doc.nodes if n.deleted] == [
            "art_10.para_5",
            "anx_I.sct_a.point_1",
            "anx_VIII.sct_b.point_7",
            "anx_VIII.sct_b.point_9",
        ]


def test_every_amendment_marker_reaches_a_node() -> None:
    """Each marker of the source lands on a node, and nodes carry no other."""
    for lang in LANGUAGES:
        content = payload("02024R1689-20260727", lang, Manifestation.FORMEX)
        root = read_bundle(content).documents[0].root
        markers = [
            {k: v for k, _, v in _PSEUDO_ATTR.findall(pi.text or "")}
            for pi in root.iter(etree.ProcessingInstruction)
            if pi.target == "CLG.MDFO"
        ]
        assert len(markers) == 77
        source = {
            (m["ACTIVE.LOC"], m["ACTION"].lower(), m["COMMAND"] == "IMPLICIT") for m in markers
        }
        doc = document("02024R1689-20260727", lang)
        nodes = {(a.location, a.action, a.implicit) for n in doc.nodes for a in n.amendments}
        assert nodes == source


def test_english_and_italian_have_the_same_structure() -> None:
    """Anticipates S6: identifiers, types, parents and amendments coincide."""
    for celex in (w.celex for w in WORKS):
        en, it = (document(celex, lang) for lang in ("eng", "ita"))
        shape = [(n.id, n.type, n.parent, n.amendments) for n in en.nodes]
        assert shape == [(n.id, n.type, n.parent, n.amendments) for n in it.nodes]


# -- no word lost --------------------------------------------------------------------

WORD = re.compile(r"\w+")
_PSEUDO_ATTR = re.compile(r'([\w.]+)=(["\'])(.*?)\2')
_GROUPED = re.compile(r"(?<=\d) (?=\d{3}\b)")
TOP_LEVEL = {"ARTICLE", "CONS.ANNEX", "ANNEX", "CONSID", "VISA"}


def source_words(bundle: FormexBundle) -> list[list[str]]:
    """Words of each top-level element in document order: footnotes and
    deleted ranges removed, nothing else interpreted."""
    out: list[list[str]] = []
    deleting: set[str] = set()

    def walk(el: Element, top: int | None) -> None:
        if el.tag is etree.ProcessingInstruction:
            attrs = {k: v for k, _, v in _PSEUDO_ATTR.findall(el.text or "")}
            if el.target == "CLG.MDFO" and attrs.get("ACTION") == "DELETED":
                deleting.add(attrs["ID"])
            elif el.target == "CLG.MDFC":
                deleting.discard(attrs.get("IDREF", ""))
            return
        if not isinstance(el.tag, str) or el.tag in ("NOTE", "BIB.INSTANCE"):
            return
        quoted = any(a.tag == "QUOT.S" for a in el.iterancestors())
        if top is None and el.tag in TOP_LEVEL and not quoted:
            top = len(out)
            out.append([])

        def emit(text: str | None) -> None:
            if top is not None and text and not deleting:
                out[top].extend(WORD.findall(text))

        emit(el.text)
        if el.tag == "INCL.ELEMENT":
            walk(bundle.included(el.get("FILEREF", "")), top)
        for child in el:
            walk(child, top)
            emit(child.tail)

    for doc in bundle.documents:
        walk(doc.root, None)
    return out


def node_words(doc: Document) -> Iterator[tuple[str, list[str]]]:
    for n in doc.nodes:
        if n.type.value in ("article", "annex", "recital", "citation"):
            text = " ".join(x for x in (n.label, n.heading, n.text) if x)
            yield n.id, WORD.findall(_GROUPED.sub("", text))


@pytest.mark.parametrize(("celex", "lang"), SOURCES)
def test_no_word_is_lost_or_added(celex: str, lang: str) -> None:
    expected = source_words(read_bundle(payload(celex, lang, Manifestation.FORMEX)))
    actual = list(node_words(document(celex, lang)))
    assert len(actual) == len(expected)
    for (node_id, words), source in zip(actual, expected, strict=True):
        assert words == source, node_id
