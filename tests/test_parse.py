"""The Formex parser on synthetic documents: structure, identifiers, text, amendments.

Each test builds the smallest Formex that shows one rule of ADR-0012 or
ADR-0002. The real corpus is checked separately (``test_corpus.py``).
"""

from __future__ import annotations

import pytest

from eucite.nodes import NodeType
from eucite.parse import ParseError
from tests.builders import (
    act,
    alinea,
    annex_document,
    article,
    cons_annex,
    consolidated,
    division,
    enacting,
    group,
    indent,
    item,
    lst,
    mdfc,
    mdfo,
    np_,
    p,
    parag,
    parse,
    preamble,
    title,
)
from tests.doubles import formex_act

A = "32099R0001"


def ids(doc: object) -> list[str]:
    return [n.id for n in doc.nodes]  # type: ignore[attr-defined]


# -- structure and identifiers --------------------------------------------------------


def test_article_paragraph_subparagraph_point() -> None:
    doc = parse(
        act(
            article(
                "006",
                "Article 6",
                "Classification rules",
                parag("006.001", "1.", alinea("An AI system shall be high-risk.")),
                parag(
                    "006.003",
                    "3.",
                    alinea("By derogation, it is not high-risk."),
                    alinea(
                        p("That is the case where:"),
                        lst(
                            item("(a)", "the task is narrow;"),
                            item("(b)", "the task is preparatory."),
                        ),
                    ),
                ),
            )
        )
    )
    assert ids(doc) == [
        A,
        f"{A}/art_6",
        f"{A}/art_6.para_1",
        f"{A}/art_6.para_1.subpara_1",
        f"{A}/art_6.para_3",
        f"{A}/art_6.para_3.subpara_1",
        f"{A}/art_6.para_3.subpara_2",
        f"{A}/art_6.para_3.subpara_2.point_a",
        f"{A}/art_6.para_3.subpara_2.point_b",
    ]
    art = doc.node(f"{A}/art_6")
    assert (art.type, art.label, art.heading, art.parent) == (
        NodeType.ARTICLE,
        "Article 6",
        "Classification rules",
        A,
    )
    assert (art.id_provenance, art.id_basis, art.source_ref) == ("inherited", "source", "art_6")
    para = doc.node(f"{A}/art_6.para_3")
    assert (para.id_provenance, para.id_basis, para.source_ref) == (
        "inherited",
        "source",
        "006.003",
    )
    sub = doc.node(f"{A}/art_6.para_3.subpara_2")
    assert (sub.id_provenance, sub.id_basis, sub.source_ref) == ("derived", "position", None)
    point = doc.node(f"{A}/art_6.para_3.subpara_2.point_a")
    assert (point.label, point.text, point.id_basis) == ("(a)", "the task is narrow;", "label")


def test_text_includes_children_one_block_per_line() -> None:
    doc = parse(
        act(
            article(
                "006",
                "Article 6",
                "Rules",
                parag(
                    "006.003",
                    "3.",
                    alinea("First."),
                    alinea(
                        p("That is the case where:"), lst(item("(a)", "one;"), item("(b)", "two."))
                    ),
                ),
            )
        )
    )
    assert doc.node(f"{A}/art_6.para_3.subpara_2").text == (
        "That is the case where:\n(a) one;\n(b) two."
    )
    assert doc.node(f"{A}/art_6").text == ("3. First.\nThat is the case where:\n(a) one;\n(b) two.")


def test_article_without_paragraphs_has_subparagraphs_directly() -> None:
    doc = parse(
        act(
            article(
                "003",
                "Article 3",
                "Definitions",
                alinea(
                    p("For the purposes of this Regulation:"),
                    lst(item("(1)", "'AI system' means a system;")),
                ),
            )
        )
    )
    assert f"{A}/art_3.subpara_1.point_1" in ids(doc)


def test_italian_labels_map_to_the_same_identifiers() -> None:
    doc = parse(
        act(
            article(
                "004A",
                "Articolo 4 bis",
                "Trattamento",
                parag(
                    "004A.001A",
                    "1 bis.",
                    alinea(
                        p("Si applica:"), lst(item("14 bis)", "voce;"), item("b ter)", "altra."))
                    ),
                ),
            )
        ),
        language="ita",
    )
    assert ids(doc)[1:] == [
        f"{A}/art_4a",
        f"{A}/art_4a.para_1a",
        f"{A}/art_4a.para_1a.subpara_1",
        f"{A}/art_4a.para_1a.subpara_1.point_14a",
        f"{A}/art_4a.para_1a.subpara_1.point_bb",
    ]
    assert doc.node(f"{A}/art_4a.para_1a.subpara_1.point_14a").label == "14 bis)"


def test_label_must_agree_with_the_formex_identifier() -> None:
    with pytest.raises(ParseError, match="disagrees with IDENTIFIER '006'"):
        parse(act(article("006", "Article 7", None, alinea("Text."))))
    with pytest.raises(ParseError, match=r"disagrees with IDENTIFIER '006\.002'"):
        parse(act(article("006", "Article 6", None, parag("006.002", "3.", alinea("Text.")))))


def test_an_unknown_label_is_refused_and_named() -> None:
    with pytest.raises(ParseError, match=r"unrecognised label '\(a\)\(b\)' at /ACT"):
        parse(act(article("001", "Article 1", None, alinea(p("x"), lst(item("(a)(b)", "y."))))))


def test_nested_points_and_indents() -> None:
    doc = parse(
        act(
            article(
                "005",
                "Article 5",
                None,
                alinea(
                    p("Prohibited:"),
                    lst(
                        item(
                            "(h)",
                            "remote identification, unless for:",
                            p(
                                lst(
                                    item("(i)", "the search;", ""),
                                    item("(ii)", "the prevention."),
                                    type_="roman",
                                )
                            ),
                        ),
                    ),
                    p("Offences:"),
                    lst(indent("terrorism,"), indent("sabotage."), type_="DASH"),
                ),
            )
        )
    )
    base = f"{A}/art_5.subpara_1"
    assert ids(doc)[2:] == [
        base,
        f"{base}.point_h",
        f"{base}.point_h.point_i",
        f"{base}.point_h.point_ii",
        f"{base}.indent_1",
        f"{base}.indent_2",
    ]
    assert doc.node(f"{base}.point_h").text == (
        "remote identification, unless for:\n(i) the search;\n(ii) the prevention."
    )
    assert doc.node(f"{base}.indent_2").id_basis == "position"


def test_chapters_sections_and_containers() -> None:
    doc = parse(
        act(
            division(
                "CHAPTER III",
                "HIGH-RISK AI SYSTEMS",
                division(
                    "SECTION 2",
                    "Requirements",
                    article("008", "Article 8", "Compliance", alinea("Text.")),
                ),
            )
        )
    )
    chapter, section, art = (
        doc.node(i) for i in (f"{A}/cpt_III", f"{A}/cpt_III.sct_2", f"{A}/art_8")
    )
    assert (chapter.label, chapter.heading, chapter.text) == (
        "CHAPTER III",
        "HIGH-RISK AI SYSTEMS",
        None,
    )
    assert (section.parent, section.source_ref, section.text) == (chapter.id, "cpt_III.sct_2", None)
    assert art.parent == section.id
    assert doc.node(A).text is None


def test_root_carries_the_title_and_the_represented_act() -> None:
    doc = parse(
        consolidated(article("001", "Article 1", None, alinea("Text."))), work="02099R0001-20990101"
    )
    assert (doc.work, doc.act) == ("02099R0001-20990101", "32099R0001")
    root = doc.nodes[0]
    assert (root.id, root.type, root.heading, root.parent) == (
        A,
        NodeType.ACT,
        "Regulation (EU) 2099/1 of the test",
        None,
    )
    assert doc.node(f"{A}/art_1").text == "Text."


def test_recitals_and_citations() -> None:
    main = formex_act(
        title()
        + preamble(
            visas=("Having regard to the Treaty,", "Whereas the Parliament,"),
            recitals=("First recital.", "Second."),
        )
        + enacting(article("001", "Article 1", None, alinea("Text.")))
    )
    doc = parse(main)
    assert ids(doc)[1:5] == [f"{A}/cit_1", f"{A}/cit_2", f"{A}/rct_1", f"{A}/rct_2"]
    recital = doc.node(f"{A}/rct_2")
    assert (recital.label, recital.text, recital.source_ref) == ("(2)", "Second.", "rct_2")
    citation = doc.node(f"{A}/cit_1")
    assert (citation.text, citation.id_provenance, citation.source_ref) == (
        "Having regard to the Treaty,",
        "inherited",
        "cit_1",
    )


def test_annexes_sections_points_and_tables() -> None:
    first = annex_document(
        "ANNEX I",
        "List of legislation",
        group(
            "<TI><P>Section A. Based on the New Legislative Framework</P></TI>",
            np_("1.", "Directive A;"),
            np_("2.", "Directive B."),
        ),
        group(
            "<TI><P>Section B</P></TI><STI><P>Other legislation</P></STI>",
            np_("3.", "Regulation C."),
        ),
    )
    second = annex_document(
        "ANNEX II",
        None,
        p("Introduction."),
        group(
            "<TI><NP><NO.P>2.</NO.P><TXT>Codes</TXT></NP></TI>",
            group(
                "<TI><NP><NO.P>a.</NO.P><TXT>Systems</TXT></NP></TI>",
                p(
                    '<TBL COLS="2"><CORPUS>'
                    '<ROW TYPE="HEADER"><CELL>Code</CELL><CELL><IE/></CELL></ROW>'
                    "<ROW><CELL>AIP 0102</CELL><CELL><P>Toys</P><P>and games</P></CELL></ROW>"
                    "</CORPUS></TBL>"
                ),
            ),
        ),
        np_("3.", "A point outside any list."),
    )
    doc = parse(act(article("001", "Article 1", None, alinea("Text."))), (first, second))
    assert ids(doc)[3:] == [
        f"{A}/anx_I",
        f"{A}/anx_I.sct_a",
        f"{A}/anx_I.sct_a.point_1",
        f"{A}/anx_I.sct_a.point_2",
        f"{A}/anx_I.sct_b",
        f"{A}/anx_I.sct_b.point_3",
        f"{A}/anx_II",
        f"{A}/anx_II.sct_2",
        f"{A}/anx_II.sct_2.sct_a",
        f"{A}/anx_II.sct_2.sct_a.table_1",
        f"{A}/anx_II.point_3",
    ]
    section = doc.node(f"{A}/anx_I.sct_a")
    assert (section.label, section.heading, section.id_basis) == (
        "Section A",
        "Based on the New Legislative Framework",
        "label",
    )
    assert doc.node(f"{A}/anx_I.sct_b").heading == "Other legislation"
    assert doc.node(f"{A}/anx_I").text == (
        "Section A Based on the New Legislative Framework\n1. Directive A;\n2. Directive B.\n"
        "Section B Other legislation\n3. Regulation C."
    )
    assert doc.node(f"{A}/anx_II.sct_2.sct_a.table_1").text == "Code |\nAIP 0102 | Toys and games"
    assert doc.node(f"{A}/anx_II.sct_2").label == "2."


# -- text --------------------------------------------------------------------------------


def test_quoted_text_is_never_structure() -> None:
    quoted = (
        "<QUOT.S>"
        '<PARAG IDENTIFIER="002.013"><NO.PARAG><QUOT.START CODE="2018"/>13.</NO.PARAG>'
        "<ALINEA><P>For these systems:</P>"
        f"{lst(item('(a)', 'one;'), item('(b)', 'two.'))}"
        '<QUOT.END CODE="2019"/></ALINEA></PARAG></QUOT.S>'
    )
    doc = parse(
        act(
            article(
                "001",
                "Article 1",
                None,
                alinea(
                    p("Regulation X is amended:"),
                    lst(item("(3)", f"in Article 2, a paragraph is added:{quoted};")),
                ),
            )
        )
    )
    assert len(doc.nodes) == 4  # act, article, subparagraph, point (3)
    assert doc.node(f"{A}/art_1.subpara_1.point_3").text == (
        "in Article 2, a paragraph is added:\n"
        "\u201813. For these systems:\n(a) one;\n(b) two.\u2019;"
    )


def test_notes_are_kept_apart_from_the_text() -> None:
    doc = parse(
        act(
            article(
                "040",
                "Article 40",
                None,
                alinea(
                    "Regulation (EU) No 1025/2012"
                    '<NOTE NOTE.ID="E0001">'
                    "<P>Regulation of 25 October 2012 (OJ L 316, p. 12).</P></NOTE>"
                    " applies."
                ),
            )
        )
    )
    sub = doc.node(f"{A}/art_40.subpara_1")
    assert sub.text == "Regulation (EU) No 1025/2012 applies."
    assert sub.notes == ("Regulation of 25 October 2012 (OJ L 316, p. 12).",)


def test_inline_rendering() -> None:
    doc = parse(
        act(
            article(
                "051",
                "Article 51",
                None,
                alinea(
                    'greater than 10<HT TYPE="SUP">25</HT> and H<HT TYPE="SUB">2</HT>O, '
                    'fines of EUR <FT TYPE="NUMBER">35000000</FT> or <FT TYPE="NUMBER">1500</FT>, '
                    '<HT TYPE="ITALIC">mutatis mutandis</HT>, '
                    '<QUOT.START CODE="00AB"/>quoted<QUOT.END CODE="00BB"/>, '
                    "soft\u00adhyphen and\u00a0no-break\n  spaces."
                ),
            )
        )
    )
    assert doc.node(f"{A}/art_51.subpara_1").text == (
        "greater than 10^25 and H_2O, fines of EUR 35 000 000 or 1500, mutatis mutandis, "
        "\u00abquoted\u00bb, softhyphen and no-break spaces."
    )


# -- amendments ------------------------------------------------------------------------


def amendments(doc: object, node: str) -> list[tuple[str, str]]:
    return [(a.action, a.scope) for a in doc.node(f"{A}/{node}").amendments]  # type: ignore[attr-defined]


def test_an_inserted_article_is_inserted_whole_with_its_content() -> None:
    doc = parse(
        consolidated(
            article("004", "Article 4", None, alinea("Old.")),
            mdfo("1", "INSERTED", loc="AR:1;PT:6")
            + article("004A", "Article 4a", "New", alinea("New."))
            + mdfc("1"),
        )
    )
    assert amendments(doc, "art_4a") == [("inserted", "whole")]
    assert amendments(doc, "art_4a.subpara_1") == [("inserted", "whole")]
    assert amendments(doc, "art_4") == []
    amendment = doc.node(f"{A}/art_4a").amendments[0]
    assert (amendment.amending_act, amendment.location, amendment.implicit) == (
        "32099R0002",
        "AR:1;PT:6",
        False,
    )


def test_a_range_across_elements_marks_only_what_it_covers() -> None:
    """Article 58(1): the label and the introduction are replaced, the points are not."""
    doc = parse(
        consolidated(
            article(
                "058",
                "Article 58",
                None,
                f'<PARAG IDENTIFIER="058.001">{mdfo("1")}<NO.PARAG>1.</NO.PARAG>'
                f"<ALINEA><P>New intro:</P>{mdfc('1')}"
                + lst(
                    item("(a)", "untouched;"),
                    "<ITEM><NP><NO.P>(b)</NO.P><TXT>end"
                    f"{mdfo('2', level='TEXT', command='IMPLICIT')};{mdfc('2')}</TXT></NP></ITEM>",
                    mdfo("3", "INSERTED") + item("(c)", "inserted.") + mdfc("3"),
                )
                + "</ALINEA></PARAG>",
            )
        )
    )
    assert amendments(doc, "art_58") == []
    assert amendments(doc, "art_58.para_1") == [("replaced", "part")]
    assert amendments(doc, "art_58.para_1.subpara_1") == [("replaced", "part")]
    assert amendments(doc, "art_58.para_1.subpara_1.point_a") == []
    assert amendments(doc, "art_58.para_1.subpara_1.point_b") == [("replaced", "part")]
    assert doc.node(f"{A}/art_58.para_1.subpara_1.point_b").amendments[0].implicit
    assert amendments(doc, "art_58.para_1.subpara_1.point_c") == [("inserted", "whole")]


def test_a_deleted_paragraph_is_kept_without_text() -> None:
    doc = parse(
        consolidated(
            article(
                "010",
                "Article 10",
                None,
                parag("010.004", "4.", alinea("Kept.")),
                mdfo("1", "DELETED")
                + parag("010.005", "5.", alinea(p("Deleted text:"), lst(item("(a)", "gone.")))),
                mdfc("1") + parag("010.006", "6.", alinea("Also kept.")),
            )
        )
    )
    deleted = doc.node(f"{A}/art_10.para_5")
    assert deleted.deleted
    assert (deleted.label, deleted.text, deleted.heading) == ("5.", None, None)
    assert amendments(doc, "art_10.para_5") == [("deleted", "whole")]
    assert doc.children(deleted.id) == ()
    assert doc.node(f"{A}/art_10").text == "4. Kept.\n6. Also kept."
    assert deleted.block() == []


def test_deleted_text_inside_a_node_is_removed_from_it() -> None:
    doc = parse(
        consolidated(
            article(
                "001",
                "Article 1",
                None,
                alinea(f"Kept{mdfo('1', 'DELETED', level='TEXT')} and removed{mdfc('1')}."),
            )
        )
    )
    node = doc.node(f"{A}/art_1.subpara_1")
    assert (node.text, node.deleted) == ("Kept.", False)
    assert amendments(doc, "art_1.subpara_1") == [("deleted", "part")]


def test_a_replaced_heading_marks_the_article_in_part() -> None:
    doc = parse(
        consolidated(
            article(
                "075",
                "Article 75",
                None,
                mdfo("1") + "<STI.ART>New heading</STI.ART>" + mdfc("1"),
                alinea("Text."),
            )
        )
    )
    assert amendments(doc, "art_75") == [("replaced", "part")]
    assert doc.node(f"{A}/art_75").heading == "New heading"
    assert amendments(doc, "art_75.subpara_1") == []


def test_an_inserted_annex() -> None:
    doc = parse(
        consolidated(
            article("001", "Article 1", None, alinea("Text.")),
            annexes=(
                mdfo("1", "INSERTED")
                + cons_annex("ANNEX XIV", None, np_("1.", "Codes."))
                + mdfc("1"),
            ),
        )
    )
    assert amendments(doc, "anx_XIV") == [("inserted", "whole")]
    assert amendments(doc, "anx_XIV.point_1") == [("inserted", "whole")]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (mdfo("1") + alinea("x"), "never closed"),
        (alinea("x") + mdfc("1"), "closed but not open"),
        (mdfo("1", "MOVED") + alinea("x") + mdfc("1"), "unknown value"),
        (mdfo("1", command="TACIT") + alinea("x") + mdfc("1"), "unknown value"),
        (mdfo("1", mod_level="2") + alinea("x") + mdfc("1"), "amendment of an amendment"),
        (mdfo("1") + mdfo("1") + alinea("x") + mdfc("1") + mdfc("1"), "opened twice"),
        (
            '<?CLG.MDFO ID="O1" ACTION="REPLACED" LEVEL="TEXT" COMMAND="EXPLICIT" '
            'ACTIVE.DOC="x" COLOUR="red"?>',
            "attributes",
        ),
    ],
)
def test_malformed_amendment_markers_are_refused(body: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse(consolidated(article("001", "Article 1", None, body)))


# -- refusals ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (article("001", "Article 1", None, "<FOO/>"), "unexpected <FOO> in <ARTICLE>"),
        (
            article("001", "Article 1", None, "stray text", alinea("x")),
            "unexpected text after <TI.ART>",
        ),
        (
            article("001", "Article 1", None, alinea("<FOO>x</FOO>")),
            "unexpected <FOO> in subparagraph",
        ),
        (
            article("001", "Article 1", None, alinea("x<?OTHER a='1'?>")),
            r"unknown processing instruction <\?OTHER\?>",
        ),
        (
            article("001", "Article 1", None, alinea(f"<TXT>{lst(item('(a)', 'x'))}</TXT>")),
            r"structure \['LIST'",
        ),
        (
            article(
                "001", "Article 1", None, alinea(p("x"), lst(item("(a)", "y"), item("(a)", "z")))
            ),
            "duplicate identifier",
        ),
        (article("001", "Article 1", None, alinea("")), "article without text"),
        ("<ARTICLE><TI.ART>Article 1</TI.ART></ARTICLE>", "without IDENTIFIER"),
    ],
)
def test_unknown_shapes_are_refused(body: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse(act(body))


def test_page_breaks_are_ignored() -> None:
    doc = parse(
        act(article("001", "Article 1", None, "<?PAGE NO='3'?>", alinea("x<?PAGE NO='4'?>y")))
    )
    assert doc.node(f"{A}/art_1").text == "xy"


def test_an_unsupported_schema_is_refused() -> None:
    main = formex_act(
        title() + enacting(article("001", "Article 1", None, alinea("x"))), schema="formex-05.xd"
    )
    with pytest.raises(ParseError, match="unsupported Formex schema"):
        parse(main)


def test_an_unreferenced_file_is_refused() -> None:
    with pytest.raises(ParseError, match="no document refers to it"):
        parse(act(article("001", "Article 1", None, alinea("x"))), extra={"Z.xml": b"<ANNEX/>"})


def test_an_included_file_is_read_where_it_is_quoted() -> None:
    quoted = '<QUOT.S><INCL.ELEMENT FILEREF="INC.xml" TYPE="FORMEX.DOC"/></QUOT.S>'
    annex_xiv = formex_act(
        "<TITLE><TI><P>ANNEX XIV</P></TI></TITLE><CONTENTS><P>Codes.</P></CONTENTS>", root="ANNEX"
    )
    doc = parse(
        act(article("001", "Article 1", None, alinea(p("The following Annex is added:"), quoted))),
        included={"INC.xml": annex_xiv},
    )
    assert doc.node(f"{A}/art_1").text == "The following Annex is added:\nANNEX XIV\nCodes."
    with pytest.raises(ParseError, match=r"included file 'INC\.xml' missing"):
        parse(act(article("001", "Article 1", None, alinea(quoted))))
