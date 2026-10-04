"""Generate or serve the Auto Trading AegisGraph read-only knowledge graph."""

from __future__ import annotations

import argparse
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from aegis_graph.audit import (
    append_invocation,
    default_state_dir,
    load_invocations,
    new_record,
)
from aegis_graph.integrations.auto_trading import SOURCE_ANCHORS, create_engine
from aegis_graph.integrations.auto_trading_audit import audit_target
from aegis_graph.ui import write_graph_html
from aegis_graph.ui.auto_trading_labels import AUTO_TRADING_DISPLAY_LABELS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="read-only target project path")
    parser.add_argument(
        "--output",
        default=str(default_state_dir() / "reports" / "aegis-auto-trading-graph.html"),
    )
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8798)
    args = parser.parse_args()

    started = time.monotonic()
    audit = audit_target(args.target)
    append_invocation(new_record(
        mode="reg_dashboard",
        target=args.target,
        source="aegis_reg",
        verdict=audit.proof.verdict.value,
        evidence_snapshot_id=audit.evidence.snapshot_id,
        target_commit=audit.evidence.commit_sha,
        duration_ms=round((time.monotonic() - started) * 1000),
    ))
    invocations = load_invocations(limit=200)
    engine = create_engine()
    output = write_graph_html(
        args.output,
        engine.graph,
        proof=audit.proof,
        fact_values=audit.evidence.fact_values,
        evidence_sources=audit.evidence.sources,
        source_anchors=SOURCE_ANCHORS,
        display_labels=AUTO_TRADING_DISPLAY_LABELS,
        invocations=invocations,
        title="AegisGraph · 自动交易 Auto Trading",
        target_root=args.target,
    )
    print(f"GRAPH={output}")
    print(f"VERDICT={audit.proof.verdict.value.upper()}")
    if not args.serve:
        return
    handler = partial(SimpleHTTPRequestHandler, directory=str(output.parent))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"URL=http://{args.host}:{args.port}/{output.name}")
    server.serve_forever()


if __name__ == "__main__":
    main()
