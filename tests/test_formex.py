"""Reading a Formex bundle as one logical document, whatever its files are called."""

from __future__ import annotations

import io
import zipfile

import pytest
from lxml import etree

from eucite.formex import BundleError, read_bundle
from tests.doubles import formex_act, formex_bundle


def zipped(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, text in members.items():
            bundle.writestr(name, text)
    return buffer.getvalue()


def test_documents_follow_the_descriptor_not_the_file_names() -> None:
    content = formex_bundle(
        formex_act("<P>main</P>"),
        (formex_act("<P>first annex</P>", root="ANNEX"), formex_act("<P>second</P>", root="ANNEX")),
        reverse_members=True,
    )
    docs = read_bundle(content).documents
    assert [(d.role, d.seq, d.kind) for d in docs] == [
        ("main", "0001", None),
        ("sub", "0001.0001", "ANNEX"),
        ("sub", "0001.0002", "ANNEX"),
    ]
    assert docs[1].root.findtext("P") == "first annex"


def test_metadata_files_are_not_documents() -> None:
    names = {d.filename for d in read_bundle(formex_bundle(formex_act("<P/>"))).documents}
    assert not any(".doc." in n or ".toc." in n for n in names)


def test_an_unexpected_file_is_kept_as_unreferenced() -> None:
    content = formex_bundle(formex_act("<P/>"), extra={"Z.xml": b"<ANNEX><P>?</P></ANNEX>"})
    assert read_bundle(content).documents[-1].role == "unreferenced"


def test_an_included_file_is_not_unreferenced() -> None:
    act = '<QUOT.S><INCL.ELEMENT FILEREF="INC.xml" TYPE="FORMEX.DOC"/></QUOT.S>'
    content = formex_bundle(formex_act(act), included={"INC.xml": formex_act("<P/>", root="ANNEX")})
    bundle = read_bundle(content)
    assert [d.role for d in bundle.documents] == ["main"]
    assert bundle.included("INC.xml") is not None


def test_processing_instructions_survive_parsing() -> None:
    """The consolidated text records its amendments as processing instructions."""
    act = '<?CLG.MDFO ACTION="DELETED"?><P>deleted text</P><?CLG.MDFC?>'
    root = read_bundle(formex_bundle(formex_act(act))).documents[0].root
    targets = [pi.target for pi in root.iter(etree.ProcessingInstruction)]
    assert targets == ["CLG.MDFO", "CLG.MDFC"]


def test_schema_is_read_from_the_main_document() -> None:
    schema = read_bundle(formex_bundle(formex_act("<P/>"))).schema
    assert schema is not None and schema.endswith("formex-06.02.1-20231031.xd")


@pytest.mark.parametrize(
    ("members", "reason"),
    [
        ({"A.xml": "<ACT/>"}, "descriptor"),
        (
            {
                "A.doc.xml": '<DOC><FMX><DOC.MAIN.PUB NO.SEQ="0001">'
                '<REF.PHYS FILE="gone.xml" TYPE="DOC.XML"/></DOC.MAIN.PUB></FMX></DOC>',
            },
            "not in the bundle",
        ),
        ({"A.doc.xml": "<DOC><FMX/></DOC>"}, "no main document"),
        ({"A.doc.xml": "<DOC><FMX>"}, "malformed"),
    ],
)
def test_unreadable_bundles_are_refused(members: dict[str, str], reason: str) -> None:
    with pytest.raises(BundleError, match=reason):
        read_bundle(zipped(members))
