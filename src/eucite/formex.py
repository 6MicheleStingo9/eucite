"""Reading a Formex bundle as one logical document.

A Formex manifestation is a zip of XML files whose names and number depend on
how the Publications Office split the act: the consolidated text is one file,
the base act sixteen (enacting terms, one file per annex, a table of contents,
a descriptor), the Omnibus four, one of which is *included* inside a quotation
of the enacting terms. Reading "the largest file" silently loses annexes.

The descriptor (root ``DOC``) lists the documents of the publication in order:
``DOC.MAIN.PUB`` then each ``DOC.SUB.PUB``, each pointing to its file. Files
referenced by an ``INCL.ELEMENT`` belong where the reference stands. The table
of contents (root ``PUBLICATION``) is publication metadata. Any other XML file
is unexpected and is kept, not dropped, so that its appearance is noticed.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from typing import Any, Literal

from lxml import etree

__all__ = ["BundleDocument", "BundleError", "FormexBundle", "parse_xml", "read_bundle"]

# Formex files are self-contained: no DTD, no external entities, no network.
# Processing instructions are kept: the consolidated text records each
# amendment as a pair of them (<?CLG.MDFO ... ACTION="DELETED" ...?> ...
# <?CLG.MDFC ...?>). Dropping them silently loses every amendment marker.
_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    remove_comments=True,
    remove_pis=False,
)

Element = Any  # lxml ships no type information
Role = Literal["main", "sub", "unreferenced"]


class BundleError(Exception):
    """The bundle cannot be read as a Formex publication."""


def parse_xml(content: bytes) -> Element:
    try:
        return etree.fromstring(content, _PARSER)
    except etree.XMLSyntaxError as exc:
        raise BundleError(f"malformed XML: {exc}") from exc


@dataclass(frozen=True)
class BundleDocument:
    """One document of the publication, in the order the descriptor gives."""

    role: Role
    seq: str
    """``NO.SEQ`` from the descriptor (``0001``, ``0001.0003``)."""
    kind: str | None
    """``TYPE`` of a sub-publication, such as ``ANNEX``."""
    filename: str
    root: Element


@dataclass(frozen=True)
class FormexBundle:
    documents: tuple[BundleDocument, ...]
    files: dict[str, Element] = field(repr=False)
    """Every parsed act file by name, including those only reached by inclusion."""
    schema: str | None
    """The Formex schema the main document declares."""

    def included(self, fileref: str) -> Element | None:
        return self.files.get(fileref)


_XSI_SCHEMA = "{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation"


def read_bundle(content: bytes) -> FormexBundle:
    """Parse every file of the bundle and order the documents by the descriptor."""
    with zipfile.ZipFile(io.BytesIO(content)) as bundle:
        parsed = {
            name: parse_xml(bundle.read(name))
            for name in bundle.namelist()
            if name.endswith(".xml")
        }

    descriptors = [
        n for n, root in parsed.items() if root.tag == "DOC" and root.find("FMX") is not None
    ]
    if len(descriptors) != 1:
        raise BundleError(f"expected one descriptor, found {len(descriptors)}")
    descriptor = parsed[descriptors[0]]
    metadata = {descriptors[0]} | {n for n, root in parsed.items() if root.tag == "PUBLICATION"}
    acts = {n: root for n, root in parsed.items() if n not in metadata}

    documents: list[BundleDocument] = []
    for pub in descriptor.find("FMX"):
        if pub.tag not in ("DOC.MAIN.PUB", "DOC.SUB.PUB"):
            continue
        role: Role = "main" if pub.tag == "DOC.MAIN.PUB" else "sub"
        for ref in pub.iter("REF.PHYS"):
            if ref.get("TYPE") != "DOC.XML":
                continue
            name = ref.get("FILE")
            if name not in acts:
                raise BundleError(f"descriptor lists {name!r}, which is not in the bundle")
            seq, kind = pub.get("NO.SEQ", ""), pub.get("TYPE")
            documents.append(BundleDocument(role, seq, kind, name, acts[name]))
    if not documents or documents[0].role != "main":
        raise BundleError("descriptor lists no main document")

    listed = {d.filename for d in documents}
    included = {
        inc.get("FILEREF")
        for root in acts.values()
        for inc in root.iter("INCL.ELEMENT")
        if inc.getparent() is not None and inc.getparent().tag != "INCLUSIONS"
    }
    for name in sorted(set(acts) - listed - included):
        documents.append(BundleDocument("unreferenced", "", None, name, acts[name]))

    return FormexBundle(
        documents=tuple(documents),
        files=acts,
        schema=documents[0].root.get(_XSI_SCHEMA),
    )
