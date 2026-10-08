"""Small builders of synthetic Formex, for parser tests that read like the act.

Each builder returns a fragment of XML as a string. Text is escaped by the
caller where it matters; the fragments used in tests are plain.
"""

from __future__ import annotations

from eucite.formex import FormexBundle, read_bundle
from eucite.nodes import Document
from eucite.parse import parse_formex
from tests.doubles import SCHEMA, XSI, formex_act, formex_bundle

WORK = "32099R0001"


def title(text: str = "Regulation (EU) 2099/1 of the test") -> str:
    return f"<TITLE><TI><P>{text}</P></TI></TITLE>"


def article(identifier: str, label: str, heading: str | None, *content: str) -> str:
    sti = f"<STI.ART>{heading}</STI.ART>" if heading else ""
    return (
        f'<ARTICLE IDENTIFIER="{identifier}"><TI.ART>{label}</TI.ART>{sti}'
        f"{''.join(content)}</ARTICLE>"
    )


def parag(identifier: str, label: str, *alineas: str) -> str:
    return (
        f'<PARAG IDENTIFIER="{identifier}"><NO.PARAG>{label}</NO.PARAG>{"".join(alineas)}</PARAG>'
    )


def alinea(*content: str) -> str:
    return f"<ALINEA>{''.join(content)}</ALINEA>"


def p(*content: str) -> str:
    return f"<P>{''.join(content)}</P>"


def lst(*items: str, type_: str = "alpha") -> str:
    return f'<LIST TYPE="{type_}">{"".join(items)}</LIST>'


def item(label: str, text: str, *more: str) -> str:
    return f"<ITEM><NP><NO.P>{label}</NO.P><TXT>{text}</TXT>{''.join(more)}</NP></ITEM>"


def indent(text: str) -> str:
    return f"<ITEM><P>{text}</P></ITEM>"


def division(label: str, heading: str, *content: str) -> str:
    return (
        f"<DIVISION><TITLE><TI><P>{label}</P></TI><STI><P>{heading}</P></STI></TITLE>"
        f"{''.join(content)}</DIVISION>"
    )


def enacting(*content: str) -> str:
    return f"<ENACTING.TERMS>{''.join(content)}</ENACTING.TERMS>"


def preamble(visas: tuple[str, ...] = (), recitals: tuple[str, ...] = ()) -> str:
    gr_visa = "".join(f"<VISA>{v}</VISA>" for v in visas)
    consid = "".join(
        f"<CONSID><NP><NO.P>({i})</NO.P><TXT>{r}</TXT></NP></CONSID>"
        for i, r in enumerate(recitals, 1)
    )
    return (
        "<PREAMBLE><PREAMBLE.INIT>THE PARLIAMENT,</PREAMBLE.INIT>"
        f"<GR.VISA>{gr_visa}</GR.VISA>"
        f"<GR.CONSID><GR.CONSID.INIT>Whereas:</GR.CONSID.INIT>{consid}</GR.CONSID>"
        "<PREAMBLE.FINAL>HAVE ADOPTED THIS REGULATION:</PREAMBLE.FINAL></PREAMBLE>"
    )


def annex_parts(label: str, heading: str | None, *content: str) -> str:
    sti = f"<STI><P>{heading}</P></STI>" if heading else ""
    return f"<TITLE><TI><P>{label}</P></TI>{sti}</TITLE><CONTENTS>{''.join(content)}</CONTENTS>"


def annex_document(label: str, heading: str | None, *content: str) -> str:
    """An annex published as its own file, as in the base act."""
    return formex_act(annex_parts(label, heading, *content), root="ANNEX")


def cons_annex(label: str, heading: str | None, *content: str) -> str:
    """An annex inside a consolidated text."""
    return f"<CONS.ANNEX>{annex_parts(label, heading, *content)}</CONS.ANNEX>"


def group(title_xml: str, *content: str) -> str:
    return f'<GR.SEQ LEVEL="1"><TITLE>{title_xml}</TITLE>{"".join(content)}</GR.SEQ>'


def np_(label: str, text: str) -> str:
    return f"<NP><NO.P>{label}</NO.P><TXT>{text}</TXT></NP>"


def mdfo(
    ident: str,
    action: str = "REPLACED",
    *,
    level: str = "STRUCTURE",
    command: str = "EXPLICIT",
    act: str = "32099R0002",
    loc: str = "AR:1;PT:1",
    mod_level: str = "1",
) -> str:
    return (
        f'<?CLG.MDFO ID="O{ident}" IDREF="C{ident}" ACTION="{action}" LEVEL="{level}" '
        f'COMMAND="{command}" ACTIVE.DOC="{act}" ACTIVE.LOC="{loc}" MOD.LEVEL="{mod_level}"?>'
    )


def mdfc(ident: str) -> str:
    return f'<?CLG.MDFC ID="C{ident}" IDREF="O{ident}"?>'


def act(*body: str) -> str:
    """A complete ACT document: title, empty preamble, enacting terms from ``body``."""
    return formex_act(title() + preamble() + enacting(*body) + "<FINAL><P>Done.</P></FINAL>")


def consolidated(*body: str, annexes: tuple[str, ...] = ()) -> str:
    """A consolidated text: CONS.ACT with production metadata, no recitals."""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><CONS.ACT {XSI} '
        f'xsi:noNamespaceSchemaLocation="{SCHEMA}">'
        "<INFO.CONSLEG>metadata</INFO.CONSLEG><INFO.PROD>metadata</INFO.PROD><CONS.DOC>"
        '<BIB.INSTANCE><DOCUMENT.REF FILE="x"/></BIB.INSTANCE>'
        "<FAM.COMP><BIB.DATA>amended by</BIB.DATA></FAM.COMP>"
        f"{title()}<PREAMBLE><PREAMBLE.INIT>THE PARLIAMENT,</PREAMBLE.INIT>"
        "<PREAMBLE.FINAL>HAVE ADOPTED</PREAMBLE.FINAL></PREAMBLE>"
        f"{enacting(*body)}<FINAL><P>Done.</P></FINAL>{''.join(annexes)}</CONS.DOC></CONS.ACT>"
    )


def bundle(main: str, annexes: tuple[str, ...] = (), **kwargs: object) -> FormexBundle:
    return read_bundle(formex_bundle(main, annexes, **kwargs))  # type: ignore[arg-type]


def parse(
    main: str,
    annexes: tuple[str, ...] = (),
    *,
    work: str = WORK,
    language: str = "eng",
    **kwargs: object,
) -> Document:
    content = formex_bundle(main, annexes, **kwargs)  # type: ignore[arg-type]
    return parse_formex(content, work=work, language=language)
