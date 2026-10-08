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

from ai_act_corpus import DISCLAIMER, __version__
from ai_act_corpus.cache import ObjectStore, SourceLock
from ai_act_corpus.cellar import CellarClient
from ai_act_corpus.fetch import Outcome, fetch_sources
from ai_act_corpus.sources import LANGUAGES, WORKS, Manifestation, all_sources, work

DEFAULT_CACHE = Path("cache")
DEFAULT_LOCK = Path("sources.lock.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-act-corpus",
        description="Structured representation of Regulation (EU) 2024/1689.",
        epilog=DISCLAIMER,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ai-act-corpus {__version__}",
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
    fetch.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="cache directory")
    fetch.add_argument("--lock", type=Path, default=DEFAULT_LOCK, help="source lock file")
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
        )
    lock_written = report.lock.save(args.lock)

    for r in report.results:
        if r.outcome is Outcome.FAILED or r.entry is None:
            print(f"{r.outcome:<9} {r.key}  {r.error}")
        else:
            print(f"{r.outcome:<9} {r.key}  sha256:{r.entry.sha256[:12]}  {r.entry.size:>9} B")
    print(
        f"{len(report.results)} sources, {report.requests} requests, "
        f"{len(report.failed)} failed; lock {'updated' if lock_written else 'unchanged'}"
    )
    return 1 if report.failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "fetch":
        return _cmd_fetch(args)

    # ``error`` exits; reached only if a subcommand is registered without a handler.
    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
