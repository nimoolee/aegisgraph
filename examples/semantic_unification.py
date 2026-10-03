"""Build a read-only candidate semantic graph and detect conservative conflicts."""

from __future__ import annotations

import argparse
import time

from aegis_graph.audit import append_invocation, new_record
from aegis_graph.discovery import discover_python
from aegis_graph.semantics import detect_conflicts, unify_discovery
from aegis_graph.semantics.render import render_conflicts, render_unification


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="target repository/path to inspect read-only")
    parser.add_argument("--contains", help="filter candidate concepts by implementation symbol")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--conflicts", action="store_true")
    args = parser.parse_args()

    started = time.monotonic()
    discovery = discover_python(args.target)
    unified = unify_discovery(discovery)
    print(render_unification(unified, contains=args.contains, limit=args.limit))
    conflicts = detect_conflicts(unified) if args.conflicts else None
    if conflicts is not None:
        print()
        print(render_conflicts(conflicts, unified))
    append_invocation(new_record(
        mode="semantic_discovery",
        target=args.target,
        source="aegis_cli",
        duration_ms=round((time.monotonic() - started) * 1000),
        note=(f"conflicts={len(conflicts.conflicts)}" if conflicts is not None else f"concepts={len(unified.concepts)}"),
    ))


if __name__ == "__main__":
    main()
