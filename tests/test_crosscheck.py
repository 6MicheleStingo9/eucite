"""Inherited identifiers checked against the identifiers of the XHTML."""

from __future__ import annotations

from eucite.crosscheck import crosscheck, xhtml_identifiers
from eucite.nodes import Document
from tests.builders import act, alinea, article, division, parag, parse
from tests.doubles import xhtml


def sample() -> Document:
    return parse(
        act(
            division(
                "CHAPTER I",
                "GENERAL PROVISIONS",
                article("001", "Article 1", "Subject matter", parag("001.001", "1.", alinea("x."))),
            )
        )
    )


def page(*ids: str) -> bytes:
    return xhtml("".join(f'<div id="{i}">x</div>' for i in ids))


def test_identifiers_are_read_from_every_element() -> None:
    assert xhtml_identifiers(page("art_1", "id-3f2a", "001.001")) == {"art_1", "id-3f2a", "001.001"}


def test_every_inherited_identifier_found() -> None:
    check = crosscheck(sample(), xhtml_identifiers(page("cpt_I", "art_1", "art_1.tit_1", "id-x")))
    assert check.ok
    assert (check.checked, check.unchecked) == (2, 1)  # the paragraph cannot be checked here


def test_paragraphs_are_checked_where_the_xhtml_carries_them() -> None:
    check = crosscheck(sample(), xhtml_identifiers(page("cpt_I", "art_1", "001.002")))
    assert check.missing == ("001.001",)
    assert check.unchecked == 0
    assert not check.ok


def test_an_inherited_identifier_missing_from_eurlex() -> None:
    check = crosscheck(sample(), xhtml_identifiers(page("cpt_I")))
    assert check.missing == ("art_1",)


def test_an_eurlex_identifier_without_a_node() -> None:
    check = crosscheck(sample(), xhtml_identifiers(page("cpt_I", "art_1", "art_2", "rct_7")))
    assert check.unmatched == ("art_2", "rct_7")
    assert not check.ok
