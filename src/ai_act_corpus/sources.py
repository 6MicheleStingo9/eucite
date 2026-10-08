"""The works the corpus is composed from, and how each is requested from Cellar.

The corpus is not one document. The consolidated text has no preamble, so the
recitals come from the base act, and the amending act is needed both for its
own recitals and as the reference for the amendment diff (ADR-0001). Every work
is read in two manifestations, each used only for what the other cannot
provide: Formex for text and structure, XHTML for the amendment markers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import product

__all__ = [
    "LANGUAGES",
    "WORKS",
    "Manifestation",
    "Role",
    "SourceKey",
    "Work",
    "all_sources",
    "work",
]


class Role(StrEnum):
    BASE_ACT = "base_act"
    CONSOLIDATED = "consolidated"
    AMENDING_ACT = "amending_act"


class Manifestation(StrEnum):
    """A manifestation, named as Cellar names it in its notices."""

    FORMEX = "fmx4"
    XHTML = "xhtml"

    @property
    def accept(self) -> str:
        """The ``Accept`` header that negotiates this manifestation.

        Formex is a bundle of files, so it is negotiated as a zip. The
        single-document form ``application/xml;type=fmx4`` returns 404 for these
        works: that is the request that misled the first feasibility spike.
        """
        return _ACCEPT[self]

    @property
    def media_type(self) -> str:
        """The media type a valid response must declare."""
        return _MEDIA_TYPE[self]


_ACCEPT = {
    Manifestation.FORMEX: "application/zip;mtype=fmx4",
    Manifestation.XHTML: "application/xhtml+xml",
}
_MEDIA_TYPE = {
    Manifestation.FORMEX: "application/zip",
    Manifestation.XHTML: "application/xhtml+xml",
}


@dataclass(frozen=True)
class Work:
    celex: str
    role: Role
    title: str


WORKS: tuple[Work, ...] = (
    Work(
        "32024R1689",
        Role.BASE_ACT,
        "Regulation (EU) 2024/1689 (AI Act), as published in the Official Journal",
    ),
    Work(
        "02024R1689-20260727",
        Role.CONSOLIDATED,
        "Regulation (EU) 2024/1689, consolidated text of 27 July 2026",
    ),
    Work(
        "32026R1744",
        Role.AMENDING_ACT,
        "Regulation (EU) 2026/1744 (Digital Omnibus on AI)",
    ),
)

# ISO 639-3, the codes Cellar expects in Accept-Language.
LANGUAGES: tuple[str, ...] = ("ita", "eng")


@dataclass(frozen=True, order=True)
class SourceKey:
    """One payload to acquire: a work, in a language, in a manifestation."""

    celex: str
    lang: str
    manifestation: Manifestation

    @property
    def accept(self) -> str:
        return self.manifestation.accept

    def __str__(self) -> str:
        return f"{self.celex}/{self.lang}/{self.manifestation}"


def work(celex: str) -> Work:
    """Return the registered work with this CELEX number."""
    for w in WORKS:
        if w.celex == celex:
            return w
    known = ", ".join(w.celex for w in WORKS)
    raise ValueError(f"unknown work {celex!r}; the corpus is composed of: {known}")


def all_sources(
    works: tuple[Work, ...] = WORKS,
    languages: tuple[str, ...] = LANGUAGES,
    manifestations: tuple[Manifestation, ...] = tuple(Manifestation),
) -> list[SourceKey]:
    """Every payload the corpus needs, in a stable order."""
    return sorted(
        SourceKey(w.celex, lang, m) for w, lang, m in product(works, languages, manifestations)
    )
