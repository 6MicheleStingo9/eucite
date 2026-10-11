"""Command line entry point.

Subcommands are added by the step that implements them, so that ``--help``
never advertises something that does not work yet:

    fetch   S1 — acquisition from Cellar
    dump    S7 — dataset export
    diff    S8 — amendment diffs
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from eucite import DISCLAIMER, __version__
from eucite.cache import ObjectStore, SourceLock
from eucite.cellar import CellarClient
from eucite.dataset import BuildError, build, check, write, write_archive
from eucite.fetch import Outcome, fetch_sources
from eucite.sources import LANGUAGES, WORKS, Manifestation, all_sources, work

DEFAULT_CACHE = Path("cache")
DEFAULT_LOCK = Path("sources.lock.json")
DEFAULT_OUT = Path("dist-data")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eucite",
        description="Structured representation of Regulation (EU) 2024/1689.",
        epilog=DISCLAIMER,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"eucite {__version__}",
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    fetch = commands.add_parser(
        "fetch",
        help="acquire the source documents from Cellar",
        description=(
            "Download every source the corpus is composed of into an immutable "
            "cache and record it in the source lock. Sources already in the lock "
            "and in the cache are not requested again unless --refresh is given."
        ),
    )
    fetch.add_argument(
        "--work",
        action="append",
        choices=[w.celex for w in WORKS],
        help="only this work (repeatable; default: all)",
    )
    fetch.add_argument(
        "--lang",
        action="append",
        choices=LANGUAGES,
        help="only this language, ISO 639-3 (repeatable; default: all)",
    )
    fetch.add_argument(
        "--manifestation",
        action="append",
        choices=[m.value for m in Manifestation],
        help="only this manifestation (repeatable; default: all)",
    )
    fetch.add_argument(
        "--refresh",
        action="store_true",
        help="download again even if the source is cached",
    )
    fetch.add_argument(
        "--frozen",
        action="store_true",
        help="restore exactly what the lock records; fail if a source is missing "
        "from it or Cellar serves different bytes, and never change it",
    )
    fetch.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="cache directory")
    fetch.add_argument("--lock", type=Path, default=DEFAULT_LOCK, help="source lock file")

    dump = commands.add_parser(
        "dump",
        help="build the dataset from the cached sources",
        description=(
            "Parse the locked sources, check every inherited identifier against "
            "EUR-Lex and the languages against each other, and write one JSON "
            "line per node, one file per work and language, with a manifest. "
            "Nothing is written if a check fails."
        ),
    )
    dump.add_argument("--out", type=Path, default=DEFAULT_OUT, help="dataset directory")
    dump.add_argument(
        "--work",
        action="append",
        choices=[w.celex for w in WORKS],
        help="only this work (repeatable; default: all)",
    )
    dump.add_argument(
        "--lang",
        action="append",
        choices=LANGUAGES,
        help="only this language (repeatable; default: all; parity is checked on all)",
    )
    dump.add_argument("--dataset-version", help="version recorded in the manifest")
    mode = dump.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="write nothing; fail if --out differs from what would be written",
    )
    mode.add_argument(
        "--archive", type=Path, help="also write a reproducible .tar.gz of the dataset"
    )
    dump.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="cache directory")
    dump.add_argument("--lock", type=Path, default=DEFAULT_LOCK, help="source lock file")
    return parser


def _make_client() -> CellarClient:
    return CellarClient()


def _cmd_fetch(args: argparse.Namespace) -> int:
    works = tuple(work(c) for c in args.work) if args.work else WORKS
    langs = tuple(args.lang) if args.lang else LANGUAGES
    manifestations = (
        tuple(Manifestation(m) for m in args.manifestation)
        if args.manifestation
        else tuple(Manifestation)
    )
    keys = all_sources(works, langs, manifestations)

    with _make_client() as client:
        report = fetch_sources(
            keys,
            client=client,
            store=ObjectStore(args.cache),
            lock=SourceLock.load(args.lock),
            refresh=args.refresh,
            frozen=args.frozen,
        )
    lock_written = False if args.frozen else report.lock.save(args.lock)

    for r in report.results:
        if r.outcome is Outcome.FAILED or r.entry is None:
            print(f"{r.outcome:<9} {r.key}  {r.error}")
        else:
            note = "  (presentation only)" if r.presentation_only else ""
            print(
                f"{r.outcome:<9} {r.key}  sha256:{r.entry.sha256[:12]}  {r.entry.size:>9} B{note}"
            )
    print(
        f"{len(report.results)} sources, {report.requests} requests, "
        f"{len(report.failed)} failed; lock {'updated' if lock_written else 'unchanged'}"
    )
    return 1 if report.failed else 0


def _cmd_dump(args: argparse.Namespace) -> int:
    works = tuple(work(c) for c in args.work) if args.work else WORKS
    langs = tuple(args.lang) if args.lang else LANGUAGES
    try:
        dataset = build(
            store=ObjectStore(args.cache),
            lock=SourceLock.load(args.lock),
            works=works,
            languages=langs,
            dataset_version=args.dataset_version,
        )
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    manifest = dataset.manifest
    for entry in manifest["nodes"]:
        sha = manifest["files"][entry["path"]]["sha256"]
        print(f"{entry['path']:<36} {entry['nodes']:>5} nodes  sha256:{sha[:12]}")
    identifiers = manifest["checks"]["identifiers"]
    checked = sum(c["checked"] for c in identifiers)
    unchecked = sum(c["unchecked"] for c in identifiers)
    print(
        f"checks: {checked} inherited identifiers found in EUR-Lex "
        f"({unchecked} paragraph references not checkable there); "
        f"{len(manifest['checks']['parity'])} works with their languages in parity"
    )

    if args.check:
        differences = check(dataset, args.out)
        for difference in differences:
            print(f"differs   {difference}")
        print(f"{args.out}: " + ("differs" if differences else "identical"))
        return 1 if differences else 0

    try:
        write(dataset, args.out)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {args.out}/ ({len(dataset.files)} files)")
    if args.archive:
        root = "eucite-dataset" + (f"-{args.dataset_version}" if args.dataset_version else "")
        digest = write_archive(dataset, args.archive, root=root)
        print(f"wrote {args.archive}  sha256:{digest}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "fetch":
        return _cmd_fetch(args)
    if args.command == "dump":
        return _cmd_dump(args)

    # ``error`` exits; reached only if a subcommand is registered without a handler.
    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
