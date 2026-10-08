"""Printed labels to identifier numbers (ADR-0002): every rule, and refusal otherwise."""

from __future__ import annotations

import pytest

from eucite.labels import (
    LabelError,
    annex_number,
    annex_section,
    article_number,
    division_number,
    identifier_number,
    point_number,
)


@pytest.mark.parametrize(
    ("label", "number"),
    [
        ("(a)", "a"),
        ("a)", "a"),
        ("(iv)", "iv"),
        ("iv)", "iv"),
        ("(1)", "1"),
        ("1)", "1"),
        ("1.", "1"),
        ("(180)", "180"),
        ("3.1.", "3-1"),
        ("a.", "a"),
        ("(14a)", "14a"),
        ("14 bis)", "14a"),
        ("(14 ter)", "14b"),
        ("(ba)", "ba"),
        ("b bis)", "ba"),
        ("d bis)", "da"),
        ("b ter)", "bb"),
        ("1a.", "1a"),
        ("1 bis.", "1a"),
        ("1 quinquies.", "1d"),
        ("1 sexies.", "1e"),
        ("  ( a )  ", "a"),
        ("(01)", "1"),
    ],
)
def test_point_labels(label: str, number: str) -> None:
    assert point_number(label) == number


@pytest.mark.parametrize(
    "label", ["", "\u2014", "-", "\u2022", "(a", "a", "(a)(b)", "14 undecies)", "(\u00e9)"]
)
def test_unknown_point_labels_are_refused(label: str) -> None:
    with pytest.raises(LabelError, match="unrecognised label"):
        point_number(label)


@pytest.mark.parametrize(
    ("identifier", "number"),
    [("006", "6"), ("004A", "4a"), ("075D", "75d"), ("006.003", "3"), ("006.001A", "1a")],
)
def test_formex_identifiers(identifier: str, number: str) -> None:
    assert identifier_number(identifier) == number


@pytest.mark.parametrize("identifier", ["", "6a", "006.", "art_6"])
def test_unknown_identifiers_are_refused(identifier: str) -> None:
    with pytest.raises(LabelError):
        identifier_number(identifier)


@pytest.mark.parametrize(
    ("label", "number"),
    [
        ("Article 6", "6"),
        ("Article 4a", "4a"),
        ("Articolo 4 bis", "4a"),
        ("Articolo 75 quinquies", "75d"),
        ("Articolo\u00a0113", "113"),
    ],
)
def test_article_labels(label: str, number: str) -> None:
    assert article_number(label) == number


@pytest.mark.parametrize("label", ["Art. 6", "Artikel 6", "Article", "Article six"])
def test_unknown_article_labels_are_refused(label: str) -> None:
    with pytest.raises(LabelError):
        article_number(label)


def test_division_labels() -> None:
    assert division_number("CHAPTER III", nested=False) == "III"
    assert division_number("CAPO XIII", nested=False) == "XIII"
    assert division_number("SECTION 2", nested=True) == "2"
    assert division_number("SEZIONE 4", nested=True) == "4"
    with pytest.raises(LabelError):
        division_number("SECTION 2", nested=False)
    with pytest.raises(LabelError):
        division_number("CHAPTER 3", nested=False)


def test_annex_labels() -> None:
    assert annex_number("ANNEX XIV") == "XIV"
    assert annex_number("ALLEGATO III") == "III"
    with pytest.raises(LabelError):
        annex_number("ANNEX")


@pytest.mark.parametrize(
    ("title", "split"),
    [
        (
            "Section A. List of Union harmonisation legislation",
            ("Section A", "a", "List of Union harmonisation legislation"),
        ),
        (
            "Section B \u2014 Information to be submitted",
            ("Section B", "b", "Information to be submitted"),
        ),
        ("Sezione B \u2013 Elenco di altre", ("Sezione B", "b", "Elenco di altre")),
        ("Sezione A - Informazioni", ("Sezione A", "a", "Informazioni")),
        ("Section 1", ("Section 1", "1", "")),
    ],
)
def test_annex_section_titles(title: str, split: tuple[str, str, str]) -> None:
    assert annex_section(title) == split


@pytest.mark.parametrize("title", ["Introduction", "Section Alpha", "Part A. List"])
def test_unknown_annex_section_titles_are_refused(title: str) -> None:
    with pytest.raises(LabelError):
        annex_section(title)
