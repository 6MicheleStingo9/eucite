"""The source registry: which works, languages and manifestations the corpus needs."""

from __future__ import annotations

import pytest

from eucite.sources import LANGUAGES, WORKS, Manifestation, Role, all_sources, work


def test_corpus_needs_twelve_payloads() -> None:
    """Three works, two languages, two manifestations (ADR-0001)."""
    keys = all_sources()
    assert len(keys) == len(set(keys)) == 12
    assert keys == sorted(keys)


def test_composition_has_one_work_per_role() -> None:
    assert sorted(w.role for w in WORKS) == sorted(Role)
    assert work("02024R1689-20260727").role is Role.CONSOLIDATED


def test_italian_and_english_in_iso_639_3() -> None:
    assert set(LANGUAGES) == {"ita", "eng"}


def test_formex_is_negotiated_as_a_bundle() -> None:
    """The single-document form is the request that misled the first spike."""
    assert Manifestation.FORMEX.accept == "application/zip;mtype=fmx4"
    assert Manifestation.FORMEX.accept != "application/xml;type=fmx4"
    assert Manifestation.XHTML.accept == "application/xhtml+xml"


def test_unknown_work_names_the_registered_ones() -> None:
    with pytest.raises(ValueError, match="32024R1689"):
        work("32016R0679")


def test_source_key_reads_as_a_path() -> None:
    key = all_sources()[0]
    assert str(key) == f"{key.celex}/{key.lang}/{key.manifestation}"
