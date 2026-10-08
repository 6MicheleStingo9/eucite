"""Properties of the parser on generated documents (plan S3).

Hypothesis builds articles of random shape — paragraphs or not, subparagraphs
with or without lists, nested points — and wraps random elements in amendment
markers, deletions included. Whatever the shape, the invariants of ADR-0012
must hold: unique identifiers, valid parents, children that compose their
parent's text, no word lost or added, deletions applied.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

from hypothesis import given, settings
from hypothesis import strategies as st

from eucite.nodes import Document
from tests.builders import alinea, article, consolidated, mdfc, mdfo, p, parse
from tests.invariants import assert_composition, assert_tree

WORD = re.compile(r"\w+")
VOCABULARY = ("system", "provider", "shall", "market", "data", "risk", "union", "notified", "body")
ACTIONS = (None, None, None, "REPLACED", "INSERTED", "DELETED")


@dataclass
class Element:
    """A generated element: its XML, the words it contributes, its node identifier."""

    xml: str
    words: list[str]
    node: str
    action: str | None
    children: list[Element] = field(default_factory=list)


_ids = itertools.count()


def wrap(xml: str, action: str | None) -> str:
    if action is None:
        return xml
    ident = str(next(_ids))
    return mdfo(ident, action) + xml + mdfc(ident)


def kept(words: list[str], action: str | None) -> list[str]:
    return [] if action == "DELETED" else words


sentences = st.lists(st.sampled_from(VOCABULARY), min_size=1, max_size=5).map(
    lambda ws: " ".join(ws)
)


@st.composite
def points(draw: st.DrawFn, parent: str, depth: int) -> list[Element]:
    out = []
    for letter in "abc"[: draw(st.integers(1, 3))]:
        node = f"{parent}.point_{letter}"
        text = draw(sentences) + ";"
        nested: list[Element] = []
        if depth < 2 and draw(st.booleans()):
            nested = draw(points(node, depth + 1))
        inner = "".join(e.xml for e in nested)
        sub = f'<P><LIST TYPE="alpha">{inner}</LIST></P>' if nested else ""
        action = draw(st.sampled_from(ACTIONS))
        xml = wrap(f"<ITEM><NP><NO.P>({letter})</NO.P><TXT>{text}</TXT>{sub}</NP></ITEM>", action)
        words = [letter, *WORD.findall(text), *(w for e in nested for w in e.words)]
        out.append(Element(xml, kept(words, action), node, action, nested))
    return out


@st.composite
def subparagraphs(draw: st.DrawFn, parent: str) -> list[Element]:
    out = []
    for position in range(1, draw(st.integers(1, 3)) + 1):
        node = f"{parent}.subpara_{position}"
        intro = draw(sentences)
        listed: list[Element] = draw(st.one_of(st.just([]), points(node, 0)))
        if listed:
            inner = "".join(e.xml for e in listed)
            body = alinea(p(intro + ":"), f'<LIST TYPE="alpha">{inner}</LIST>')
        else:
            body = alinea(intro + ".")
        action = draw(st.sampled_from(ACTIONS))
        words = WORD.findall(intro) + [w for e in listed for w in e.words]
        out.append(Element(wrap(body, action), kept(words, action), node, action, listed))
    return out


@st.composite
def articles(draw: st.DrawFn) -> list[Element]:
    out = []
    for number in range(1, draw(st.integers(1, 3)) + 1):
        node = f"art_{number}"
        children: list[Element]
        if draw(st.booleans()):
            children = []
            for k in range(1, draw(st.integers(1, 3)) + 1):
                para_node = f"{node}.para_{k}"
                subs = draw(subparagraphs(para_node))
                action = draw(st.sampled_from(ACTIONS))
                xml = (
                    f'<PARAG IDENTIFIER="{number:03d}.{k:03d}"><NO.PARAG>{k}.</NO.PARAG>'
                    f"{''.join(e.xml for e in subs)}</PARAG>"
                )
                words = [str(k), *(w for e in subs for w in e.words)]
                children.append(
                    Element(wrap(xml, action), kept(words, action), para_node, action, subs)
                )
        else:
            children = draw(subparagraphs(node))
        xml = article(f"{number:03d}", f"Article {number}", "Heading", *(e.xml for e in children))
        words = ["Article", str(number), "Heading", *(w for e in children for w in e.words)]
        out.append(Element(xml, words, node, None, children))
    return out


def generated(elements: list[Element]) -> Document:
    return parse(consolidated(*(e.xml for e in elements)))


def walk(elements: list[Element], deleted_above: bool = False) -> list[tuple[Element, bool]]:
    out = []
    for e in elements:
        out.append((e, deleted_above))
        out.extend(walk(e.children, deleted_above or e.action == "DELETED"))
    return out


PROPERTIES = settings(max_examples=150, deadline=None)


@PROPERTIES
@given(articles())
def test_identifiers_are_unique_and_parents_precede_children(elements: list[Element]) -> None:
    assert_tree(generated(elements))


@PROPERTIES
@given(articles())
def test_children_compose_the_text_of_their_parent(elements: list[Element]) -> None:
    assert_composition(generated(elements))


@PROPERTIES
@given(articles())
def test_no_word_is_lost_or_added(elements: list[Element]) -> None:
    doc = generated(elements)
    for element in elements:
        node = doc.node(f"{doc.act}/{element.node}")
        text = " ".join(x for x in (node.label, node.heading, node.text) if x)
        assert WORD.findall(text) == element.words


@PROPERTIES
@given(articles())
def test_amendments_land_on_the_nodes_they_wrap(elements: list[Element]) -> None:
    doc = generated(elements)
    present = {n.id for n in doc.nodes}
    for element, deleted_above in walk(elements):
        node_id = f"{doc.act}/{element.node}"
        if deleted_above:
            assert node_id not in present
            continue
        node = doc.node(node_id)
        actions = {a.action for a in node.amendments if a.scope == "whole"}
        if element.action is not None:
            assert element.action.lower() in actions
        if element.action == "DELETED":
            assert node.deleted
            assert node.text is None
            assert doc.children(node_id) == ()
        else:
            assert not node.deleted
