"""The canonical form ignores presentation and catches content (ADR-0006).

Each manifestation is exercised with two families of variants of one fixture:
changes that must leave the canonical hash untouched, and changes that must
alter it. The second family matters as much as the first: a canonical form
that ignores too much would hide changes in the law.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Callable
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eucite.canonical import (
    CANONICAL_VERSION,
    canonicalize_formex,
    canonicalize_xhtml,
    normalize_text,
)
from tests.doubles import formex_act, formex_bundle

Variant = Callable[[], bytes]

# -- text normalisation ------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("an\u00a0AI\u2009system", "an AI system"),
        ("  leading and\n\ttrailing  ", "leading and trailing"),
        ("high\u2011risk and high\u2013risk", "high-risk and high-risk"),
        ("Member State\u2019s", "Member State's"),
        ("\u201cAI system\u201d and \u00abAI system\u00bb", '"AI system" and "AI system"'),
        ("co\u00adoperation", "cooperation"),
        ("e\u0301", "\u00e9"),  # NFC
        ("paragraph 1 , point (a )", "paragraph 1, point (a)"),
        ("( see Article 6 )", "(see Article 6)"),
    ],
)
def test_text_normalisation(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


WHITESPACE = st.text(alphabet=" \n\t\u00a0\u2009\u202f\u2007", min_size=1, max_size=4)
WORDS = st.lists(st.text(alphabet="abcdefghij", min_size=1, max_size=8), min_size=1, max_size=12)


@given(words=WORDS, data=st.data())
def test_any_whitespace_between_words_is_one_space(words: list[str], data: st.DataObject) -> None:
    separators = [data.draw(WHITESPACE) for _ in words]
    text = "".join(sep + word for sep, word in zip(separators, words, strict=True))
    assert normalize_text(text) == " ".join(words)


# -- Formex ------------------------------------------------------------------------

ARTICLE = (
    "<ENACTING.TERMS>"
    '<ARTICLE IDENTIFIER="006">'
    "<TI.ART>Article 6</TI.ART>"
    "<STI.ART><P>Classification rules</P></STI.ART>"
    '<?PAGE NO="2"?>'
    '<?CLG.MDFO ID="O1" IDREF="C1" ACTION="REPLACED" LEVEL="STRUCTURE" '
    'ACTIVE.DOC="32026R1744" ACTIVE.LOC="AR:1;PT:4"?>'
    '<PARAG IDENTIFIER="006.003">'
    "<NO.PARAG>3.</NO.PARAG>"
    '<ALINEA><P>By derogation from <HT TYPE="ITALIC">paragraph 2</HT>, '
    "an AI system shall not be considered high-risk where:</P>"
    '<LIST TYPE="alpha"><ITEM><NP><NO.P>(a)</NO.P>'
    "<TXT>the AI system performs a narrow procedural task"
    '<NOTE NOTE.ID="E0001" NUMBERING="ARAB"><P>OJ L 1, 1.1.2024, p. 1.</P></NOTE>;</TXT>'
    "</NP></ITEM></LIST>"
    "</ALINEA>"
    "</PARAG>"
    '<?CLG.MDFC ID="C1" IDREF="O1"?>'
    '<PARAG IDENTIFIER="006.004"><NO.PARAG>4.</NO.PARAG>'
    '<ALINEA>The threshold is 10<HT TYPE="SUP">25</HT> operations, as the term '
    '<QUOT.START CODE="2018" ID="Q1" REF.END="Q2"/>operation'
    '<QUOT.END CODE="2019" ID="Q2" REF.START="Q1"/> is used in Article 3.</ALINEA>'
    "</PARAG>"
    "</ARTICLE>"
    "</ENACTING.TERMS>"
)
ANNEX = (
    '<CONTENTS><GR.SEQ LEVEL="1"><TITLE ID.TITLE="T0001"><TI><P>Section A</P></TI></TITLE>'
    "<NP><NO.P>1.</NO.P><TXT>Directive 2006/42/EC</TXT></NP></GR.SEQ></CONTENTS>"
)
QUOTATION = (
    '<QUOT.START CODE="2018" ID="Q1" REF.END="Q2"/>operation'
    '<QUOT.END CODE="2019" ID="Q2" REF.START="Q1"/>'
)


def bundle(article: str = ARTICLE, annex: str = ANNEX, **options: Any) -> bytes:
    return formex_bundle(formex_act(article), (formex_act(annex, root="ANNEX"),), **options)


def edit(old: str, new: str, *, annex: bool = False) -> Variant:
    source = ANNEX if annex else ARTICLE
    assert old in source, old
    if annex:
        return lambda: bundle(annex=ANNEX.replace(old, new))
    return lambda: bundle(article=ARTICLE.replace(old, new))


def other_schema() -> bytes:
    schema = "http://formex.publications.europa.eu/schema/formex-06.03.0.xd"
    return formex_bundle(
        formex_act(ARTICLE, schema=schema), (formex_act(ANNEX, root="ANNEX", schema=schema),)
    )


def other_bibliography() -> bytes:
    act = formex_act(ARTICLE).replace("<PAGE.FIRST>1</PAGE.FIRST>", "<PAGE.FIRST>7</PAGE.FIRST>")
    return formex_bundle(act, (formex_act(ANNEX, root="ANNEX"),))


def page_break_moved() -> bytes:
    article = ARTICLE.replace('<?PAGE NO="2"?>', "")
    return bundle(article=article.replace("</ARTICLE>", '<?PAGE NO="3"?></ARTICLE>'))


PRESENTATION: dict[str, Variant] = {
    "zip member order": lambda: bundle(reverse_members=True),
    "zip timestamps": lambda: bundle(date_time=(2027, 1, 2, 3, 4, 5)),
    "zip compression": lambda: bundle(compression=zipfile.ZIP_STORED),
    "file names": lambda: bundle(prefix="L_RENAMED"),
    "schema version": other_schema,
    "indentation": edit("<PARAG IDENTIFIER", "\n    <PARAG IDENTIFIER"),
    "non-breaking space": edit("an AI system", "an\u00a0AI\u00a0system"),
    "typographic hyphen": edit("high-risk", "high\u2011risk"),
    "italic dropped": edit('<HT TYPE="ITALIC">paragraph 2</HT>', "paragraph 2"),
    "bold added": edit("narrow procedural", '<HT TYPE="BOLD">narrow</HT> procedural'),
    "page break moved": page_break_moved,
    "note renumbered": edit('NOTE.ID="E0001"', 'NOTE.ID="E0042"'),
    "quotation style": edit('CODE="2018" ID="Q1"', 'CODE="201C" ID="Q7"'),
    "attribute order": edit('NOTE.ID="E0001" NUMBERING="ARAB"', 'NUMBERING="ARAB" NOTE.ID="E0001"'),
    "pseudo-attribute order": edit(
        'ID="O1" IDREF="C1" ACTION="REPLACED"', 'ACTION="REPLACED" IDREF="C1" ID="O1"'
    ),
    "bibliographic data": other_bibliography,
    "title identifier": edit('ID.TITLE="T0001"', 'ID.TITLE="T0099"', annex=True),
}

CONTENT: dict[str, Variant] = {
    "a word": edit("narrow procedural", "broad procedural"),
    "a point label": edit("<NO.P>(a)</NO.P>", "<NO.P>(b)</NO.P>"),
    "a paragraph identifier": edit('IDENTIFIER="006.003"', 'IDENTIFIER="006.005"'),
    "an amendment action": edit('ACTION="REPLACED"', 'ACTION="DELETED"'),
    "an amending location": edit('ACTIVE.LOC="AR:1;PT:4"', 'ACTIVE.LOC="AR:1;PT:5"'),
    "a superscript": edit('10<HT TYPE="SUP">25</HT>', "1025"),
    "a quotation removed": edit(QUOTATION, "operation"),
    "a footnote": edit("OJ L 1, 1.1.2024", "OJ L 2, 1.1.2024"),
    "a paragraph renumbered": edit(
        '<PARAG IDENTIFIER="006.004"><NO.PARAG>4.</NO.PARAG>',
        '<PARAG IDENTIFIER="006.002"><NO.PARAG>2.</NO.PARAG>',
    ),
    "annex text": edit("2006/42/EC", "2006/43/EC", annex=True),
    "annex removed": lambda: formex_bundle(formex_act(ARTICLE)),
    "unreferenced file": lambda: bundle(
        extra={"L_TEST.999901.fmx.xml": b"<ANNEX><P>x</P></ANNEX>"}
    ),
}

BASELINE = canonicalize_formex(bundle()).sha256


@pytest.mark.parametrize("name", PRESENTATION)
def test_formex_presentation_does_not_change_the_hash(name: str) -> None:
    assert canonicalize_formex(PRESENTATION[name]()).sha256 == BASELINE


@pytest.mark.parametrize("name", CONTENT)
def test_formex_content_changes_the_hash(name: str) -> None:
    assert canonicalize_formex(CONTENT[name]()).sha256 != BASELINE


def records(content: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in canonicalize_formex(content).lines]


def test_form_starts_with_its_version() -> None:
    assert records(bundle())[0] == {"canonical": CANONICAL_VERSION, "manifestation": "fmx4"}


def test_amendment_markers_are_kept_and_pagination_is_not() -> None:
    text = canonicalize_formex(bundle()).text()
    assert '"t":"?CLG.MDFO"' in text
    assert '"ACTION":"REPLACED"' in text
    assert '"t":"?CLG.MDFC"' in text
    assert "PAGE" not in text


def test_superscript_is_kept_as_markup() -> None:
    texts = [str(r.get("x", "")) for r in records(bundle())]
    assert any("10^{25} operations" in t for t in texts)


def test_text_after_a_nested_block_stays_after_it() -> None:
    article = '<P>replaced by the following:<QUOT.S LEVEL="1"><P>quoted text</P></QUOT.S>;</P>'
    tags = [(r.get("t"), r.get("x")) for r in records(formex_bundle(formex_act(article)))]
    start = tags.index(("P", "replaced by the following:"))
    assert tags[start : start + 4] == [
        ("P", "replaced by the following:"),
        ("QUOT.S", None),
        ("P", "quoted text"),
        ("#tail", ";"),
    ]


def test_publication_metadata_is_not_in_the_form() -> None:
    text = canonicalize_formex(bundle()).text()
    assert "BIB.INSTANCE" not in text
    assert "PAGE.FIRST" not in text
    assert "table of contents" not in text


def including(name: str) -> bytes:
    act = (
        '<P>Annex is added:<QUOT.S LEVEL="1">'
        f'<INCL.ELEMENT FILEREF="{name}" TYPE="FORMEX.DOC"/></QUOT.S></P>'
    )
    return formex_bundle(
        formex_act(act),
        included={name: formex_act("<P>included annex text</P>", root="ANNEX")},
    )


def test_included_files_are_read_where_they_are_included() -> None:
    texts = [r.get("x") for r in records(including("L_TEST.003601.fmx.xml"))]
    assert "included annex text" in texts
    renamed = canonicalize_formex(including("L_OTHER.009901.fmx.xml")).sha256
    assert canonicalize_formex(including("L_TEST.003601.fmx.xml")).sha256 == renamed


def test_a_missing_inclusion_is_recorded() -> None:
    act = '<P><QUOT.S LEVEL="1"><INCL.ELEMENT FILEREF="absent.xml" TYPE="FORMEX.DOC"/></QUOT.S></P>'
    assert any(r.get("t") == "#missing" for r in records(formex_bundle(formex_act(act))))


def test_schema_is_recorded_but_not_hashed() -> None:
    form = canonicalize_formex(bundle())
    assert form.schema is not None and "formex-06.02.1" in form.schema
    assert "formex-06.02.1" not in form.text()


# -- XHTML -------------------------------------------------------------------------

PAGE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>32024R1689</title>\n'
    '<link rel="stylesheet" href="style-v1.css"/><style>p { margin: 0 }</style></head>\n'
    '<body><div class="eli-container">\n'
    '<div class="eli-subdivision" id="art_6"><p class="title-article-norm">Article 6</p>\n'
    '<p class="modref">\u25bcM1</p>\n'
    '<div id="006.003"><p class="norm">3. By derogation from '
    '<span class="italic">paragraph 2</span>, an AI system shall not be considered '
    "high-risk.</p></div>\n"
    '<p class="note" id="id-3f2a0c">(1) OJ L 1</p></div></div>'
    "<script>track()</script></body></html>"
)
MARKER = '<p class="modref">\u25bcM1</p>\n'


def page_edit(old: str, new: str) -> Variant:
    assert old in PAGE, old
    return lambda: PAGE.replace(old, new).encode()


def nested_layout() -> bytes:
    page = PAGE.replace('<div class="eli-container">', '<div class="eli-container"><div>')
    return page.replace("</div></div><script>", "</div></div></div><script>").encode()


def marker_moved() -> bytes:
    page = PAGE.replace(MARKER, "")
    return page.replace('<p class="note"', MARKER + '<p class="note"').encode()


XHTML_PRESENTATION: dict[str, Variant] = {
    "stylesheet": page_edit("style-v1.css", "style-v2.css"),
    "inline style": page_edit("margin: 0", "margin: 1em"),
    "script": page_edit("track()", "trackV2()"),
    "title": page_edit("<title>32024R1689</title>", "<title>AI Act</title>"),
    "class names": page_edit('class="norm"', 'class="norm-text"'),
    "generated id": page_edit('id="id-3f2a0c"', 'id="id-9b1c77"'),
    "inline wrapper": page_edit('<span class="italic">paragraph 2</span>', "paragraph 2"),
    "layout nesting": nested_layout,
    "non-breaking space": page_edit("an AI system", "an\u00a0AI system"),
}

XHTML_CONTENT: dict[str, Variant] = {
    "marker": page_edit("\u25bcM1", "\u25bcB"),
    "structural id": page_edit('id="art_6"', 'id="art_7"'),
    "paragraph id": page_edit('id="006.003"', 'id="006.004"'),
    "a word": page_edit("not be considered", "be considered"),
    "marker moved": marker_moved,
}

XHTML_BASELINE = canonicalize_xhtml(PAGE.encode()).sha256


@pytest.mark.parametrize("name", XHTML_PRESENTATION)
def test_xhtml_presentation_does_not_change_the_hash(name: str) -> None:
    assert canonicalize_xhtml(XHTML_PRESENTATION[name]()).sha256 == XHTML_BASELINE


@pytest.mark.parametrize("name", XHTML_CONTENT)
def test_xhtml_content_changes_the_hash(name: str) -> None:
    assert canonicalize_xhtml(XHTML_CONTENT[name]()).sha256 != XHTML_BASELINE


def test_xhtml_keeps_identifiers_and_markers_in_order() -> None:
    form = [json.loads(line) for line in canonicalize_xhtml(PAGE.encode()).lines[1:]]
    kinds = [(r["t"], r.get("a", {}).get("v") or r.get("x")) for r in form]
    assert kinds[:4] == [
        ("id", "art_6"),
        ("text", "Article 6"),
        ("marker", "\u25bcM1"),
        ("id", "006.003"),
    ]
    assert ("id", "id-3f2a0c") not in kinds
