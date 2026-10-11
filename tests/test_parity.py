"""Language parity (S6): divergences are reported, never repaired.

The definition of done of S6 asks that a divergence introduced on purpose make
the check fail. Each test below introduces one.
"""

from __future__ import annotations

import pytest

from eucite.nodes import Amendment, Document, NodeType
from eucite.parity import ASPECTS, ParityError, compare, require_parity
from tests.builders import act, alinea, article, consolidated, item, lst, mdfc, mdfo, p, parse

A = "32099R0001"


def bilingual(english: str, italian: str, *, work: str = A) -> list[Document]:
    return [parse(english, work=work, language="eng"), parse(italian, work=work, language="ita")]


def definitions(*points: tuple[str, str]) -> str:
    body = alinea(
        p("For the purposes of this Regulation:"), lst(*(item(lb, t) for lb, t in points))
    )
    return act(article("003", "Article 3", "Definitions", body))


def definizioni(*points: tuple[str, str]) -> str:
    body = alinea(p("Ai fini del presente regolamento:"), lst(*(item(lb, t) for lb, t in points)))
    return act(article("003", "Articolo 3", "Definizioni", body))


def test_the_same_structure_in_two_languages_is_in_parity() -> None:
    parity = compare(
        bilingual(
            definitions(("(14)", "'SME' means;"), ("(14a)", "'SMC' means.")),
            definizioni(("14)", "«PMI»:"), ("14 bis)", "«SMC»:")),
        )
    )
    assert parity.ok
    assert (parity.work, parity.languages, parity.nodes) == (A, ("eng", "ita"), 5)


def test_a_point_missing_in_one_language() -> None:
    """Reported where it is missing, and where it changes the shape of the text."""
    parity = compare(
        bilingual(
            definitions(("(14)", "'SME' means;"), ("(14a)", "'SMC' means.")),
            definizioni(("14)", "\u00abPMI\u00bb:")),
        )
    )
    assert [(d.node.split("/")[1], d.aspect) for d in parity.divergences] == [
        ("art_3.subpara_1.point_14a", "presence"),
        ("art_3", "blocks"),
        ("art_3.subpara_1", "blocks"),
    ]
    assert parity.divergences[0].values == (("eng", "present"), ("ita", "absent"))
    assert parity.divergences[1].values == (("eng", "3"), ("ita", "2"))


def test_a_label_numbered_differently_is_two_divergences() -> None:
    """``14 ter`` is ``14b``: if one language printed ``14 ter`` where the other
    prints ``(14a)``, the identifiers differ and neither is silently renamed."""
    parity = compare(
        bilingual(
            definitions(("(14)", "x;"), ("(14a)", "y.")),
            definizioni(("14)", "x;"), ("14 ter)", "y.")),
        )
    )
    assert {(d.node.rsplit(".", 1)[-1], d.aspect) for d in parity.divergences} == {
        ("point_14a", "presence"),
        ("point_14b", "presence"),
    }


def test_a_different_shape_of_text() -> None:
    parity = compare(
        bilingual(
            act(article("001", "Article 1", None, alinea("One block."))),
            act(article("001", "Articolo 1", None, alinea(p("Primo blocco."), p("Secondo.")))),
        )
    )
    assert {(d.node, d.aspect) for d in parity.divergences} == {
        (f"{A}/art_1", "blocks"),
        (f"{A}/art_1.subpara_1", "blocks"),
    }


def test_an_amendment_recorded_in_one_language_only() -> None:
    parity = compare(
        bilingual(
            consolidated(
                mdfo("1", "INSERTED") + article("004", "Article 4", None, alinea("x.")) + mdfc("1")
            ),
            consolidated(article("004", "Articolo 4", None, alinea("x."))),
            work="02099R0001-20990101",
        )
    )
    assert {(d.node, d.aspect) for d in parity.divergences} == {
        (f"{A}/art_4", "amendments"),
        (f"{A}/art_4.subpara_1", "amendments"),
    }


def test_a_different_order() -> None:
    first = act(
        article("001", "Article 1", None, alinea("x.")),
        article("002", "Article 2", None, alinea("y.")),
    )
    swapped = act(
        article("002", "Articolo 2", None, alinea("y.")),
        article("001", "Articolo 1", None, alinea("x.")),
    )
    parity = compare(bilingual(first, swapped))
    assert [d.aspect for d in parity.divergences] == ["order"]
    assert parity.divergences[0].values == (("eng", f"{A}/art_1"), ("ita", f"{A}/art_2"))


@pytest.mark.parametrize("aspect", sorted(ASPECTS))
def test_every_aspect_is_compared(aspect: str) -> None:
    """Change one aspect of one node in one language: exactly that is reported."""
    english, italian = bilingual(
        definitions(("(1)", "'AI system' means a system;")),
        definizioni(("1)", "«sistema di IA»: un sistema;")),
    )
    target = f"{A}/art_3.subpara_1.point_1"
    changes: dict[str, dict[str, object]] = {
        "type": {"type": NodeType.INDENT},
        "parent": {"parent": f"{A}/art_3"},
        "id_provenance": {"id_provenance": "inherited"},
        "id_basis": {"id_basis": "position"},
        "source_ref": {"source_ref": "003.001"},
        "amendments": {
            "amendments": (
                Amendment(
                    action="replaced", scope="part", amending_act="x", location="y", implicit=False
                ),
            )
        },
        "deleted": {
            "amendments": (
                Amendment(
                    action="deleted", scope="whole", amending_act="x", location="y", implicit=False
                ),
            )
        },
        "has_label": {"label": None},
        "has_heading": {"heading": "A heading"},
        "blocks": {"text": "«sistema di IA»:\nun sistema;"},
        "notes": {"notes": ("OJ L 1, p. 1.",)},
    }
    nodes = tuple(
        n.model_copy(update=changes[aspect]) if n.id == target else n for n in italian.nodes
    )
    altered = Document(
        work=italian.work,
        act=italian.act,
        language=italian.language,
        schema_location=italian.schema_location,
        nodes=nodes,
    )
    reported = {(d.node, d.aspect) for d in compare([english, altered]).divergences}
    expected = {(target, aspect)}
    if aspect == "deleted":
        expected.add((target, "amendments"))
    assert reported == expected


def test_require_parity_names_the_divergences() -> None:
    documents = bilingual(
        definitions(("(14)", "x;"), ("(14a)", "y.")),
        definizioni(("14)", "x;")),
    )
    with pytest.raises(
        ParityError, match=r"point_14a — presence differs \(eng: present; ita: absent\)"
    ):
        require_parity(documents)


def test_only_expressions_of_one_work_are_compared() -> None:
    english = parse(act(article("001", "Article 1", None, alinea("x."))), language="eng")
    other = parse(
        act(article("001", "Article 1", None, alinea("x."))), work="32099R0002", language="ita"
    )
    with pytest.raises(ValueError, match="one work"):
        compare([english, other])
    with pytest.raises(ValueError, match="appears twice"):
        compare([english, english])
