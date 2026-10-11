"""The dataset (S7, ADR-0013): one JSON line per node, one file per work and language.

A dataset is built from the locked sources only, after every check has passed:
each document is parsed, its inherited identifiers are found in the XHTML of
the same work and language (``eucite.crosscheck``), and its languages are in
parity (``eucite.parity``). If anything fails, nothing is written.

The output is a function of the locked bytes and of the version of this
package: building twice gives the same bytes, on any machine that has the
sources (``eucite fetch --frozen``). Nothing in it records when or where it was
built.

Lines follow document order, and carry no field that changes when unrelated
nodes change — no position, no retrieval time — so that the diff of two
versions of a file shows the nodes that changed and nothing else.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
import tarfile
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files as package_files
from pathlib import Path
from typing import Any

from eucite import DISCLAIMER, DISCLAIMER_IT, __version__
from eucite.cache import CacheCorruptionError, LockEntry, ObjectStore, SourceLock
from eucite.canonical import CANONICAL_VERSION
from eucite.corpus import load_document, locked_payload
from eucite.crosscheck import CrossCheck, crosscheck, xhtml_identifiers
from eucite.nodes import Document, Node
from eucite.parity import ParityError, require_parity
from eucite.parse import ParseError
from eucite.sources import LANGUAGES, WORKS, Manifestation, SourceKey, Work

__all__ = [
    "ATTRIBUTION",
    "DATASET_FORMAT",
    "FIELDS",
    "BuildError",
    "Dataset",
    "DatasetError",
    "build",
    "check",
    "jsonl",
    "read_dataset",
    "read_nodes",
    "record",
    "write",
    "write_archive",
]

DATASET_FORMAT = 1
"""Bumped whenever a line changes shape: a field added, removed or redefined."""

FIELDS = (
    "id",
    "type",
    "parent",
    "label",
    "heading",
    "text",
    "notes",
    "amendments",
    "deleted",
    "id_provenance",
    "id_basis",
    "source_ref",
    "text_sha256",
    "work",
    "language",
)
"""The fields of a line, in this order. Identifier first, so that a diff reads."""

ATTRIBUTION = (
    "Contains information from EUR-Lex, © European Union, 1998-2026, licensed under "
    "CC BY 4.0. Structured, identified and diffed by EUCITE. Modified from the original."
)

MANIFEST = "manifest.json"
LOCK = "sources.lock.json"
README = "README.md"
LICENCE = "LICENSE"


class BuildError(Exception):
    """A dataset cannot be built: a source is missing or a check failed."""


class DatasetError(Exception):
    """A dataset on disk does not match its manifest or its hashes."""


# -- lines ---------------------------------------------------------------------------


def _line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def record(node: Node, document: Document) -> dict[str, Any]:
    data = node.model_dump(mode="json")
    data["work"] = document.work
    data["language"] = document.language
    return {field: data[field] for field in FIELDS}


def jsonl(document: Document) -> bytes:
    """The nodes of a document, one JSON line each, in document order."""
    return "".join(_line(record(n, document)) + "\n" for n in document.nodes).encode("utf-8")


def read_nodes(content: bytes) -> tuple[Node, ...]:
    """Read the lines of a dataset file back into nodes, checking every text hash.

    The position of a node is its line: ``order`` is the line index.
    """
    nodes = []
    for index, line in enumerate(content.decode("utf-8").splitlines()):
        data = json.loads(line)
        if list(data) != list(FIELDS):
            raise DatasetError(f"line {index + 1}: fields {list(data)} instead of {list(FIELDS)}")
        expected = {k: data.pop(k) for k in ("text_sha256", "deleted", "work", "language")}
        node = Node(order=index, **data)
        if node.text_sha256 != expected["text_sha256"] or node.deleted != expected["deleted"]:
            raise DatasetError(f"line {index + 1} ({node.id}): text or deletion does not match")
        nodes.append(node)
    return tuple(nodes)


# -- building ------------------------------------------------------------------------


@dataclass(frozen=True)
class Dataset:
    files: dict[str, bytes]
    """Every file of the dataset, by name."""

    @property
    def manifest(self) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads(self.files[MANIFEST])
        return loaded


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_name(document: Document) -> str:
    return f"{document.work}.{document.language}.jsonl"


def _load(
    work: Work, language: str, store: ObjectStore, lock: SourceLock
) -> tuple[Document, CrossCheck]:
    try:
        document = load_document(work.celex, language, store=store, lock=lock)
        xhtml = locked_payload(
            SourceKey(work.celex, language, Manifestation.XHTML), store=store, lock=lock
        )
    except (KeyError, FileNotFoundError, CacheCorruptionError) as exc:
        raise BuildError(f"{work.celex}/{language}: {exc}; run `eucite fetch --frozen`") from exc
    except ParseError as exc:
        raise BuildError(f"{work.celex}/{language}: {exc}") from exc
    check = crosscheck(document, xhtml_identifiers(xhtml))
    if not check.ok:
        raise BuildError(
            f"{work.celex}/{language}: identifiers not found in EUR-Lex {list(check.missing)}, "
            f"EUR-Lex identifiers without a node {list(check.unmatched)}"
        )
    return document, check


def build(
    *,
    store: ObjectStore,
    lock: SourceLock,
    works: Sequence[Work] = WORKS,
    languages: Sequence[str] = LANGUAGES,
    dataset_version: str | None = None,
) -> Dataset:
    """Parse, check and serialise. Every language is parsed, whatever ``languages``
    asks for: parity cannot be checked on one language."""
    documents: list[Document] = []
    crosschecks: list[dict[str, Any]] = []
    parities: list[dict[str, Any]] = []
    used: list[LockEntry] = []
    for work in works:
        loaded = [_load(work, language, store, lock) for language in LANGUAGES]
        try:
            parity = require_parity([document for document, _ in loaded])
        except ParityError as exc:
            raise BuildError(str(exc)) from exc
        parities.append(
            {"work": work.celex, "languages": list(parity.languages), "nodes": parity.nodes}
        )
        for document, check in loaded:
            crosschecks.append(
                {
                    "work": work.celex,
                    "language": document.language,
                    "checked": check.checked,
                    "unchecked": check.unchecked,
                }
            )
            for manifestation in Manifestation:
                entry = lock.get(SourceKey(work.celex, document.language, manifestation))
                assert entry is not None
                used.append(entry)
            if document.language in languages:
                documents.append(document)

    files: dict[str, bytes] = {_file_name(d): jsonl(d) for d in documents}
    source_lock = SourceLock(entries=tuple(sorted(used, key=lambda e: e.key)))
    files[LOCK] = source_lock.to_json().encode("utf-8")
    files[LICENCE] = package_files("eucite").joinpath("data_licence.txt").read_bytes()
    files[README] = _readme(documents, dataset_version).encode("utf-8")
    manifest = {
        "format": DATASET_FORMAT,
        "generator": f"eucite {__version__}",
        "dataset_version": dataset_version,
        "licence": "CC-BY-4.0",
        "attribution": ATTRIBUTION,
        "canonical_version": CANONICAL_VERSION,
        "nodes": [
            {
                "path": _file_name(d),
                "work": d.work,
                "act": d.act,
                "language": d.language,
                "nodes": len(d.nodes),
                "source": str(SourceKey(d.work, d.language, Manifestation.FORMEX)),
            }
            for d in documents
        ],
        "sources": [
            {
                "source": str(e.key),
                "url": e.final_url,
                "retrieved_at": e.retrieved_at.isoformat(),
                "sha256": e.sha256,
                "canonical_sha256": e.canonical_sha256,
            }
            for e in source_lock.entries
        ],
        "checks": {"identifiers": crosschecks, "parity": parities},
        "files": {
            name: {"sha256": _sha256(c), "size": len(c)} for name, c in sorted(files.items())
        },
    }
    files[MANIFEST] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return Dataset(dict(sorted(files.items())))


def _readme(documents: Sequence[Document], dataset_version: str | None) -> str:
    title = f"EUCITE dataset {dataset_version}" if dataset_version else "EUCITE dataset"
    titles = {w.celex: w.title for w in WORKS}
    rows = "\n".join(
        f"| `{_file_name(d)}` | {titles.get(d.work, d.work)} | {d.language} | {len(d.nodes)} |"
        for d in documents
    )
    fields = ", ".join(f"`{f}`" for f in FIELDS)
    version_flag = f" --dataset-version {dataset_version}" if dataset_version else ""
    return f"""# {title}

Regulation (EU) 2024/1689 (the AI Act), its consolidated text and the act that
amended it, as identified nodes: articles, paragraphs, subparagraphs, points,
annexes, recitals. Built by `eucite {__version__}` from the sources listed in
`{LOCK}`.

| File | Work | Language | Nodes |
|---|---|---|---|
{rows}

## Format

One JSON object per line, one line per node, in document order. The fields, in
this order: {fields}.

- `id` is `<act>/<path>` (`32024R1689/art_6.para_3.subpara_2.point_a`): the same
  in every language and in every version of the act, as long as the provision
  is the same. `id_provenance` says whether it is inherited from the source or
  derived by the parser, and `id_basis` whether it rests on the source, a
  printed label or a position.
- `text` is the text of the node and of everything it contains, one block per
  line. `label` and `heading` are printed apart, footnotes are in `notes`.
- `amendments` are those the consolidated text records on the node. A deleted
  provision keeps its `id` and `label`, with `deleted: true` and no text.
- `text_sha256` is the SHA-256 of `text` in UTF-8.

## Provenance

`{MANIFEST}` lists every file with its checksum, the sources with their URL,
retrieval time and checksum, and the checks the dataset passed: every inherited
identifier found in EUR-Lex, the languages in parity.

To derive the dataset again from the same sources, with `eucite {__version__}`,
in this directory:

    eucite fetch --frozen --lock {LOCK} --cache cache
    eucite dump --out . --check --lock {LOCK} --cache cache{version_flag}

## Licence

CC BY 4.0, see `{LICENCE}`. Retain this notice:

> {ATTRIBUTION}

## Disclaimer

{DISCLAIMER}

*{DISCLAIMER_IT}*
"""


# -- disk ----------------------------------------------------------------------------


def write(dataset: Dataset, out: Path) -> None:
    """Write the dataset to ``out``, replacing a dataset already there.

    A directory that exists and is not a dataset (no manifest) is never
    touched. The new dataset is written beside it first, so an interrupted
    write leaves the old one in place.
    """
    if out.exists() and not out.is_dir():
        raise BuildError(f"{out} exists and is not a directory")
    if out.exists() and any(out.iterdir()) and not (out / MANIFEST).is_file():
        raise BuildError(f"{out} exists and is not a dataset directory: not overwriting it")
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    try:
        for name, content in dataset.files.items():
            (staging / name).write_bytes(content)
        staging.chmod(0o755)
        if out.exists():
            shutil.rmtree(out)
        staging.rename(out)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def check(dataset: Dataset, out: Path) -> list[str]:
    """Differences between ``dataset`` and the dataset in ``out``; empty if identical."""
    if not out.is_dir():
        return [f"{out} does not exist"]
    differences = []
    present = {p.name for p in out.iterdir() if p.is_file()}
    for name, content in dataset.files.items():
        if name not in present:
            differences.append(f"{name}: missing")
        elif (out / name).read_bytes() != content:
            differences.append(f"{name}: differs")
    differences += [
        f"{name}: not part of the dataset" for name in sorted(present - set(dataset.files))
    ]
    return differences


def write_archive(dataset: Dataset, path: Path, *, root: str) -> str:
    """A reproducible ``.tar.gz`` of the dataset; return its SHA-256.

    Entries are sorted and carry no owner; their time is the latest retrieval
    of a source, and the gzip header has no time. The same dataset gives the
    same archive with the same compression library.
    """
    times = [datetime.fromisoformat(s["retrieved_at"]) for s in dataset.manifest["sources"]]
    mtime = int(max(times).timestamp()) if times else 0
    buffer = io.BytesIO()
    with (
        gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0, compresslevel=9) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as tar,
    ):
        for name, content in dataset.files.items():
            info = tarfile.TarInfo(f"{root}/{name}")
            info.size, info.mtime, info.mode = len(content), mtime, 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(content))
    data = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha256(data)


def read_dataset(directory: Path) -> dict[tuple[str, str], tuple[Node, ...]]:
    """Read a dataset written by :func:`write`, verifying every checksum.

    Returns the nodes of each file by ``(work, language)``.
    """
    manifest = json.loads((directory / MANIFEST).read_bytes())
    if manifest.get("format") != DATASET_FORMAT:
        raise DatasetError(f"dataset format {manifest.get('format')}, expected {DATASET_FORMAT}")
    for name, meta in manifest["files"].items():
        if _sha256((directory / name).read_bytes()) != meta["sha256"]:
            raise DatasetError(f"{name}: checksum does not match the manifest")
    return {
        (entry["work"], entry["language"]): read_nodes((directory / entry["path"]).read_bytes())
        for entry in manifest["nodes"]
    }
