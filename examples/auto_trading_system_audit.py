"""Run the first real AegisGraph read-only system proof against Auto Trading."""

from __future__ import annotations

import argparse
import time

from aegis_graph.audit import append_invocation, new_record
from aegis_graph.integrations.auto_trading_audit import audit_target, render_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="Path to the read-only auto-trading target project")
    args = parser.parse_args()
    started = time.monotonic()
    audit = audit_target(args.target)
    append_invocation(new_record(
        mode="accepted_rule_proof",
        target=args.target,
        source="aegis_cli",
        verdict=audit.proof.verdict.value,
        evidence_snapshot_id=audit.evidence.snapshot_id,
        target_commit=audit.evidence.commit_sha,
        duration_ms=round((time.monotonic() - started) * 1000),
    ))
    print(render_audit(audit))


if __name__ == "__main__":
    main()
