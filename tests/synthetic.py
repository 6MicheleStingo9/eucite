"""A small synthetic corpus in a cache and a lock, for building datasets offline.

Every registered work, in every language, as one short act with a citation, a
recital, a chapter, an article with a list, and an annex; and an XHTML page
carrying the EUR-Lex identifiers of those nodes. Tests change one source to
show one behaviour.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from eucite.cache import ObjectStore, SourceLock, lock_entry, sha256_hex
from eucite.sources import Manifestation, SourceKey, all_sources
from tests.builders import (
    alinea,
    annex_document,
    article,
    division,
    enacting,
    item,
    lst,
    np_,
    p,
    parag,
    preamble,
    title,
)
from tests.doubles import FIXED_NOW, formex_act, formex_bundle, xhtml

WORDS = {
    "eng": {"article": "Article", "chapter": "CHAPTER", "annex": "ANNEX"},
    "ita": {"article": "Articolo", "chapter": "CAPO", "annex": "ALLEGATO"},
}
IDENTIFIERS = ("cit_1", "rct_1", "cpt_I", "art_1", "001.001", "anx_I")


def label(language: str, letter: str) -> str:
    return f"({letter})" if language == "eng" else f"{letter})"


def act_xml(language: str, points: dict[str, str] | None = None) -> str:
    words = WORDS[language]
    points = points if points is not None else {"a": "the first rule;", "b": "the second rule."}
    items = lst(*(item(label(language, k), v) for k, v in points.items()))
    body = division(
        f"{words['chapter']} I",
        "GENERAL PROVISIONS",
        article(
            "001",
            f"{words['article']} 1",
            "Subject matter",
            parag("001.001", "1.", alinea(p("This Regulation lays down:"), items)),
        ),
    )
    main = title() + preamble(visas=("Having regard to the Treaty,",), recitals=("The purpose.",))
    return formex_act(main + enacting(body))


def annex_xml(language: str) -> str:
    return annex_document(f"{WORDS[language]['annex']} I", "List", np_("1.", "Directive A."))


def formex(language: str, points: dict[str, str] | None = None) -> bytes:
    return formex_bundle(act_xml(language, points), (annex_xml(language),))


def page(identifiers: tuple[str, ...] = IDENTIFIERS) -> bytes:
    return xhtml("".join(f'<div id="{i}">x</div>' for i in identifiers))


Override = Callable[[SourceKey], bytes | None]


def corpus(root: Path, override: Override | None = None) -> tuple[ObjectStore, SourceLock]:
    """Store every source under ``root/cache`` and lock it.

    ``override`` may return other content for a key, or ``None`` for the default.
    """
    store = ObjectStore(root / "cache")
    lock = SourceLock()
    for key in all_sources():
        content = override(key) if override else None
        if content is None:
            content = formex(key.lang) if key.manifestation is Manifestation.FORMEX else page()
        digest, _ = store.put(content)
        url = f"https://publications.europa.eu/resource/celex/{key.celex}"
        lock = lock.with_entry(
            lock_entry(
                key,
                request_url=url,
                final_url=f"{url}/{sha256_hex(content)[:8]}",
                content_type=key.manifestation.media_type,
                sha256=digest,
                size=len(content),
                retrieved_at=FIXED_NOW,
            )
        )
    return store, lock
