"""Citations of provisions, read from text in Italian and English (S7b, ADR-0011).

A citation designates provisions of an act: ``Article 6(3)(a)``,
``art. 6, par. 3, lett. a)``, ``point 4 of Annex III``, ``considerando 58``,
``Articles 8 to 15``. Reading one is a matter of syntax only: this module turns
text into references — paths of steps such as article 6, paragraph 3, point a —
without consulting the act. What a reference designates is decided against the
structure of the act by :mod:`eucite.resolver`, which knows, for instance, that
Article 3 has no numbered paragraphs.

The grammar is closed. A form it does not know is not read, and nothing next to
a citation is guessed into it: :func:`find_citations` returns what it
recognises, :func:`read_citation` returns ``None`` unless the whole string is
one citation.

The act a citation belongs to is read from what is written next to it: ``GDPR
Art. 5(1)(b)``, ``Article 9(1) of Regulation (EU) 2016/679``, ``art. 22 del
GDPR``. A citation written next to no act is left to the caller, who knows what
the text is about.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from eucite.labels import MULTIPLICATIVES, LabelError, label_value

__all__ = [
    "ACTS",
    "NOT_ACTS",
    "ORDINALS",
    "ActName",
    "Level",
    "Mention",
    "Reference",
    "Step",
    "find_citations",
    "read_citation",
]


class Level(StrEnum):
    """What a step designates, named as in identifiers (ADR-0002)."""

    ARTICLE = "art"
    PARAGRAPH = "para"
    SUBPARAGRAPH = "subpara"
    POINT = "point"
    ANNEX = "anx"
    SECTION = "sct"
    RECITAL = "rct"
    CHAPTER = "cpt"


@dataclass(frozen=True)
class Step:
    level: Level
    number: str
    """As identifiers write it: ``6``, ``4a``, ``III``, ``a``, ``iv``, ``3-1``."""
    compact: bool = False
    """A number in parentheses, or after a dot, right after an article number:
    ``6(3)``, ``15.5``. It is read as a paragraph; where the article has no
    numbered paragraphs, the resolver also reads it as the unnumbered paragraph
    or the point with that number (``Article 3(1)``)."""


@dataclass(frozen=True)
class Reference:
    """One provision, or one range of provisions, that a citation designates."""

    steps: tuple[Step, ...]
    through: Step | None = None
    """The last provision of a range (``Articles 8 to 15``), at the level of the
    last step."""


@dataclass(frozen=True)
class ActName:
    """An act named next to a citation: ``GDPR``, ``Regulation (EU) 2016/679``."""

    text: str
    celex: str | None
    """The CELEX number of the act, when the name identifies it: a number of the
    form ``Regulation (EU) 2016/679``, or a name of an act of :data:`ACTS`
    (``AI Act``). ``None`` for any other name (``DORA``, ``that Regulation``)."""


@dataclass(frozen=True)
class Mention:
    """A citation found in text."""

    text: str
    start: int
    end: int
    language: str | None
    """``ita`` or ``eng``, from the words of the citation; ``None`` when nothing
    in it belongs to one language (``Art. 6(3)``)."""
    references: tuple[Reference, ...]
    act: ActName | None
    """The act named next to the citation. ``None`` when none is named, or when
    the citation names the act it is written in (``this Regulation``)."""


# -- lexicon -------------------------------------------------------------------------

_ENGLISH_ORDINALS = (
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
)  # fmt: skip
_ITALIAN_ORDINALS = (
    "primo", "secondo", "terzo", "quarto", "quinto", "sesto", "settimo", "ottavo", "nono", "decimo",
)  # fmt: skip
ORDINALS = {
    word: index + 1
    for words in (_ENGLISH_ORDINALS, _ITALIAN_ORDINALS)
    for index, word in enumerate(words)
}

ACTS = {"32024R1689": "ai", "32026R1744": "omnibus"}
"""The acts of the corpus, by the group of the grammar that names them."""

# Capitals that do not name an act when they stand next to a citation.
NOT_ACTS = frozenset(
    {
        "AGI", "AI", "AIO", "API", "APIs", "CEN", "CENELEC", "CLI", "CSV", "DE", "DPIA",
        "EAIB", "EN", "ES", "ETSI", "EU", "FAQ", "FR", "FRIA", "GU", "GUUE", "GenAI",
        "GPAI", "HRAIS", "IA", "IEC", "ISO", "IT", "JSON", "KPI", "LLM", "LLMs", "MCP",
        "ML", "MS", "NB", "NCA", "NCAs", "NIST", "NOTE", "OECD", "OJ", "OJEU", "PDF",
        "PMI", "PS", "QMS", "RAG", "README", "RMS", "SDK", "SME", "SMEs", "TODO", "UE",
        "UK", "UN", "URL", "US", "USA",
    }
)  # fmt: skip

_MULT = "|".join(MULTIPLICATIVES)
_ORDINAL = "|".join(ORDINALS)

_SPACE = r"[ \t ]"
# A line break that does not end a paragraph: Markdown wraps lines inside one.
_WS = rf"(?:{_SPACE}|\r?\n(?![ \t ]*\r?\n))"
_S = rf"{_WS}+"
_O = rf"{_WS}*"
_APOSTROPHE = "['’]"

# Label values as citations write them: 6, 4a, 14 bis, 3.1; a, ba, b ter; iv.
_DIGITS = rf"\d{{1,3}}(?:\.\d{{1,3}})*[a-z]?(?:{_SPACE}+(?:{_MULT}))?"
_VALUE = rf"(?:{_DIGITS}|(?:[a-z]{{1,2}}|[ivxl]{{1,5}})(?:{_SPACE}+(?:{_MULT}))?)"

_ARTICLE_NUMBER = re.compile(rf"(?P<n>\d{{1,3}})(?:(?P<suffix>[a-z])|{_SPACE}+(?P<mult>{_MULT}))?(?!\w)")
_NUMBER = re.compile(rf"(?P<n>\d{{1,3}}[a-z]?)(?:{_SPACE}+(?P<mult>{_MULT}))?(?!\w)")
_ROMAN = re.compile(r"(?P<n>[IVXLC]{1,7})(?!\w)")
_RECITAL_NUMBER = re.compile(r"(?P<open>\()?(?P<n>\d{1,3})(?(open)\))(?!\w)")
_SECTION_NUMBER = re.compile(r"(?P<n>[A-Z]|\d{1,2})(?!\w)")
_GROUP = re.compile(rf"{_SPACE}?\({_SPACE}*(?P<v>{_VALUE}){_SPACE}*\)")
_CLOSED_LABEL = re.compile(rf"(?P<v>{_VALUE})\)")
_BARE_LABEL = re.compile(rf"(?P<v>{_DIGITS})(?![\w)])")
_DOTTED_PARAGRAPH = re.compile(r"\.(?P<v>\d{1,2}[a-z]?)(?!\w|\.\d)")
_DOTTED_POINT = re.compile(r"\.(?P<v>\d{1,2}(?:\.\d{1,2})*)(?!\w|\.\d)")

_COMPONENT_SEP = re.compile(rf"{_O},{_O}|{_S}")
_LIST_SEP = re.compile(
    rf"{_O},{_O}(?:(?i:and|or|e|ed|o){_S})?|{_S}(?i:and|or|e|ed|o){_S}|{_O}/{_O}"
)
_RANGE_SEP = re.compile(rf"{_S}(?i:to){_S}|{_O}[-–—]{_O}")
_FROM = re.compile(rf"(?i:da){_S}")
_UNTIL = re.compile(rf"{_S}(?i:a){_S}")
# A gloss between the items of a list: "Articles 9, 14 (Human Oversight), and 15".
_GLOSS = re.compile(rf"{_SPACE}?\((?=[^()\d\n]*[A-Za-z])[^()\d\n]{{1,80}}\)")
_OF = re.compile(
    rf"(?:{_O},)?{_S}(?:(?i:of){_S}(?:(?i:the){_S})?|(?i:del|dello|della|dei|degli|delle|di){_S})"
    rf"|(?:{_O},)?{_S}(?i:dell){_APOSTROPHE}{_O}"
)

_PARAGRAPH_WORD = re.compile(
    rf"(?:(?i:paragraphs?|paras?|paragraf[oi])(?!\w)|(?i:paras?|par|parr)\.|§§?){_O}"
)
_COMMA_WORD = re.compile(rf"(?:(?i:comm[ai])(?!\w)|(?i:co)\.){_S}")
_SUBPARAGRAPH_WORD = re.compile(rf"(?:(?i:sub-?paragraphs?|subparas?)(?!\w)|(?i:subparas?)\.){_O}")
_ORDINAL_UNIT = re.compile(
    rf"(?P<o>(?i:{_ORDINAL})){_S}(?i:sub-?paragraph|paragraph|comma|paragrafo)(?!\w)"
)
_POINT_WORD = re.compile(
    rf"(?:(?i:points?|letters?|letter[ae]|punt[oi])(?!\w)|(?i:pts?|lett)\.|nn?\.){_O}"
)
_SECTION_WORD = re.compile(rf"(?:(?i:sections?|sezion[ei])(?!\w)|(?i:sect)\.){_S}")

_ARTICLE_WORD = r"(?:(?i:articles?|arts?\.|articol[oi]|artt\.)|Arts?)"
_DA = rf"(?:(?i:da){_S})?"  # "articoli da 8 a 15"
_ANCHOR = re.compile(
    rf"(?P<article>(?<!\w){_ARTICLE_WORD}(?={_O}{_DA}\d))"
    rf"|(?P<annex>(?<!\w)(?i:annex(?:es)?|allegat[oi])(?={_S}{_DA}[IVXLC]+(?!\w)))"
    rf"|(?P<recital>(?<!\w)(?i:recitals?|considerando)(?={_S}{_DA}\(?\d))"
    rf"|(?P<chapter>(?<!\w)(?i:chapters?|cap[oi])(?={_S}{_DA}[IVXLC]+(?!\w)))"
    rf"|(?P<inverted>(?<!\w)(?:(?i:{_ORDINAL}){_S}(?i:sub-?paragraph|paragraph|comma|paragrafo)"
    rf"|(?i:points?|paragraphs?|sub-?paragraphs?|sections?|letter[ae]|lett\.|punt[oi]"
    rf"|paragraf[oi]|sezion[ei]|comm[ai]))(?!\w))"
)
# What ends an inverted citation: "of Article 6(3)", "dell'allegato III".
_PRIMARY = re.compile(
    rf"(?P<article>(?:(?i:article|art\.|articolo)|Art)(?={_O}\d))"
    rf"|(?P<annex>(?i:annex|allegato)(?={_S}[IVXLC]+(?!\w)))"
    rf"|(?P<chapter>(?i:chapter|capo)(?={_S}[IVXLC]+(?!\w)))"
)
_PLURAL = re.compile(r"(?i:articles|arts\.?|articoli|artt\.|annexes|allegati|recitals|considerando|chapters|capi)")

# Words that say which language a citation is written in.
_ENGLISH = frozenset(
    "article articles annex annexes recital recitals chapter chapters paragraph paragraphs "
    "para paras subparagraph subparagraphs subpara point points letter letters section "
    "sections arts of and or to the this regulation".split()
) | frozenset(_ENGLISH_ORDINALS)
_ITALIAN = frozenset(
    "articolo articoli artt allegato allegati considerando capo capi paragrafo paragrafi "
    "parr comma commi lettera lettere lett punto punti sezione sezioni del dello della dei "
    "degli delle dell di da ed presente regolamento".split()
) | frozenset(_ITALIAN_ORDINALS)

# -- act names -----------------------------------------------------------------------

_FORMAL = (
    rf"(?:(?:Commission|Council|Implementing|Delegated){_S})*"
    rf"(?P<kind>(?i:regulation|directive|decision|regolamento|direttiva|decisione))"
    rf"(?:{_S}(?i:delegat[oa]|di{_S}esecuzione))?"
    rf"(?:{_S}\((?:EU|UE|EC|CE|EEC|CEE|Euratom)\))?"
    rf"(?:{_S}(?P<old>No\.?|n[.,°]|nr\.?))?"
    rf"{_S}(?P<year>\d{{2,4}})/(?P<number>\d{{1,4}})"
    rf"(?:/(?:EU|UE|EC|CE|EEC|CEE|JHA|GAI|CFSP|PESC))?(?!\d)"
)
_AI_ACT = (
    rf"(?:(?:EU|European){_S})?(?:AI|Artificial{_S}Intelligence){_S}Act(?!\w)|AIA(?!\w)"
    rf"|(?i:regolamento){_S}(?:(?i:europeo){_S})?"
    rf"(?:(?i:sull){_APOSTROPHE}{_O}(?:IA|(?i:intelligenza{_S}artificiale))|IA)(?!\w)"
)
_OMNIBUS = rf"Digital{_S}Omnibus{_S}on{_S}AI(?!\w)"
_THIS = rf"(?:this|the){_S}Regulation(?!\w)(?!{_S}\()|(?i:(?:il{_S})?presente{_S}regolamento)(?!\w)"
_THAT = (
    rf"(?:that|the{_S}said|said|the{_S}same){_S}(?i:regulation|directive|decision)(?!\w)"
    rf"|(?i:(?:tale|detto|predetto|suddetto|citato|medesimo|stesso){_S}"
    rf"(?:regolamento|direttiva|decisione))(?!\w)"
)
_NAMED = (
    rf"(?:[A-Z][\w-]*{_SPACE}+(?:(?:of|on|for|and|the){_SPACE}+)?){{0,5}}"
    rf"(?:Act|Regulation|Directive|Decision|Charter|Treaty|Convention|Constitution|Code)(?!\w)"
    rf"|(?i:Carta|Costituzione|Cost\.|trattato|convenzione|legge|decreto|codice"
    rf"|d\.{_O}lgs\.?|d\.{_O}l\.|d\.{_O}p\.{_O}r\.|c\.{_O}c\.|c\.{_O}p\.(?:{_O}[cp]\.)?)(?!\w)"
)
_ACRONYM = r"[a-z]?[A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*"
_ACRONYMS = rf"(?<!\w){_ACRONYM}(?:{_SPACE}+{_ACRONYM})*(?!\w)"

_DESIGNATION = (
    rf"(?P<formal>{_FORMAL})|(?P<ai>{_AI_ACT})|(?P<omnibus>{_OMNIBUS})|(?P<this>{_THIS})"
    rf"|(?P<that>{_THAT})|(?P<named>{_NAMED})|(?P<acronyms>{_ACRONYMS})"
)
# Without a preposition, only a name that cannot be anything else.
_ADJACENT = (
    rf"(?P<formal>{_FORMAL})|(?P<ai>{_AI_ACT})|(?P<omnibus>{_OMNIBUS})|(?P<acronyms>{_ACRONYMS})"
)
_ACT_AFTER = re.compile(
    rf"(?:{_O},)?{_S}(?:(?i:of|in){_S}(?:(?i:the){_S})?"
    rf"|(?i:del|dello|della|dei|degli|delle|di){_S}|(?i:dell){_APOSTROPHE}{_O})(?:{_DESIGNATION})"
)
_ACT_ADJACENT_AFTER = re.compile(rf"{_S}(?:{_ADJACENT})")
_ACT_BEFORE = re.compile(rf"(?:{_ADJACENT})(?:{_APOSTROPHE}s)?{_O}(?P<paren>\({_O})?\Z")
_SKIP = re.compile(_O)
_TYPES = {"regulation": "R", "regolamento": "R", "directive": "L", "direttiva": "L",
          "decision": "D", "decisione": "D"}  # fmt: skip


class _NotAnAct(Exception):
    """Capitals next to a citation that do not name an act."""


def _act(match: re.Match[str]) -> ActName | None:
    """The act a name designates; ``None`` for the act being read (``this Regulation``)."""
    groups = match.groupdict()
    if groups.get("this"):
        return None
    if groups.get("acronyms"):
        text = groups["acronyms"]
        if all(token in NOT_ACTS for token in text.split()):
            raise _NotAnAct
        return ActName(text, None)
    for celex, group in ACTS.items():
        if groups.get(group):
            return ActName(" ".join(groups[group].split()), celex)
    if groups.get("formal"):
        year, number = groups["year"], groups["number"]
        celex = None
        if not groups["old"] and len(year) == 4 and int(year) >= 2015:
            celex = f"3{year}{_TYPES[groups['kind'].lower()]}{int(number):04d}"
        return ActName(" ".join(groups["formal"].split()), celex)
    name = groups.get("that") or groups.get("named") or ""
    return ActName(" ".join(name.split()), None)


# -- reading -------------------------------------------------------------------------


class _Reader:
    """A position in the text, advanced by every pattern that matches there."""

    def __init__(self, text: str, pos: int) -> None:
        self.text = text
        self.pos = pos

    def take(self, pattern: re.Pattern[str]) -> re.Match[str] | None:
        match = pattern.match(self.text, self.pos)
        if match is not None:
            self.pos = match.end()
        return match


Read = Callable[[_Reader], "list[Reference] | None"]
"""Reads one item of a list, as references relative to what precedes the list."""
Bare = Callable[[_Reader], "Step | None"]
"""Reads the bare number of an item: what a range may join."""


def _number(match: re.Match[str]) -> str:
    groups = match.groupdict()
    value = groups["n"] + (groups.get("suffix") or "")
    if groups.get("mult"):
        value += " " + groups["mult"]
    return label_value(value)


def _items(r: _Reader, read: Read, bare: Bare, *, lists: bool = True) -> list[Reference] | None:
    """An item and, when ``lists``, the items and ranges that follow it.

    Items are separated by commas, ``and``/``e``, ``or``/``o`` or slashes. A range
    joins two bare items: ``8 to 15``, ``IV–XIII``, ``da 1 a 5``, ``(a) to (d)``.
    """
    refs = (_from_until(r, bare) if lists else None) or read(r)
    if refs is None:
        return None
    return _following(r, refs, read, bare) if lists else refs


def _from_until(r: _Reader, bare: Bare) -> list[Reference] | None:
    """Italian ranges: ``da 1 a 5``."""
    save = r.pos
    if r.take(_FROM):
        first = bare(r)
        last = bare(r) if first is not None and r.take(_UNTIL) else None
        if first is not None and last is not None:
            return [Reference((first,), last)]
    r.pos = save
    return None


def _following(r: _Reader, refs: list[Reference], read: Read, bare: Bare) -> list[Reference]:
    while True:
        save = r.pos
        r.take(_GLOSS)
        last = refs[-1]
        if last.through is None and len(last.steps) == 1 and r.take(_RANGE_SEP):
            end = bare(r)
            if end is not None:
                refs[-1] = Reference(last.steps, end)
                continue
            r.pos = save
            r.take(_GLOSS)
        if r.take(_LIST_SEP):
            more = _from_until(r, bare) or read(r)
            if more is not None:
                refs.extend(more)
                continue
        r.pos = save
        return refs


def _single(level: Level, pattern: re.Pattern[str]) -> tuple[Read, Bare]:
    """Readers for an item that is one number: a paragraph, a section, an annex."""

    def bare(r: _Reader) -> Step | None:
        match = r.take(pattern)
        if match is None:
            return None
        if level in (Level.ANNEX, Level.CHAPTER):
            return Step(level, match.group("n"))
        if level is Level.SECTION:
            return Step(level, match.group("n").lower())
        return Step(level, _number(match))

    def read(r: _Reader) -> list[Reference] | None:
        step = bare(r)
        return None if step is None else [Reference((step,))]

    return read, bare


def _label(r: _Reader, *, nested: bool) -> tuple[Step, ...] | None:
    """A point label, with the points nested in it when ``nested``: ``(a)``, ``a)``,
    ``4``, ``1(a)``, ``(49)(b)``, ``14 bis)``."""
    save = r.pos
    match = r.take(_GROUP) or r.take(_CLOSED_LABEL) or r.take(_BARE_LABEL)
    if match is None:
        return None
    try:
        steps = [Step(Level.POINT, label_value(match.group("v")))]
        while nested and (inner := r.take(_GROUP)):
            steps.append(Step(Level.POINT, label_value(inner.group("v"))))
    except LabelError:
        r.pos = save
        return None
    return tuple(steps)


def _read_point(r: _Reader) -> list[Reference] | None:
    steps = _label(r, nested=True)
    return None if steps is None else [Reference(steps)]


def _bare_point(r: _Reader) -> Step | None:
    steps = _label(r, nested=False)
    return None if steps is None else steps[0]


def _component(r: _Reader, path: tuple[Step, ...], container: Level) -> list[Reference] | None:
    """A worded part of a citation after its article, annex or chapter:
    ``paragraph 3``, ``second subparagraph``, ``points (d) and (e)``, ``Section A``.
    """
    if container is Level.ARTICLE:
        if ordinal := r.take(_ORDINAL_UNIT):
            number = str(ORDINALS[ordinal.group("o").lower()])
            return [Reference((Step(Level.SUBPARAGRAPH, number),))]
        if r.take(_SUBPARAGRAPH_WORD):
            read, bare = _single(Level.SUBPARAGRAPH, _NUMBER)
            return _items(r, read, bare, lists=False)
        if r.take(_PARAGRAPH_WORD):
            return _items(r, *_single(Level.PARAGRAPH, _NUMBER))
        if r.take(_COMMA_WORD):
            # Italian national usage: "comma 3" is the paragraph numbered 3, and
            # after a paragraph, its third subparagraph.
            within = any(s.level in (Level.PARAGRAPH, Level.SUBPARAGRAPH) for s in path)
            return _items(r, *_single(Level.SUBPARAGRAPH if within else Level.PARAGRAPH, _NUMBER))
    if container in (Level.ANNEX, Level.CHAPTER) and r.take(_SECTION_WORD):
        return _items(r, *_single(Level.SECTION, _SECTION_NUMBER))
    if container in (Level.ARTICLE, Level.ANNEX) and r.take(_POINT_WORD):
        return _items(r, _read_point, _bare_point)
    return None


def _compact(r: _Reader, path: list[Step]) -> list[Reference] | None:
    """``6(3)(a)``, ``15.5``, and the siblings of the last group: ``25(2) and (4)``.

    Returns the references when the groups end in a list, ``None`` otherwise,
    having added the groups to ``path``.
    """
    if dotted := r.take(_DOTTED_PARAGRAPH):
        path.append(Step(Level.PARAGRAPH, label_value(dotted.group("v")), compact=True))
    while (group := r.take(_GROUP)) is not None:
        value = group.group("v")
        try:
            number = label_value(value)
        except LabelError:
            r.pos = group.start()
            break
        if len(path) == 1 and value[0].isdigit():
            path.append(Step(Level.PARAGRAPH, number, compact=True))
        else:
            path.append(Step(Level.POINT, number))
    if len(path) == 1:
        return None
    last = path[-1]

    def bare(reader: _Reader) -> Step | None:
        save = reader.pos
        match = reader.take(_GROUP)
        if match is None:
            return None
        try:
            return Step(last.level, label_value(match.group("v")), last.compact)
        except LabelError:
            reader.pos = save
            return None

    def read(reader: _Reader) -> list[Reference] | None:
        first = bare(reader)
        if first is None:
            return None
        steps = [first]
        while (inner := reader.take(_GROUP)) is not None:
            try:
                steps.append(Step(Level.POINT, label_value(inner.group("v"))))
            except LabelError:
                reader.pos = inner.start()
                break
        return [Reference(tuple(steps))]

    refs = _following(r, [Reference((last,))], read, bare)
    if len(refs) == 1 and refs[0].through is None:
        return None
    head = tuple(path[:-1])
    return [Reference((*head, *ref.steps), ref.through) for ref in refs]


def _tail(r: _Reader, path: list[Step], container: Level) -> list[Reference]:
    """What follows the number of an article, an annex or a chapter."""
    if container is Level.ARTICLE:
        listed = _compact(r, path)
        if listed is not None:
            return listed
    elif container is Level.ANNEX and (dotted := r.take(_DOTTED_POINT)):
        path.append(Step(Level.POINT, label_value(dotted.group("v"))))
    while True:
        save = r.pos
        if not r.take(_COMPONENT_SEP):
            break
        refs = _component(r, tuple(path), container)
        if refs is None:
            r.pos = save
            break
        if len(refs) == 1 and refs[0].through is None:
            path.extend(refs[0].steps)
            continue
        while True:  # "punti da 1 a 5 e punti 8 e 9"
            save = r.pos
            more = _component(r, tuple(path), container) if r.take(_LIST_SEP) else None
            if more is None or more[0].steps[0].level is not refs[0].steps[0].level:
                r.pos = save
                break
            refs.extend(more)
        return [Reference((*path, *ref.steps), ref.through) for ref in refs]
    return [Reference(tuple(path))]


def _article_number(r: _Reader) -> Step | None:
    match = r.take(_ARTICLE_NUMBER)
    return None if match is None else Step(Level.ARTICLE, _number(match))


def _read_article(r: _Reader) -> list[Reference] | None:
    step = _article_number(r)
    return None if step is None else _tail(r, [step], Level.ARTICLE)


def _roman(level: Level) -> tuple[Read, Bare]:
    def bare(r: _Reader) -> Step | None:
        match = r.take(_ROMAN)
        return None if match is None else Step(level, match.group("n"))

    def read(r: _Reader) -> list[Reference] | None:
        step = bare(r)
        return None if step is None else _tail(r, [step], level)

    return read, bare


def _primary(r: _Reader, kind: str, *, plural: bool) -> list[Reference] | None:
    if kind == "article":
        return _items(r, _read_article, _article_number, lists=plural)
    if kind in ("annex", "chapter"):
        level = Level.ANNEX if kind == "annex" else Level.CHAPTER
        return _items(r, *_roman(level), lists=plural)
    if kind == "recital":
        return _items(r, *_single(Level.RECITAL, _RECITAL_NUMBER), lists=plural)
    raise AssertionError(kind)  # pragma: no cover


def _inverted_component(r: _Reader) -> list[Reference] | None:
    if ordinal := r.take(_ORDINAL_UNIT):
        return [Reference((Step(Level.SUBPARAGRAPH, str(ORDINALS[ordinal.group("o").lower()])),))]
    if r.take(_SUBPARAGRAPH_WORD):
        return _items(r, *_single(Level.SUBPARAGRAPH, _NUMBER), lists=False)
    if r.take(_PARAGRAPH_WORD) or r.take(_COMMA_WORD):
        return _items(r, *_single(Level.PARAGRAPH, _NUMBER))
    if r.take(_SECTION_WORD):
        return _items(r, *_single(Level.SECTION, _SECTION_NUMBER))
    if r.take(_POINT_WORD):
        return _items(r, _read_point, _bare_point)
    return None


def _inverted(r: _Reader) -> list[Reference] | None:
    """``point (a) of the first subparagraph of Article 5(1)``, ``punto 4 dell'allegato
    III``: parts of a provision, then the provision they belong to."""
    chain: list[list[Reference]] = []
    while True:
        refs = _inverted_component(r)
        if refs is None or (chain and (len(refs) != 1 or refs[0].through is not None)):
            return None
        chain.append(refs)
        if not r.take(_OF):
            return None
        primary = r.take(_PRIMARY)
        if primary is not None:
            break
    kind = primary.lastgroup
    assert kind is not None
    r.take(_SKIP)
    base = _primary(r, kind, plural=False)
    if base is None or len(base) != 1 or base[0].through is not None:
        return None
    middle = [refs[0].steps for refs in reversed(chain[1:])]
    steps = [*base[0].steps, *(s for part in middle for s in part)]
    paragraphs = sum(s.level is Level.PARAGRAPH for s in steps)
    out = []
    for ref in chain[0]:
        inner = ref.steps
        if paragraphs and inner[0].level is Level.PARAGRAPH:
            # "secondo comma del paragrafo 3": a comma inside a paragraph
            inner = (Step(Level.SUBPARAGRAPH, inner[0].number), *inner[1:])
        out.append(Reference((*steps, *inner), ref.through))
    return out


def _language(text: str) -> str | None:
    for word in re.findall(r"[^\W\d_]+", text.lower()):
        if word in _ENGLISH:
            return "eng"
        if word in _ITALIAN:
            return "ita"
    return None


def _mention(text: str, anchor: re.Match[str]) -> Mention | None:
    kind = anchor.lastgroup
    assert kind is not None
    if kind == "inverted":
        r = _Reader(text, anchor.start())
        refs = _inverted(r)
    else:
        r = _Reader(text, anchor.end())
        r.take(_SKIP)
        refs = _primary(r, kind, plural=bool(_PLURAL.fullmatch(anchor.group(kind))))
    if not refs:
        return None
    start, end = anchor.start(), r.pos
    act: ActName | None = None
    named = False
    for pattern in (_ACT_AFTER, _ACT_ADJACENT_AFTER):
        after = pattern.match(text, end)
        if after is not None:
            try:
                act, named, end = _act(after), True, after.end()
                break
            except _NotAnAct:
                pass
    if not named:
        before = _ACT_BEFORE.search(text, max(0, start - 160), start)
        if before is not None:
            try:
                act = _act(before)
                if not before.group("paren"):
                    start = before.start()
            except _NotAnAct:
                pass
    return Mention(text[start:end], start, end, _language(text[start:end]), tuple(refs), act)


def find_citations(text: str) -> list[Mention]:
    """Every citation in ``text``, in order."""
    mentions = []
    pos = 0
    while (anchor := _ANCHOR.search(text, pos)) is not None:
        mention = _mention(text, anchor)
        if mention is None:
            pos = anchor.end()
            continue
        mentions.append(mention)
        pos = mention.end
    return mentions


def read_citation(text: str) -> Mention | None:
    """``text`` as one citation, or ``None`` if it is not exactly one."""
    stripped = text.strip().rstrip(".;,")
    mentions = find_citations(stripped)
    if len(mentions) == 1 and (mentions[0].start, mentions[0].end) == (0, len(stripped)):
        return mentions[0]
    return None
