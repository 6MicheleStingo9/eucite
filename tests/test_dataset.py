"""The dataset (S7): format, determinism, round trip, refusals, readable diffs."""

from __future__ import annotations

import difflib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from eucite import DISCLAIMER, DISCLAIMER_IT
from eucite.dataset import (
    FIELDS,
    BuildError,
    DatasetError,
    build,
    check,
    jsonl,
    read_dataset,
    read_nodes,
    write,
    write_archive,
)
from eucite.parse import parse_formex
from eucite.sources import LANGUAGES, WORKS, Manifestation, SourceKey
from tests import synthetic
from tests.builders import act, alinea, article
from tests.doubles import FIXED_NOW, formex_bundle

BASE = "32024R1689"


def files_of(root: Path) -> dict[str, bytes]:
    store, lock = synthetic.corpus(root)
    return build(store=store, lock=lock).files


def test_one_file_per_work_and_language_and_the_release_files(tmp_path: Path) -> None:
    files = files_of(tmp_path)
    expected = {f"{w.celex}.{lang}.jsonl" for w in WORKS for lang in LANGUAGES}
    assert set(files) == expected | {"manifest.json", "sources.lock.json", "README.md", "LICENSE"}


def test_lines_are_nodes_in_document_order_with_fields_in_order(tmp_path: Path) -> None:
    lines = files_of(tmp_path)[f"{BASE}.ita.jsonl"].decode().splitlines()
    records = [json.loads(line) for line in lines]
    assert all(list(r) == list(FIELDS) for r in records)
    assert [r["id"].split("/")[-1] for r in records] == [
        BASE,
        "cit_1",
        "rct_1",
        "cpt_I",
        "art_1",
        "art_1.para_1",
        "art_1.para_1.subpara_1",
        "art_1.para_1.subpara_1.point_a",
        "art_1.para_1.subpara_1.point_b",
        "anx_I",
        "anx_I.point_1",
    ]
    assert {(r["work"], r["language"]) for r in records} == {(BASE, "ita")}
    assert records[7]["label"] == "a)"


def test_nodes_read_back_identical_and_checked() -> None:
    document = parse_formex(synthetic.formex("eng"), work=BASE, language="eng")
    content = jsonl(document)
    assert read_nodes(content) == document.nodes
    lines = content.splitlines(keepends=True)
    point = next(i for i, line in enumerate(lines) if b'point_a"' in line.split(b",")[0])
    lines[point] = lines[point].replace(b"the first rule", b"the first rules")
    with pytest.raises(DatasetError, match=r"\(32024R1689/art_1\.para_1\.subpara_1\.point_a\)"):
        read_nodes(b"".join(lines))


def test_the_build_is_deterministic(tmp_path: Path) -> None:
    store, lock = synthetic.corpus(tmp_path)
    assert build(store=store, lock=lock).files == build(store=store, lock=lock).files


def test_the_build_does_not_depend_on_hash_seeds(tmp_path: Path) -> None:
    _, lock = synthetic.corpus(tmp_path)
    (tmp_path / "sources.lock.json").write_text(lock.to_json())
    outputs = []
    for seed in ("1", "2"):
        out = tmp_path / f"out-{seed}"
        subprocess.run(
            [sys.executable, "-m", "eucite", "dump", "--out", str(out), "--cache",
             str(tmp_path / "cache"), "--lock", str(tmp_path / "sources.lock.json")],
            check=True,
            capture_output=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )  # fmt: skip
        outputs.append({p.name: p.read_bytes() for p in sorted(out.iterdir())})
    assert outputs[0] == outputs[1]


def test_the_manifest_lists_checksums_sources_and_checks(tmp_path: Path) -> None:
    store, lock = synthetic.corpus(tmp_path)
    dataset = build(store=store, lock=lock, dataset_version="t.1")
    manifest = dataset.manifest
    assert (manifest["format"], manifest["dataset_version"], manifest["licence"]) == (
        1,
        "t.1",
        "CC-BY-4.0",
    )
    assert set(manifest["files"]) == set(dataset.files) - {"manifest.json"}
    assert len(manifest["sources"]) == 12
    assert {c["checked"] for c in manifest["checks"]["identifiers"]} == {6}
    assert [p["work"] for p in manifest["checks"]["parity"]] == [w.celex for w in WORKS]
    readme = " ".join(dataset.files["README.md"].decode().split())
    assert "Contains information from EUR-Lex" in readme
    assert DISCLAIMER in readme
    assert DISCLAIMER_IT in readme
    assert dataset.files["LICENSE"] == (Path(__file__).parent.parent / "LICENSE-DATA").read_bytes()


# -- refusals ------------------------------------------------------------------------


def test_a_parity_failure_builds_nothing(tmp_path: Path) -> None:
    def extra_point_in_italian(key: SourceKey) -> bytes | None:
        if key == SourceKey(BASE, "ita", Manifestation.FORMEX):
            return synthetic.formex("ita", {"a": "x;", "b": "y;", "c": "z."})
        return None

    store, lock = synthetic.corpus(tmp_path, extra_point_in_italian)
    with pytest.raises(
        BuildError, match=r"point_c — presence differs \(ita: present; eng: absent\)"
    ):
        build(store=store, lock=lock)


def test_parity_is_checked_even_for_one_language(tmp_path: Path) -> None:
    def extra_point_in_english(key: SourceKey) -> bytes | None:
        if key == SourceKey(BASE, "eng", Manifestation.FORMEX):
            return synthetic.formex("eng", {"a": "x;", "b": "y;", "c": "z."})
        return None

    store, lock = synthetic.corpus(tmp_path, extra_point_in_english)
    with pytest.raises(BuildError, match="presence differs"):
        build(store=store, lock=lock, languages=("ita",))


def test_an_identifier_missing_from_eurlex_builds_nothing(tmp_path: Path) -> None:
    def no_article(key: SourceKey) -> bytes | None:
        if key == SourceKey(BASE, "eng", Manifestation.XHTML):
            return synthetic.page(tuple(i for i in synthetic.IDENTIFIERS if i != "art_1"))
        return None

    store, lock = synthetic.corpus(tmp_path, no_article)
    with pytest.raises(
        BuildError, match=r"32024R1689/eng: identifiers not found in EUR-Lex \['art_1'\]"
    ):
        build(store=store, lock=lock)


def test_a_missing_source_asks_for_a_frozen_fetch(tmp_path: Path) -> None:
    store, lock = synthetic.corpus(tmp_path)
    entry = lock.get(SourceKey(BASE, "ita", Manifestation.FORMEX))
    assert entry is not None
    path = store.path_for(entry.sha256)
    path.chmod(0o644)
    path.unlink()
    with pytest.raises(BuildError, match="run `eucite fetch --frozen`"):
        build(store=store, lock=lock)


# -- disk ----------------------------------------------------------------------------


def test_write_then_check_then_read(tmp_path: Path) -> None:
    store, lock = synthetic.corpus(tmp_path)
    dataset = build(store=store, lock=lock)
    out = tmp_path / "dist"
    write(dataset, out)
    assert check(dataset, out) == []
    nodes = read_dataset(out)
    assert set(nodes) == {(w.celex, lang) for w in WORKS for lang in LANGUAGES}

    (out / f"{BASE}.eng.jsonl").write_bytes(b"{}\n")
    (out / "notes.txt").write_text("mine")
    assert check(dataset, out) == [
        f"{BASE}.eng.jsonl: differs",
        "notes.txt: not part of the dataset",
    ]
    with pytest.raises(DatasetError, match="checksum"):
        read_dataset(out)


def test_write_replaces_a_dataset_and_nothing_else(tmp_path: Path) -> None:
    store, lock = synthetic.corpus(tmp_path)
    dataset = build(store=store, lock=lock)
    out = tmp_path / "dist"
    write(dataset, out)
    (out / "stale.jsonl").write_text("old")
    write(dataset, out)
    assert check(dataset, out) == []

    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "thesis.tex").write_text("months of work")
    with pytest.raises(BuildError, match="not a dataset directory"):
        write(dataset, precious)
    assert (precious / "thesis.tex").read_text() == "months of work"


def test_the_archive_is_reproducible(tmp_path: Path) -> None:
    store, lock = synthetic.corpus(tmp_path)
    dataset = build(store=store, lock=lock, dataset_version="t.1")
    first = write_archive(dataset, tmp_path / "a.tar.gz", root="eucite-dataset-t.1")
    second = write_archive(dataset, tmp_path / "b.tar.gz", root="eucite-dataset-t.1")
    assert first == second
    with tarfile.open(tmp_path / "a.tar.gz") as tar:
        members = tar.getmembers()
        assert [m.name for m in members] == [f"eucite-dataset-t.1/{n}" for n in dataset.files]
        assert {(m.uid, m.gid, m.uname, m.mode) for m in members} == {(0, 0, "", 0o644)}
        assert {m.mtime for m in members} == {int(FIXED_NOW.timestamp())}
        extracted = tar.extractfile(members[0])
        assert extracted is not None
        assert extracted.read() == next(iter(dataset.files.values()))


# -- readable diffs --------------------------------------------------------------------


def changed_ids(before: bytes, after: bytes) -> tuple[list[str], list[str]]:
    """Identifiers of the lines removed and added between two versions of a file."""
    old, new = before.decode().splitlines(), after.decode().splitlines()
    removed: list[str] = []
    added: list[str] = []
    for line in difflib.unified_diff(old, new, lineterm="", n=0):
        if line.startswith(("---", "+++", "@@")):
            continue
        target = removed if line.startswith("-") else added
        target.append(json.loads(line[1:])["id"].split("/")[-1])
    return removed, added


def test_a_changed_word_changes_its_node_and_its_ancestors_only(tmp_path: Path) -> None:
    before = files_of(tmp_path / "before")[f"{BASE}.eng.jsonl"]

    def amended(key: SourceKey) -> bytes | None:
        if key.manifestation is Manifestation.FORMEX:
            return synthetic.formex(key.lang, {"a": "the first rule;", "b": "the amended rule."})
        return None

    store, lock = synthetic.corpus(tmp_path / "after", amended)
    after = build(store=store, lock=lock).files[f"{BASE}.eng.jsonl"]
    ancestors = ["art_1", "art_1.para_1", "art_1.para_1.subpara_1"]
    assert changed_ids(before, after) == (
        [*ancestors, "art_1.para_1.subpara_1.point_b"],
        [*ancestors, "art_1.para_1.subpara_1.point_b"],
    )


def test_an_inserted_point_is_one_more_line(tmp_path: Path) -> None:
    before = files_of(tmp_path / "before")[f"{BASE}.eng.jsonl"]

    def inserted(key: SourceKey) -> bytes | None:
        if key.manifestation is Manifestation.FORMEX:
            points = {"a": "the first rule;", "aa": "an inserted rule;", "b": "the second rule."}
            return synthetic.formex(key.lang, points)
        return None

    store, lock = synthetic.corpus(tmp_path / "after", inserted)
    after = build(store=store, lock=lock).files[f"{BASE}.eng.jsonl"]
    removed, added = changed_ids(before, after)
    ancestors = ["art_1", "art_1.para_1", "art_1.para_1.subpara_1"]
    assert removed == ancestors
    assert sorted(added) == sorted([*ancestors, "art_1.para_1.subpara_1.point_aa"])


def test_the_jsonl_is_utf8_without_escapes() -> None:
    text = "\u00abSistema di IA\u00bb: un sistema \u00e8 automatizzato."
    main = act(article("003", "Articolo 3", "Definizioni", alinea(text)))
    content = jsonl(parse_formex(formex_bundle(main), work=BASE, language="ita"))
    assert text.encode("utf-8") in content
    assert b"\\u" not in content
    assert content.endswith(b"\n")
