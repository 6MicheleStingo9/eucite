"""Language parity (S6): one act, one structure, in every language.

The Italian and English versions of a provision are one node in two
expressions (ADR-0002). What may differ between languages is what is written
in them: the printed label, the heading, the text. Everything else must
coincide, node by node and in the same order: the identifier, the type, the
parent, the declared provenance of the identifier, the amendments, the
deletion, the number of footnotes, and the shape of the text — whether there
is a label, a heading, a text, and how many blocks the text has.

Parity is checked, never repaired. A divergence names the node and what
differs in each language, and the build fails on it: a dataset in which a
citation resolves in one language and not in the other is not published.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from eucite.nodes import Document, Node

__all__ = ["ASPECTS", "Divergence", "Parity", "ParityError", "compare", "require_parity"]


def _blocks(node: Node) -> int | None:
    return None if node.text is None else node.text.count("\n") + 1


# What must coincide between languages, and how to read it from a node.
ASPECTS: dict[str, Callable[[Node], object]] = {
    "type": lambda n: n.type.value,
    "parent": lambda n: n.parent,
    "id_provenance": lambda n: n.id_provenance,
    "id_basis": lambda n: n.id_basis,
    "source_ref": lambda n: n.source_ref,
    "amendments": lambda n: tuple(
        (a.action, a.scope, a.amending_act, a.location, a.implicit) for a in n.amendments
    ),
    "deleted": lambda n: n.deleted,
    "has_label": lambda n: n.label is not None,
    "has_heading": lambda n: n.heading is not None,
    "blocks": _blocks,
    "notes": lambda n: len(n.notes),
}


@dataclass(frozen=True)
class Divergence:
    node: str
    aspect: str
    """``presence``, ``order``, or one of :data:`ASPECTS`."""
    values: tuple[tuple[str, str], ...]
    """What each language has, as ``(language, value)``."""

    def __str__(self) -> str:
        values = "; ".join(f"{lang}: {value}" for lang, value in self.values)
        return f"{self.node} — {self.aspect} differs ({values})"


@dataclass(frozen=True)
class Parity:
    work: str
    languages: tuple[str, ...]
    nodes: int
    divergences: tuple[Divergence, ...]

    @property
    def ok(self) -> bool:
        return not self.divergences


class ParityError(Exception):
    def __init__(self, parity: Parity, shown: int = 10) -> None:
        lines = [str(d) for d in parity.divergences[:shown]]
        more = len(parity.divergences) - shown
        if more > 0:
            lines.append(f"… and {more} more")
        languages = ", ".join(parity.languages)
        super().__init__(
            f"{parity.work}: the languages ({languages}) diverge in "
            f"{len(parity.divergences)} place(s):\n  " + "\n  ".join(lines)
        )
        self.parity = parity


def compare(documents: Sequence[Document]) -> Parity:
    """Compare the expressions of one work in several languages."""
    if not documents:
        raise ValueError("nothing to compare")
    work = documents[0].work
    if any(d.work != work for d in documents):
        raise ValueError(f"parity compares one work: {sorted({d.work for d in documents})}")
    languages = tuple(d.language for d in documents)
    if len(set(languages)) != len(languages):
        raise ValueError(f"a language appears twice: {languages}")

    divergences: list[Divergence] = []
    ids = [{n.id for n in d.nodes} for d in documents]
    common = set.intersection(*ids)
    for node_id in sorted(set.union(*ids) - common):
        presence = tuple(
            (lang, "present" if node_id in present else "absent")
            for lang, present in zip(languages, ids, strict=True)
        )
        divergences.append(Divergence(node_id, "presence", presence))

    orders = [[n.id for n in d.nodes if n.id in common] for d in documents]
    if any(order != orders[0] for order in orders[1:]):
        first = next(i for i, at in enumerate(zip(*orders, strict=True)) if len(set(at)) > 1)
        shown = tuple((lang, order[first]) for lang, order in zip(languages, orders, strict=True))
        divergences.append(Divergence(orders[0][first], "order", shown))

    by_id = [{n.id: n for n in d.nodes} for d in documents]
    for node_id in orders[0]:
        nodes = [index[node_id] for index in by_id]
        for aspect, read in ASPECTS.items():
            values = [read(n) for n in nodes]
            if any(v != values[0] for v in values[1:]):
                shown = tuple((lang, repr(v)) for lang, v in zip(languages, values, strict=True))
                divergences.append(Divergence(node_id, aspect, shown))

    return Parity(work, languages, len(common), tuple(divergences))


def require_parity(documents: Sequence[Document]) -> Parity:
    """:func:`compare`, raising :class:`ParityError` on any divergence."""
    parity = compare(documents)
    if not parity.ok:
        raise ParityError(parity)
    return parity
