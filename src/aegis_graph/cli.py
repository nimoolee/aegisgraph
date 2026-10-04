"""Public command-line interface for AegisGraph."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from aegis_graph import __version__
from aegis_graph.audit import append_invocation, new_record
from aegis_graph.demo import render_demo
from aegis_graph.discovery import discover_python
from aegis_graph.semantics import detect_conflicts, unify_discovery
from aegis_graph.semantics.render import render_conflicts, render_unification


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aegis",
        description="Semantic verification and change-proof tooling for AI-generated code.",
    )
    parser.add_argument("--version", action="version", version=f"AegisGraph {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Discover and unify candidate semantics in a Python codebase")
    discover.add_argument("target", nargs="?", default=".")
    discover.add_argument("--contains", help="Filter candidate concepts by implementation symbol")
    discover.add_argument("--limit", type=int, default=40)
    discover.add_argument("--conflicts", action="store_true", help="Also print conservative semantic conflicts")

    check = sub.add_parser("check", help="CI-friendly semantic conflict check for a Python codebase")
    check.add_argument("target", nargs="?", default=".")
    check.add_argument("--contains", help="Filter rendered candidate concepts")
    check.add_argument("--limit", type=int, default=20)

    sub.add_parser("demo", help="Run a dependency-free invariant proof demo")
    return parser


def _append_cli_audit(*, target: str, verdict: str | None, note: str) -> None:
    """Best-effort Aegis-owned audit logging; never mutate or gate the target."""

    try:
        append_invocation(
            new_record(
                mode="semantic_discovery",
                target=target,
                source="aegis_cli",
                verdict=verdict,
                note=note,
            )
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"AEGISGRAPH AUDIT WARNING: {exc}", file=sys.stderr)


def _discover(args: argparse.Namespace, *, fail_on_conflict: bool) -> int:
    discovery = discover_python(args.target)
    unified = unify_discovery(discovery)
    print(render_unification(unified, contains=args.contains, limit=args.limit))
    if discovery.warnings:
        print("\nAEGISGRAPH SOURCE WARNINGS", file=sys.stderr)
        for warning in discovery.warnings:
            print(f"- {warning}", file=sys.stderr)
    conflicts = detect_conflicts(unified)
    if fail_on_conflict or getattr(args, "conflicts", False):
        print()
        print(render_conflicts(conflicts, unified))

    scan_incomplete = bool(discovery.warnings)
    verdict: str | None
    if fail_on_conflict and conflicts.conflicts:
        exit_code = 1
        verdict = "fail"
    elif fail_on_conflict and scan_incomplete:
        exit_code = 2
        verdict = "unknown"
        print(
            "\nAEGISGRAPH SCAN STATUS: UNKNOWN — source evidence is incomplete; "
            "see warnings above.",
            file=sys.stderr,
        )
    else:
        exit_code = 0
        verdict = "pass" if fail_on_conflict else None

    _append_cli_audit(
        target=args.target,
        verdict=verdict,
        note=(
            f"conflicts={len(conflicts.conflicts)} concepts={len(unified.concepts)} "
            f"scan_warnings={len(discovery.warnings)}"
        ),
    )
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "demo":
            print(render_demo())
            return 0
        if args.command == "discover":
            return _discover(args, fail_on_conflict=False)
        if args.command == "check":
            return _discover(args, fail_on_conflict=True)
        raise AssertionError(f"unhandled command: {args.command}")
    except (OSError, ValueError) as exc:
        print(f"AEGISGRAPH ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def console_main() -> None:
    raise SystemExit(main())
