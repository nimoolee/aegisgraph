"""Run read-only Semantic Discovery v0.1 against a Python target repository."""

from __future__ import annotations

import argparse

from aegis_graph.discovery.python_ast import discover_python
from aegis_graph.discovery.render import render_discovery


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="target repository/path to inspect read-only")
    parser.add_argument("--contains", help="optional post-discovery text filter")
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    report = discover_python(args.target)
    print(render_discovery(report, contains=args.contains, limit=args.limit))


if __name__ == "__main__":
    main()
