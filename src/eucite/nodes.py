"""The node model (ADR-0012): what the parser produces and the dataset ships.

A node is one addressable unit of an act — an article, a paragraph, a point, an
annex, a recital — with its identifier (ADR-0002), its text in one language,
and the amendments the source records on it.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, PrivateAttr, computed_field

__all__ = [
    "Action",
    "Amendment",
    "Document",
    "IdBasis",
    "Node",
    "NodeType",
    "Provenance",
    "Scope",
    "compose_block",
]

Action = Literal["replaced", "inserted", "deleted"]
Scope = Literal["whole", "part"]
IdBasis = Literal["source", "label", "position"]


class NodeType(StrEnum):
    ACT = "act"
    CHAPTER = "chapter"
    SECTION = "section"
    ARTICLE = "article"
    PARAGRAPH = "paragraph"
    SUBPARAGRAPH = "subparagraph"
    POINT = "point"
    INDENT = "indent"
    ANNEX = "annex"
    TABLE = "table"
    RECITAL = "recital"
    CITATION = "citation"


class Amendment(BaseModel):
    """An amendment the consolidated text records on a node.

    Read from the source's own markers (``CLG.MDFO``), never inferred.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Action
    scope: Scope
    """``whole``: all the content of the node is within the amended range.
    ``part``: some of the node's own content is — its label, its heading, or text
    that does not belong to one of its children."""
    amending_act: str
    """CELEX number of the amending act."""
    location: str
    """Where in the amending act, as the source writes it (``AR:1;PT:23;PT:b``:
    Article 1, point 23, point b)."""
    implicit: bool
    """The amending act does not state this change; the consolidation applies
    it as a consequence of one it does state (typically the punctuation before
    an inserted point)."""


class Node(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    type: NodeType
    parent: str | None
    order: int
    """Position in document order. Identifiers do not sort in reading order."""
    label: str | None
    """As printed, in the node's language: ``Article 6``, ``3.``, ``(a)``, ``a)``."""
    heading: str | None
    text: str | None
    """The text of the node, children included, one block per line. ``None`` for
    the act, its chapters and sections, whose text is that of their articles, and
    for deleted nodes."""
    notes: tuple[str, ...] = ()
    """Footnotes, in order. Not part of ``text``."""
    id_provenance: Literal["inherited", "derived"]
    id_basis: IdBasis
    source_ref: str | None
    """For inherited identifiers, the identifier as the source spells it."""
    amendments: tuple[Amendment, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def deleted(self) -> bool:
        """Deleted by an amendment. The node is kept, without text, so that a
        citation of it can be told apart from a citation of nothing."""
        return any(a.action == "deleted" and a.scope == "whole" for a in self.amendments)

    def block(self) -> list[str]:
        """The lines this node contributes to its parent's text (none if deleted)."""
        if self.deleted:
            return []
        return compose_block(self.label, self.heading, self.text.split("\n") if self.text else [])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def text_sha256(self) -> str | None:
        if self.text is None:
            return None
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def compose_block(label: str | None, heading: str | None, lines: list[str]) -> list[str]:
    """How a node reads inside its parent's text.

    A heading goes on its own line after the label (``Section A List of …``);
    without a heading the label opens the first line (``(a) the AI system …``).
    """
    head = " ".join(x for x in (label, heading) if x)
    if heading:
        return [head, *lines]
    if head and lines:
        return [f"{head} {lines[0]}", *lines[1:]]
    return [head] if head else list(lines)


class Provenance(BaseModel):
    """Which payload a document was parsed from (ADR-0010)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_work: str
    manifestation: str
    accept: str
    accept_language: str
    url: str
    retrieved_at: AwareDatetime
    source_sha256: str
    canonical_sha256: str | None
    canonical_version: int | None


class Document(BaseModel):
    """One work in one language, as a sequence of nodes in document order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    work: str
    """CELEX number of the work parsed: the base act, a consolidated version, an
    amending act."""
    act: str
    """CELEX number of the act the nodes belong to: the prefix of every
    identifier. A consolidated version represents its base act."""
    language: str
    schema_location: str
    nodes: tuple[Node, ...]
    provenance: Provenance | None = None

    _by_id: dict[str, Node] = PrivateAttr(default_factory=dict)
    _children: dict[str | None, list[Node]] = PrivateAttr(default_factory=dict)

    def model_post_init(self, context: Any, /) -> None:
        for n in self.nodes:
            self._by_id[n.id] = n
            self._children.setdefault(n.parent, []).append(n)

    def node(self, node_id: str) -> Node:
        return self._by_id[node_id]

    def children(self, node_id: str) -> tuple[Node, ...]:
        return tuple(self._children.get(node_id, ()))
