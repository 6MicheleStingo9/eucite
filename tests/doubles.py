"""Offline doubles for Cellar: the suite never touches the network."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import unquote

import httpx

from eucite.cellar import CellarClient, RetryPolicy
from eucite.sources import Manifestation, SourceKey, all_sources

FIXED_NOW = datetime(2026, 10, 8, 10, 0, tzinfo=UTC)

Handler = Callable[[httpx.Request], httpx.Response]


def formex_zip(members: dict[str, bytes] | None = None) -> bytes:
    """A minimal, well-formed Formex bundle."""
    if members is None:
        members = {"L_TEST.doc.fmx.xml": b"<DOC/>", "L_TEST.000101.fmx.xml": b"<ACT/>"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, data in members.items():
            bundle.writestr(name, data)
    return buffer.getvalue()


SCHEMA = "http://formex.publications.europa.eu/schema/formex-06.02.1-20231031.xd"
XSI = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'


def formex_act(body: str, *, root: str = "ACT", schema: str = SCHEMA) -> str:
    """A Formex act with a bibliographic header and ``body`` as its content."""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><{root} {XSI} '
        f'xsi:noNamespaceSchemaLocation="{schema}">'
        '<BIB.INSTANCE><DOCUMENT.REF FILE="x"><PAGE.FIRST>1</PAGE.FIRST></DOCUMENT.REF>'
        f"</BIB.INSTANCE>{body}</{root}>"
    )


def formex_bundle(
    main: str,
    annexes: tuple[str, ...] = (),
    *,
    included: dict[str, str] | None = None,
    extra: dict[str, bytes] | None = None,
    prefix: str = "L_TEST",
    reverse_members: bool = False,
    date_time: tuple[int, int, int, int, int, int] = (2026, 8, 11, 17, 9, 50),
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    """A Formex bundle: descriptor, table of contents, main act, annexes, inclusions."""
    names = [f"{prefix}.000101.fmx.xml"] + [
        f"{prefix}.{124 + i:04d}01.fmx.xml" for i in range(len(annexes))
    ]
    pubs = [
        f'<DOC.MAIN.PUB NO.SEQ="0001"><REF.PHYS FILE="{names[0]}" TYPE="DOC.XML"/></DOC.MAIN.PUB>'
    ]
    pubs += [
        f'<DOC.SUB.PUB NO.SEQ="0001.{i:04d}" TYPE="ANNEX">'
        f'<REF.PHYS FILE="{name}" TYPE="DOC.XML"/></DOC.SUB.PUB>'
        for i, name in enumerate(names[1:], 1)
    ]
    members = {
        f"{prefix}.doc.fmx.xml": f'<?xml version="1.0"?><DOC><FMX>{"".join(pubs)}</FMX></DOC>',
        f"{prefix}.toc.fmx.xml": "<PUBLICATION><OJ>table of contents</OJ></PUBLICATION>",
        names[0]: main,
        **dict(zip(names[1:], annexes, strict=True)),
        **(included or {}),
    }
    encoded = {name: text.encode() for name, text in members.items()} | (extra or {})
    order = sorted(encoded, reverse=reverse_members)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name in order:
            info = zipfile.ZipInfo(name, date_time=date_time)
            info.compress_type = compression
            bundle.writestr(info, encoded[name])
    return buffer.getvalue()


def xhtml(body: str = "") -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<html xmlns="http://www.w3.org/1999/xhtml"><body>{body}</body></html>'
    ).encode()


def payload_for(key: SourceKey, revision: int = 0) -> bytes:
    """Distinct, valid content for each key, so that every source hashes differently."""
    marker = f"{key}#{revision}"
    if key.manifestation is Manifestation.FORMEX:
        return formex_bundle(formex_act(f"<ENACTING.TERMS><P>{marker}</P></ENACTING.TERMS>"))
    return xhtml(f"<p>{marker}</p>")


MEDIA_TYPES = {
    Manifestation.FORMEX.accept: "application/zip;charset=UTF-8",
    Manifestation.XHTML.accept: "application/xhtml+xml;charset=UTF-8",
}


class FakeCellar:
    """Serves payloads by CELEX, Accept and Accept-Language; records every request.

    Responses in ``scripted`` are served first, in order, whatever is asked.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.payloads: dict[tuple[str, str, str], bytes] = {}
        self.scripted: list[httpx.Response | Exception] = []

    def serve(self, key: SourceKey, content: bytes) -> None:
        self.payloads[(key.celex, key.accept, key.lang)] = content

    def serve_all(self, revision: int = 0) -> None:
        for key in all_sources():
            self.serve(key, payload_for(key, revision))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.scripted:
            scripted = self.scripted.pop(0)
            if isinstance(scripted, Exception):
                raise scripted
            return scripted
        celex = unquote(request.url.path.rsplit("/", 1)[-1])
        accept = request.headers.get("Accept", "")
        found = self.payloads.get((celex, accept, request.headers.get("Accept-Language", "")))
        if found is None:
            return httpx.Response(404)
        return httpx.Response(200, content=found, headers={"Content-Type": MEDIA_TYPES[accept]})


def make_client(
    handler: Handler,
    *,
    sleeps: list[float] | None = None,
    retry: RetryPolicy | None = None,
) -> CellarClient:
    record = sleeps.append if sleeps is not None else (lambda _seconds: None)
    return CellarClient(
        httpx.Client(transport=httpx.MockTransport(handler)),
        retry=retry,
        sleep=record,
        clock=lambda: FIXED_NOW,
    )
