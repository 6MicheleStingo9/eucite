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

from ai_act_corpus import DISCLAIMER, __version__


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
    parser.add_subparsers(dest="command", metavar="COMMAND")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    # Unreachable while no subcommand is registered; kept so that adding one
    # in S1 does not require restructuring this function. ``error`` exits.
    parser.error(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
