"""Formex to nodes (L1, ADR-0012).

The parser reads a Formex bundle (``eucite.formex``) and returns a
:class:`~eucite.nodes.Document`: every article, paragraph, subparagraph, point,
indent, annex, annex section, table, recital and citation, with the identifiers
of ADR-0002.

It works in two passes. The first walks the XML in document order and builds a
tree of raw nodes whose text is kept as *pieces*, each carrying the set of
amendment markers open where it stands. Markers are processing instructions
(``CLG.MDFO`` … ``CLG.MDFC``) that may open in one element and close in another
— Article 58(1) of the consolidated text marks the label of the paragraph and
the introduction of its first subparagraph, not its points — so they are
tracked on the text, not on the elements. The second pass assigns identifiers,
composes texts, applies deletions and attributes each amendment to the nodes it
covers.

What the parser does not recognise, it refuses: an element where structure is
expected, a label, a processing instruction, a marker attribute, a schema.
Each refusal names the place in the source.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import reduce

from lxml import etree

from eucite.formex import Element, FormexBundle, read_bundle
from eucite.labels import (
    LabelError,
    annex_number,
    annex_section,
    article_number,
    division_number,
    identifier_number,
    point_number,
)
from eucite.nodes import (
    Action,
    Amendment,
    Document,
    IdBasis,
    Node,
    NodeType,
    Provenance,
    Scope,
    compose_block,
)
from eucite.sources import represented_act

__all__ = ["SUPPORTED_SCHEMAS", "ParseError", "clean_text", "parse_bundle", "parse_formex"]

SUPPORTED_SCHEMAS = frozenset(
    {"http://formex.publications.europa.eu/schema/formex-06.02.1-20231031.xd"}
)


class ParseError(ValueError):
    """The source has a shape this parser does not know. Never guessed around."""


# -- text --------------------------------------------------------------------------

_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"))
_SPACE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """NFC, invisible characters removed, every run of whitespace one space.

    Unlike the canonical form (ADR-0006), quotes, dashes and apostrophes are
    kept as printed: this is the text people read and quote.
    """
    return _SPACE.sub(" ", unicodedata.normalize("NFC", text).translate(_INVISIBLE)).strip()


# Elements whose text joins the line they stand in.
INLINE = frozenset({"HT", "DATE", "REF.DOC", "REF.DOC.OJ", "LINK", "FT", "IE", "TXT"})
LABELS = frozenset({"NO.P", "NO.PARAG"})
QUOTES = frozenset({"QUOT.START", "QUOT.END"})
_HT_PREFIX = {"SUP": "^", "SUB": "_"}
# Publication metadata, wherever it appears.
METADATA = frozenset({"BIB.INSTANCE", "INFO.CONSLEG", "INFO.PROD", "FAM.COMP"})
_PSEUDO_ATTR = re.compile(r'([\w.]+)=(["\'])(.*?)\2')
# Attributes and values of the amendment markers this parser knows.
_MARKER_ATTRIBUTES = frozenset(
    {"ID", "IDREF", "ACTION", "LEVEL", "COMMAND", "ACTIVE.DOC", "ACTIVE.LOC", "MOD.LEVEL"}
)
_ACTIONS: dict[str, Action] = {"REPLACED": "replaced", "INSERTED": "inserted", "DELETED": "deleted"}
_COMMANDS = {"EXPLICIT": False, "IMPLICIT": True}


@dataclass(frozen=True)
class _Piece:
    text: str
    marks: frozenset[str]


@dataclass(frozen=True)
class _Marker:
    id: str
    order: int
    action: Action
    implicit: bool
    act: str
    location: str


# Characters that close what precedes them: never the start of a line.
_CLOSING = (";", ",", ".", ":", ")", "\u2019", "\u201d", "\u00bb")


class _Lines:
    """Text gathered as lines of pieces; a block boundary ends a line.

    Two exceptions keep lines as the text is printed: a label stays on the line
    of the block it introduces (the label ``13.`` of a quoted paragraph and the
    text that follows it), and punctuation that follows a block closes that
    block's line (the ``;`` after a quotation).
    """

    def __init__(self) -> None:
        self.items: list[list[_Piece] | _Raw] = []
        self._open: list[_Piece] | None = None
        self.glue = False

    def add(self, piece: _Piece) -> None:
        blank = not piece.text.strip()
        if self._open is None:
            if blank:
                return
            last = self.items[-1] if self.items else None
            if isinstance(last, list) and piece.text.lstrip().startswith(_CLOSING):
                self._open = last
            else:
                self._open = []
                self.items.append(self._open)
        self._open.append(piece)
        if not blank:
            self.glue = False

    def flush(self) -> None:
        if not self.glue:
            self._open = None

    def child(self, raw: _Raw) -> None:
        self.glue = False
        self._open = None
        self.items.append(raw)

    def pieces(self) -> list[_Piece]:
        return [p for item in self.items if isinstance(item, list) for p in item]


class _Raw:
    """A node before identifiers and texts are settled."""

    def __init__(
        self, kind: NodeType, el: Element, *, container: bool = False, identifier: str | None = None
    ) -> None:
        self.kind = kind
        self.el = el
        self.container = container
        self.identifier = identifier
        self.number: str | None = None
        self.label = _Lines()
        self.heading = _Lines()
        self.body = _Lines()
        self.notes: list[_Lines] = []

    @property
    def children(self) -> list[_Raw]:
        return [item for item in self.body.items if isinstance(item, _Raw)]

    def own_pieces(self) -> list[_Piece]:
        notes = [p for n in self.notes for p in n.pieces()]
        return self.label.pieces() + self.heading.pieces() + self.body.pieces() + notes


def _where(el: Element) -> str:
    path: str = el.getroottree().getpath(el)
    ident = el.get("IDENTIFIER") if isinstance(el.tag, str) else None
    return f"{path} [{ident}]" if ident else path


def _is_pi(node: Element) -> bool:
    return node.tag is etree.ProcessingInstruction


# -- first pass: the raw tree ------------------------------------------------------

Handler = Callable[[Element, _Raw], None]


class _Reader:
    def __init__(self, bundle: FormexBundle) -> None:
        self.bundle = bundle
        self.markers: dict[str, _Marker] = {}
        self.active: dict[str, None] = {}

    # markers

    def _marks(self) -> frozenset[str]:
        return frozenset(self.active)

    def _text(self, text: str | None, sink: _Lines) -> None:
        if text:
            sink.add(_Piece(text, self._marks()))

    def _pi(self, pi: Element) -> None:
        target = pi.target
        if target == "PAGE":
            return
        attrs = {k: v for k, _, v in _PSEUDO_ATTR.findall(pi.text or "")}
        if target == "CLG.MDFO":
            self._open(attrs, pi)
        elif target == "CLG.MDFC":
            ref = attrs.get("IDREF", "")
            if ref not in self.active:
                raise ParseError(f"marker {ref!r} closed but not open at {_where(pi.getparent())}")
            del self.active[ref]
        else:
            raise ParseError(
                f"unknown processing instruction <?{target}?> at {_where(pi.getparent())}"
            )

    def _open(self, attrs: dict[str, str], pi: Element) -> None:
        where = _where(pi.getparent())
        if set(attrs) - _MARKER_ATTRIBUTES or not {"ID", "ACTION", "COMMAND", "ACTIVE.DOC"} <= set(
            attrs
        ):
            raise ParseError(f"amendment marker with attributes {sorted(attrs)} at {where}")
        action = _ACTIONS.get(attrs["ACTION"])
        implicit = _COMMANDS.get(attrs["COMMAND"])
        if action is None or implicit is None or attrs.get("LEVEL") not in ("STRUCTURE", "TEXT"):
            raise ParseError(f"amendment marker {attrs} at {where}: unknown value")
        if attrs.get("MOD.LEVEL", "1") != "1":
            raise ParseError(f"amendment of an amendment (MOD.LEVEL) at {where}")
        marker = _Marker(
            id=attrs["ID"],
            order=len(self.markers),
            action=action,
            implicit=implicit,
            act=attrs["ACTIVE.DOC"],
            location=attrs.get("ACTIVE.LOC", ""),
        )
        if marker.id in self.markers:
            raise ParseError(f"amendment marker {marker.id!r} opened twice at {where}")
        self.markers[marker.id] = marker
        self.active[marker.id] = None

    # structure

    def _children(self, el: Element, owner: _Raw, handlers: Mapping[str, Handler | None]) -> None:
        """Visit a structural container: only known children, no loose text."""
        if (el.text or "").strip():
            raise ParseError(f"unexpected text in <{el.tag}> at {_where(el)}")
        for child in el:
            if _is_pi(child):
                self._pi(child)
            elif not isinstance(child.tag, str):
                pass
            elif child.tag in handlers:
                handler = handlers[child.tag]
                if handler is not None:
                    handler(child, owner)
            else:
                raise ParseError(f"unexpected <{child.tag}> in <{el.tag}> at {_where(el)}")
            if (child.tail or "").strip():
                raise ParseError(f"unexpected text after <{child.tag}> at {_where(child)}")

    def read(self) -> _Raw:
        documents = self.bundle.documents
        root = _Raw(NodeType.ACT, documents[0].root, container=True)
        for doc in documents:
            if doc.role == "unreferenced":
                raise ParseError(f"{doc.filename} is in the bundle but no document refers to it")
            readers: dict[str, Handler] = {
                "ACT": self._act,
                "CONS.ACT": self._cons_act,
                "ANNEX": self._annex,
            }
            if doc.root.tag not in readers:
                raise ParseError(f"{doc.filename}: unknown document <{doc.root.tag}>")
            readers[doc.root.tag](doc.root, root)
        if self.active:
            raise ParseError(f"amendment markers never closed: {sorted(self.active)}")
        return root

    def _act(self, el: Element, root: _Raw) -> None:
        self._children(
            el,
            root,
            {
                "BIB.INSTANCE": None,
                "TITLE": self._act_title,
                "PREAMBLE": self._preamble,
                "ENACTING.TERMS": self._enacting_terms,
                "FINAL": None,
            },
        )

    def _cons_act(self, el: Element, root: _Raw) -> None:
        self._children(
            el, root, {"INFO.CONSLEG": None, "INFO.PROD": None, "CONS.DOC": self._cons_doc}
        )

    def _cons_doc(self, el: Element, root: _Raw) -> None:
        self._children(
            el,
            root,
            {
                "BIB.INSTANCE": None,
                "FAM.COMP": None,
                "TITLE": self._act_title,
                "PREAMBLE": self._preamble,
                "ENACTING.TERMS": self._enacting_terms,
                "FINAL": None,
                "CONS.ANNEX": self._annex,
            },
        )

    def _act_title(self, el: Element, root: _Raw) -> None:
        self._flat(el, root.heading, root)

    def _preamble(self, el: Element, root: _Raw) -> None:
        self._children(
            el,
            root,
            {
                "PREAMBLE.INIT": None,
                "GR.VISA": lambda e, r: self._children(e, r, {"VISA": self._citation}),
                "GR.CONSID": lambda e, r: self._children(
                    e, r, {"GR.CONSID.INIT": None, "CONSID": self._recital}
                ),
                "PREAMBLE.FINAL": None,
            },
        )

    def _citation(self, el: Element, root: _Raw) -> None:
        raw = _Raw(NodeType.CITATION, el)
        root.body.child(raw)
        self._content(el, raw, {})

    def _recital(self, el: Element, root: _Raw) -> None:
        raw = _Raw(NodeType.RECITAL, el)
        root.body.child(raw)
        self._children(el, raw, {"NP": self._np})

    def _enacting_terms(self, el: Element, root: _Raw) -> None:
        self._children(el, root, {"DIVISION": self._chapter, "ARTICLE": self._article})

    def _chapter(self, el: Element, parent: _Raw) -> None:
        raw = _Raw(NodeType.CHAPTER, el, container=True)
        parent.body.child(raw)
        self._children(
            el,
            raw,
            {
                "TITLE": self._division_title,
                "DIVISION": self._division_section,
                "ARTICLE": self._article,
            },
        )

    def _division_section(self, el: Element, parent: _Raw) -> None:
        raw = _Raw(NodeType.SECTION, el, container=True)
        parent.body.child(raw)
        self._children(el, raw, {"TITLE": self._division_title, "ARTICLE": self._article})

    def _division_title(self, el: Element, raw: _Raw) -> None:
        self._children(
            el,
            raw,
            {
                "TI": lambda e, r: self._flat(e, r.label, r),
                "STI": lambda e, r: self._flat(e, r.heading, r),
            },
        )

    def _article(self, el: Element, parent: _Raw) -> None:
        raw = _Raw(NodeType.ARTICLE, el, identifier=self._identifier(el))
        parent.body.child(raw)
        self._children(
            el,
            raw,
            {
                "TI.ART": lambda e, r: self._flat(e, r.label, r),
                "STI.ART": lambda e, r: self._flat(e, r.heading, r),
                "PARAG": self._paragraph,
                "ALINEA": self._subparagraph,
            },
        )

    def _paragraph(self, el: Element, article: _Raw) -> None:
        raw = _Raw(NodeType.PARAGRAPH, el, identifier=self._identifier(el))
        article.body.child(raw)
        self._children(
            el,
            raw,
            {"NO.PARAG": lambda e, r: self._flat(e, r.label, r), "ALINEA": self._subparagraph},
        )

    def _identifier(self, el: Element) -> str:
        identifier = el.get("IDENTIFIER")
        if not identifier:
            raise ParseError(f"<{el.tag}> without IDENTIFIER at {_where(el)}")
        return str(identifier)

    def _subparagraph(self, el: Element, parent: _Raw) -> None:
        raw = _Raw(NodeType.SUBPARAGRAPH, el)
        parent.body.child(raw)
        self._content(el, raw, {})

    def _list(self, el: Element, owner: _Raw) -> None:
        owner.body.flush()
        self._children(el, owner, {"ITEM": self._item})

    def _item(self, el: Element, parent: _Raw) -> None:
        labelled = el.find("NP") is not None
        raw = _Raw(NodeType.POINT if labelled else NodeType.INDENT, el)
        parent.body.child(raw)
        self._children(el, raw, {"NP": self._np, "P": self._block})

    def _np(self, el: Element, raw: _Raw) -> None:
        """Label and text of a point or recital: ``NO.P`` then its content."""
        self._content(el, raw, {"NO.P": lambda e, r: self._flat(e, r.label, r)})

    def _block(self, el: Element, raw: _Raw) -> None:
        raw.body.flush()
        self._content(el, raw, {})
        raw.body.flush()

    def _annex(self, el: Element, root: _Raw) -> None:
        raw = _Raw(NodeType.ANNEX, el)
        root.body.child(raw)
        self._children(
            el,
            raw,
            {"BIB.INSTANCE": None, "TITLE": self._annex_title, "CONTENTS": self._annex_contents},
        )

    def _annex_title(self, el: Element, raw: _Raw) -> None:
        def ti(e: Element, r: _Raw) -> None:
            paragraphs = [c for c in e if isinstance(c.tag, str)]
            if not paragraphs or any(c.tag != "P" for c in paragraphs):
                raise ParseError(f"annex title of unknown shape at {_where(e)}")
            self._flat(paragraphs[0], r.label, r)
            for p in paragraphs[1:]:
                self._flat(p, r.heading, r)

        self._children(el, raw, {"TI": ti, "STI": lambda e, r: self._flat(e, r.heading, r)})

    def _annex_structure(self) -> dict[str, Handler]:
        return {"GR.SEQ": self._annex_section, "NP": self._annex_point}

    def _annex_contents(self, el: Element, raw: _Raw) -> None:
        self._content(el, raw, self._annex_structure())

    def _annex_section(self, el: Element, parent: _Raw) -> None:
        raw = _Raw(NodeType.SECTION, el)
        parent.body.child(raw)
        self._content(el, raw, {"TITLE": self._annex_section_title, **self._annex_structure()})

    def _annex_section_title(self, el: Element, raw: _Raw) -> None:
        def ti(e: Element, r: _Raw) -> None:
            numbered = e.find("NP")
            if numbered is not None:
                if [c.tag for c in e if isinstance(c.tag, str)] != ["NP"]:
                    raise ParseError(f"annex section title of unknown shape at {_where(e)}")
                self._children(
                    numbered,
                    r,
                    {
                        "NO.P": lambda x, y: self._flat(x, y.label, y),
                        "TXT": lambda x, y: self._flat(x, y.heading, y),
                    },
                )
                r.number = _number(point_number, r.label, numbered)
                return
            title = _Lines()
            self._flat(e, title, r)
            pieces = title.pieces()
            marks: frozenset[str] = frozenset().union(*(p.marks for p in pieces))
            try:
                label, number, heading = annex_section(clean_text("".join(p.text for p in pieces)))
            except LabelError as exc:
                raise ParseError(f"{exc} at {_where(e)}") from exc
            r.label.add(_Piece(label, marks))
            if heading:
                r.heading.add(_Piece(heading, marks))
            r.number = number

        self._children(el, raw, {"TI": ti, "STI": lambda e, r: self._flat(e, r.heading, r)})

    def _annex_point(self, el: Element, parent: _Raw) -> None:
        raw = _Raw(NodeType.POINT, el)
        parent.body.child(raw)
        self._np(el, raw)

    def _table(self, el: Element, owner: _Raw) -> None:
        raw = _Raw(NodeType.TABLE, el)
        owner.body.child(raw)
        self._flat(el, raw.body, raw)

    # content

    def _content(self, el: Element, raw: _Raw, structure: Mapping[str, Handler]) -> None:
        """Text of ``el`` into ``raw``; lists, tables and ``structure`` become children."""
        self._text(el.text, raw.body)
        for child in el:
            self._content_child(child, raw, structure)
            self._text(child.tail, raw.body)

    def _content_child(self, child: Element, raw: _Raw, structure: Mapping[str, Handler]) -> None:
        if _is_pi(child):
            self._pi(child)
            return
        if not isinstance(child.tag, str):
            return
        tag = child.tag
        if tag in structure:
            structure[tag](child, raw)
        elif tag == "P":
            self._block(child, raw)
        elif tag == "LIST":
            self._list(child, raw)
        elif tag == "TBL":
            self._table(child, raw)
        elif tag == "QUOT.S":
            raw.body.flush()
            self._flat(child, raw.body, raw)
            raw.body.flush()
        elif tag == "NOTE":
            self._note(child, raw)
        elif tag in INLINE or tag in QUOTES:
            hidden = [
                d.tag
                for d in child.iter("LIST", "TBL", "ITEM", "PARAG", "ALINEA")
                if not any(a.tag in ("QUOT.S", "NOTE") for a in d.iterancestors())
            ]
            if hidden:
                raise ParseError(f"structure {hidden} inside <{tag}> at {_where(child)}")
            self._flat(child, raw.body, raw)
        else:
            raise ParseError(f"unexpected <{tag}> in {raw.kind} at {_where(child)}")

    def _note(self, el: Element, owner: _Raw) -> None:
        note = _Lines()
        self._text(el.text, note)
        for child in el:
            self._flat(child, note, owner)
            self._text(child.tail, note)
        owner.notes.append(note)

    def _flat(self, el: Element, sink: _Lines, owner: _Raw) -> None:
        """Everything as text: quoted provisions, labels, headings, notes, tables."""
        if _is_pi(el):
            self._pi(el)
            return
        if not isinstance(el.tag, str) or el.tag in METADATA:
            return
        tag = el.tag
        if tag == "NOTE":
            self._note(el, owner)
            return
        if tag in QUOTES:
            sink.add(_Piece(_quote_char(el), self._marks()))
            return
        if tag == "INCL.ELEMENT":
            included = self.bundle.included(el.get("FILEREF", ""))
            if included is None:
                raise ParseError(f"included file {el.get('FILEREF')!r} missing at {_where(el)}")
            self._flat(included, sink, owner)
            return
        if tag == "ROW":
            self._row(el, sink, owner)
            return
        if tag == "FT" and el.get("TYPE") == "NUMBER" and len(el) == 0:
            self._text(_group_digits(el.text or ""), sink)
            return
        block = tag not in INLINE and tag not in LABELS
        if block:
            sink.flush()
        if tag == "HT":
            self._text(_HT_PREFIX.get(el.get("TYPE", ""), ""), sink)
        self._text(el.text, sink)
        for child in el:
            self._flat(child, sink, owner)
            self._text(child.tail, sink)
        if tag in LABELS:
            self._text(" ", sink)
            sink.glue = True
        if block:
            sink.flush()

    def _row(self, el: Element, sink: _Lines, owner: _Raw) -> None:
        """One line per row, cells separated by `` | ``."""
        sink.flush()
        first = True
        for cell in el:
            if _is_pi(cell):
                self._pi(cell)
                continue
            if not isinstance(cell.tag, str):
                continue
            if cell.tag != "CELL":
                raise ParseError(f"unexpected <{cell.tag}> in a table row at {_where(el)}")
            if not first:
                self._text(" | ", sink)
            first = False
            content = _Lines()
            self._flat(cell, content, owner)
            for i, line in enumerate(i for i in content.items if isinstance(i, list)):
                if i:
                    self._text(" ", sink)
                for piece in line:
                    sink.add(piece)
        sink.flush()


def _group_digits(number: str) -> str:
    """``35000000`` → ``35 000 000``, as the Official Journal prints a number that
    Formex marks as such. Numbers under five digits are left as written."""
    if not re.fullmatch(r"\d{5,}", number):
        return number
    head = len(number) % 3 or 3
    return " ".join([number[:head]] + [number[i : i + 3] for i in range(head, len(number), 3)])


def _quote_char(el: Element) -> str:
    code = el.get("CODE", "")
    try:
        return chr(int(code, 16))
    except ValueError as exc:
        raise ParseError(f"quotation mark with CODE {code!r} at {_where(el)}") from exc


def _number(rule: Callable[[str], str], label: _Lines, el: Element) -> str:
    text = clean_text("".join(p.text for p in label.pieces()))
    try:
        return rule(text)
    except LabelError as exc:
        raise ParseError(f"{exc} at {_where(el)}") from exc


# -- second pass: nodes --------------------------------------------------------------

SEGMENTS = {
    NodeType.CHAPTER: "cpt",
    NodeType.SECTION: "sct",
    NodeType.ARTICLE: "art",
    NodeType.PARAGRAPH: "para",
    NodeType.SUBPARAGRAPH: "subpara",
    NodeType.POINT: "point",
    NodeType.INDENT: "indent",
    NodeType.ANNEX: "anx",
    NodeType.TABLE: "table",
    NodeType.RECITAL: "rct",
    NodeType.CITATION: "cit",
}
# Levels whose identifier does not include the parent's path, as in EUR-Lex:
# art_6, not cpt_III.sct_1.art_6.
TOP_LEVEL = frozenset(
    {NodeType.CHAPTER, NodeType.ARTICLE, NodeType.ANNEX, NodeType.RECITAL, NodeType.CITATION}
)
POSITIONAL = frozenset({NodeType.SUBPARAGRAPH, NodeType.INDENT, NodeType.TABLE, NodeType.CITATION})


class _Writer:
    def __init__(self, act: str, markers: dict[str, _Marker]) -> None:
        self.act = act
        self.markers = markers
        self.deleting = frozenset(m.id for m in markers.values() if m.action == "deleted")
        self.nodes: list[Node] = []
        self.ids: set[str] = set()
        self._cover: dict[int, frozenset[str] | None] = {}
        self._lines: dict[int, list[str]] = {}

    # coverage

    def cover(self, raw: _Raw) -> frozenset[str] | None:
        """Markers open over every piece of the node's content; None if it has none."""
        key = id(raw)
        if key not in self._cover:
            sets = [p.marks for p in raw.own_pieces() if p.text.strip()]
            sets += [c for c in map(self.cover, raw.children) if c is not None]
            self._cover[key] = reduce(frozenset.intersection, sets) if sets else None
        return self._cover[key]

    def own_marks(self, raw: _Raw) -> frozenset[str]:
        return frozenset(m for p in raw.own_pieces() if p.text.strip() for m in p.marks)

    def tombstone(self, raw: _Raw) -> bool:
        return bool((self.cover(raw) or frozenset()) & self.deleting)

    def lost_to_deletion(self, raw: _Raw) -> bool:
        """Whether some of the node's content was deleted: an empty text is then
        the text in force, not a gap in the source."""
        return bool(self.own_marks(raw) & self.deleting) or any(
            self.tombstone(c) or self.lost_to_deletion(c) for c in raw.children
        )

    # text

    def line(self, pieces: list[_Piece]) -> str:
        return clean_text("".join(p.text for p in pieces if not p.marks & self.deleting))

    def flat(self, lines: _Lines) -> str | None:
        text = " ".join(
            t for item in lines.items if isinstance(item, list) if (t := self.line(item))
        )
        return text or None

    def body(self, raw: _Raw) -> list[str]:
        key = id(raw)
        if key not in self._lines:
            out: list[str] = []
            for item in raw.body.items:
                if isinstance(item, _Raw):
                    if not self.tombstone(item):
                        out.extend(self.rendered(item))
                elif text := self.line(item):
                    out.append(text)
            self._lines[key] = out
        return self._lines[key]

    def rendered(self, raw: _Raw) -> list[str]:
        """The node as it reads inside its parent's text."""
        label = clean_text("".join(p.text for p in raw.label.pieces())) or None
        return compose_block(label, self.flat(raw.heading), self.body(raw))

    # identifiers

    def number(self, raw: _Raw, parent: _Raw | None, position: int) -> tuple[str, IdBasis]:
        """Number and basis of the identifier segment.

        A basis of ``source`` means EUR-Lex or Formex identifies the level: the
        identifier is inherited, and checked (``eucite.crosscheck``). Citations
        are numbered by position, as EUR-Lex numbers them.
        """
        kind = raw.kind
        if kind in POSITIONAL:
            return str(position), "source" if kind is NodeType.CITATION else "position"
        if kind in (NodeType.ARTICLE, NodeType.PARAGRAPH):
            assert raw.identifier is not None
            number = identifier_number(raw.identifier)
            rule = article_number if kind is NodeType.ARTICLE else point_number
            printed = _number(rule, raw.label, raw.el)
            if printed != number:
                raise ParseError(
                    f"label {printed!r} disagrees with IDENTIFIER {raw.identifier!r} "
                    f"at {_where(raw.el)}"
                )
            return number, "source"
        if kind is NodeType.CHAPTER:
            return _number(lambda t: division_number(t, nested=False), raw.label, raw.el), "source"
        if kind is NodeType.SECTION and parent is not None and parent.kind is NodeType.CHAPTER:
            return _number(lambda t: division_number(t, nested=True), raw.label, raw.el), "source"
        if kind is NodeType.SECTION:
            if raw.number is None:
                raise ParseError(f"annex section without a title at {_where(raw.el)}")
            return raw.number, "label"
        if kind is NodeType.ANNEX:
            return _number(annex_number, raw.label, raw.el), "source"
        if kind is NodeType.RECITAL:
            return _number(point_number, raw.label, raw.el), "source"
        if kind is NodeType.POINT:
            return _number(point_number, raw.label, raw.el), "label"
        raise ParseError(f"no identifier rule for {kind} at {_where(raw.el)}")

    def write(
        self, raw: _Raw, parent: _Raw | None, parent_id: str | None, path: str, position: int
    ) -> None:
        basis: IdBasis
        if raw.kind is NodeType.ACT:
            node_id, basis, source_ref = self.act, "source", self.act
        else:
            number, basis = self.number(raw, parent, position)
            segment = f"{SEGMENTS[raw.kind]}_{number}"
            path = segment if raw.kind in TOP_LEVEL or not path else f"{path}.{segment}"
            node_id = f"{self.act}/{path}"
            source_ref = None
            if basis == "source":
                source_ref = raw.identifier if raw.kind is NodeType.PARAGRAPH else path
        if node_id in self.ids:
            raise ParseError(f"duplicate identifier {node_id} at {_where(raw.el)}")
        self.ids.add(node_id)

        deleted = self.tombstone(raw)
        whole = self.cover(raw) or frozenset()
        part = self.own_marks(raw) - whole
        scopes: list[tuple[str, Scope]] = [(m, "whole") for m in whole] + [
            (m, "part") for m in part
        ]
        amendments = sorted(scopes, key=lambda x: self.markers[x[0]].order)
        text: str | None = None
        if not raw.container and not deleted:
            text = "\n".join(self.body(raw))
            if not text and not self.lost_to_deletion(raw):
                raise ParseError(f"{raw.kind} without text at {_where(raw.el)}")
        label = clean_text("".join(p.text for p in raw.label.pieces())) or None
        self.nodes.append(
            Node(
                id=node_id,
                type=raw.kind,
                parent=parent_id,
                order=len(self.nodes),
                label=label,
                heading=None if deleted else self.flat(raw.heading),
                text=text,
                notes=() if deleted else tuple(n for n in map(self.flat, raw.notes) if n),
                id_provenance="inherited" if basis == "source" else "derived",
                id_basis=basis,
                source_ref=source_ref,
                amendments=tuple(
                    Amendment(
                        action=self.markers[m].action,
                        scope=scope,
                        amending_act=self.markers[m].act,
                        location=self.markers[m].location,
                        implicit=self.markers[m].implicit,
                    )
                    for m, scope in amendments
                ),
            )
        )
        if deleted:
            return
        positions: dict[NodeType, int] = {}
        for child in raw.children:
            positions[child.kind] = positions.get(child.kind, 0) + 1
            self.write(child, raw, node_id, path, positions[child.kind])


# -- entry points ----------------------------------------------------------------------

_XSI_SCHEMA = "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"


def parse_bundle(
    bundle: FormexBundle, *, work: str, language: str, provenance: Provenance | None = None
) -> Document:
    schemas = {d.root.get(_XSI_SCHEMA) for d in bundle.documents} | {bundle.schema}
    unsupported = sorted(str(s) for s in schemas - SUPPORTED_SCHEMAS - {None})
    if unsupported or bundle.schema is None:
        raise ParseError(f"unsupported Formex schema: {unsupported or 'none declared'}")
    reader = _Reader(bundle)
    root = reader.read()
    writer = _Writer(represented_act(work), reader.markers)
    writer.write(root, None, None, "", 1)
    return Document(
        work=work,
        act=writer.act,
        language=language,
        schema_location=bundle.schema,
        nodes=tuple(writer.nodes),
        provenance=provenance,
    )


def parse_formex(
    content: bytes, *, work: str, language: str, provenance: Provenance | None = None
) -> Document:
    """Parse a Formex bundle as Cellar serves it."""
    return parse_bundle(read_bundle(content), work=work, language=language, provenance=provenance)
