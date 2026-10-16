"""What a citation designates, in a version of an act (S7b, ADR-0011).

The resolver reads the references of a citation (:mod:`eucite.citations`)
against the identifiers of the corpus (ADR-0002), and answers each with a
status:

- ``resolved``: the provisions designated — one, or each one of a range;
- ``ambiguous``: more than one provision fits, and all of them are returned. None
  is chosen. In the AI Act this happens to a point of Article 43(1) cited
  without its subparagraph, and to ``Article 3(1)``, which is both the first
  paragraph of Article 3 and, as commonly written, its point (1);
- ``not_found``: the act has no such provision in that version;
- ``other_act``: the citation names an act outside the corpus, or one that
  cannot be identified (``that Regulation``). It is never resolved against the
  act the text is about.

A string that is not a citation is ``unparsed``. The resolver does not judge
whether a citation is the right one for what the text says.

Where a citation is silent on a level, the resolver looks through it, and only
through it: a point cited without its subparagraph (``Article 6(3)(a)``), a
point of an annex cited without its section (``point 3.1 of Annex VII``). It
never skips a numbered level: ``Article 6(a)`` is not found, because the points
of Article 6 are inside its paragraphs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from eucite.citations import Level, Mention, Reference, Step
from eucite.dataset import read_dataset
from eucite.nodes import Document, Node
from eucite.sources import represented_act

__all__ = ["DEFAULT_ACT", "Resolution", "Resolver", "Status", "Target"]

DEFAULT_ACT = "32024R1689"
"""The act a citation belongs to when it names none: the corpus is about it."""


class Status(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    OTHER_ACT = "other_act"
    UNPARSED = "unparsed"


@dataclass(frozen=True)
class Target:
    """A provision a reference resolves to."""

    id: str
    deleted: bool
    """Deleted by an amendment: the version keeps the identifier, not the text."""
    amended_by: tuple[str, ...]
    """The acts whose amendments the version records on this provision or on a
    provision within it, read from the markers of the consolidated text. Empty
    for an act as published."""


@dataclass(frozen=True)
class Resolution:
    status: Status
    reference: Reference | None
    act: str | None
    """CELEX number of the act resolved against; ``None`` for ``other_act`` and
    ``unparsed``."""
    as_of: str | None
    """The work searched: the version of the act, or the act as published for
    recitals."""
    candidates: tuple[Target, ...] = ()
    """``resolved``: what the reference designates. ``ambiguous``: what it may
    designate. Empty otherwise."""
    within_deleted: str | None = None
    """``not_found`` because the reference lies within a provision this version
    deleted: the identifier of that provision."""


class _Version:
    """The identifiers of one work, as a tree of paths."""

    def __init__(self, work: str, nodes: Sequence[Node]) -> None:
        self.work = work
        self.act = represented_act(work)
        prefix = f"{self.act}/"
        self.nodes: dict[str, Node] = {}
        self.kids: dict[str, list[str]] = {}
        self.order: dict[str, int] = {}
        amended: dict[str, set[str]] = {}
        for index, node in enumerate(nodes):
            if not node.id.startswith(prefix):
                continue  # the act itself
            path = node.id[len(prefix) :]
            self.nodes[path] = node
            self.order[path] = index
            parent = path.rpartition(".")[0]
            self.kids.setdefault(parent, []).append(path)
            acts = {a.amending_act for a in node.amendments}
            if acts:
                parts = path.split(".")
                for depth in range(1, len(parts) + 1):
                    amended.setdefault(".".join(parts[:depth]), set()).update(acts)
        self.amended = {path: tuple(sorted(acts)) for path, acts in amended.items()}

    def target(self, path: str) -> Target:
        node = self.nodes[path]
        return Target(node.id, node.deleted, self.amended.get(path, ()))

    def numbered_group(self, path: str) -> bool:
        """An annex group numbered like a point (``3.``, ``a)``), not a worded
        section (``Section A``). Annexes cite these groups as points."""
        label = self.nodes[path].label
        return label is not None and " " not in label.strip()


def _segment(path: str) -> str:
    return path.rpartition(".")[2]


class Resolver:
    """Resolves citations against the works of a corpus.

    ``works`` maps the CELEX number of each work to its nodes, in document order
    and in any one language: identifiers do not depend on it (S6).
    """

    def __init__(self, works: Mapping[str, Sequence[Node]], *, default_act: str = DEFAULT_ACT):
        self._versions = {work: _Version(work, nodes) for work, nodes in works.items()}
        self._by_act: dict[str, list[str]] = {}
        for work in sorted(self._versions):
            self._by_act.setdefault(represented_act(work), []).append(work)
        if default_act not in self._by_act:
            raise ValueError(f"no work of {default_act} in the corpus")
        self.default_act = default_act

    @classmethod
    def from_documents(cls, documents: Iterable[Document], **kwargs: str) -> Resolver:
        return cls({d.work: d.nodes for d in documents}, **kwargs)

    @classmethod
    def from_dataset(cls, directory: Path, **kwargs: str) -> Resolver:
        """A resolver on a dataset written by ``eucite dump``, its checksums verified."""
        works: dict[str, Sequence[Node]] = {}
        for (work, _language), nodes in sorted(read_dataset(directory).items()):
            works.setdefault(work, nodes)
        return cls(works, **kwargs)

    @property
    def acts(self) -> tuple[str, ...]:
        return tuple(self._by_act)

    def in_force(self, act: str) -> str:
        """The work a citation of ``act`` is resolved against by default: its latest
        consolidated version, or the act as published if it has none."""
        works = self._by_act[act]
        consolidated = [w for w in works if w != act]
        return max(consolidated, key=lambda w: w.rpartition("-")[2]) if consolidated else act

    def resolve(self, mention: Mention, *, as_of: str | None = None) -> tuple[Resolution, ...]:
        """Resolve each reference of ``mention``.

        ``as_of`` is a work of the act the mention cites: ``32024R1689`` resolves
        against the AI Act as published rather than the text in force.
        """
        act = self.default_act if mention.act is None else mention.act.celex
        if act is None or act not in self._by_act:
            return tuple(Resolution(Status.OTHER_ACT, ref, None, None) for ref in mention.references)
        if as_of is not None and as_of not in self._by_act[act]:
            if represented_act(as_of) == act:
                raise ValueError(f"{as_of} is not in the corpus")
            as_of = None
        work = as_of or self.in_force(act)
        return tuple(self._resolve(ref, act, work) for ref in mention.references)

    def _resolve(self, ref: Reference, act: str, work: str) -> Resolution:
        if ref.steps[0].level is Level.RECITAL and act in self._by_act[act]:
            work = act  # consolidated texts have no recitals; amending acts never amend them
        version = self._versions[work]

        def answer(status: Status, paths: Iterable[str] = (), deleted: str | None = None) -> Resolution:
            ordered = sorted(set(paths), key=version.order.__getitem__)
            return Resolution(status, ref, act, work, tuple(map(version.target, ordered)), deleted)

        found, within_deleted = self._find(version, ref.steps)
        if ref.through is None:
            if not found:
                return answer(Status.NOT_FOUND, deleted=within_deleted)
            return answer(Status.RESOLVED if len(found) == 1 else Status.AMBIGUOUS, found)
        last, last_within_deleted = self._find(version, (*ref.steps[:-1], ref.through))
        if not found or not last:
            return answer(Status.NOT_FOUND, deleted=within_deleted or last_within_deleted)
        if len(found) > 1 or len(last) > 1:
            return answer(Status.AMBIGUOUS, [*found, *last])
        span = self._span(version, found[0], last[0])
        return answer(Status.RESOLVED, span) if span else answer(Status.NOT_FOUND)

    @staticmethod
    def _span(version: _Version, start: str, end: str) -> list[str]:
        """The provisions from ``start`` to ``end`` when they are siblings of one kind,
        in document order; empty otherwise (``Articles 15 to 8``)."""
        parent = start.rpartition(".")[0]
        kind = _segment(start).partition("_")[0]
        if end.rpartition(".")[0] != parent or _segment(end).partition("_")[0] != kind:
            return []
        siblings = [p for p in version.kids[parent] if _segment(p).partition("_")[0] == kind]
        i, j = siblings.index(start), siblings.index(end)
        return siblings[i : j + 1] if i <= j else []

    def _find(self, version: _Version, steps: Sequence[Step]) -> tuple[list[str], str | None]:
        current = [""]
        for step in steps:
            following = [p for container in current for p in self._step(version, container, step)]
            if not following:
                deleted = [p for p in current if p and version.nodes[p].deleted]
                return [], deleted[0] if len(current) == 1 and deleted else None
            current = list(dict.fromkeys(following))
        return current, None

    def _step(self, version: _Version, container: str, step: Step) -> list[str]:
        kids = version.kids.get(container, [])
        n = step.number
        if step.level in (Level.ARTICLE, Level.ANNEX, Level.RECITAL, Level.CHAPTER):
            return [k for k in kids if container == "" and k == f"{step.level}_{n}"]
        if step.level is Level.SECTION:
            return self._sections(version, container, n)
        if step.level is Level.SUBPARAGRAPH:
            return [k for k in kids if _segment(k) == f"subpara_{n}"]
        if step.level is Level.PARAGRAPH:
            if any(_segment(k).startswith("para_") for k in kids):
                return [k for k in kids if _segment(k) == f"para_{n}"]
            # An article without numbered paragraphs: "Article 113(3)" is its third
            # paragraph, as the act itself writes; "Article 3(44)" its point (44).
            found = [k for k in kids if _segment(k) == f"subpara_{n}"]
            if step.compact:
                found += self._points(version, container, n)
            return found
        return self._points(version, container, n)

    def _points(self, version: _Version, container: str, n: str) -> list[str]:
        """Points numbered ``n`` in ``container``, looking through its subparagraphs and,
        in an annex, its sections."""
        found = []
        for kid in version.kids.get(container, []):
            segment = _segment(kid)
            if segment == f"point_{n}":
                found.append(kid)
            elif segment.startswith("sct_"):
                if segment == f"sct_{n}" and version.numbered_group(kid):
                    found.append(kid)
                found += self._points(version, kid, n)
            elif segment.startswith("subpara_"):
                found += self._points(version, kid, n)
        return found

    def _sections(self, version: _Version, container: str, n: str) -> list[str]:
        found = []
        for kid in version.kids.get(container, []):
            segment = _segment(kid)
            if segment == f"sct_{n}":
                found.append(kid)
            elif segment.startswith("sct_") and container.startswith("anx_"):
                found += self._sections(version, kid, n)
        return found

