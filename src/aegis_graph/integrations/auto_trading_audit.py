"""AegisGraph-owned system audit for the automatic trading reference target."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aegis_graph.core.models import Change, ChangeType
from aegis_graph.integrations.auto_trading import create_engine
from aegis_graph.integrations.auto_trading_evidence import EvidenceSnapshot, collect_evidence
from aegis_graph.proof.models import ChangeProof


@dataclass(frozen=True, slots=True)
class AutoTradingSystemAudit:
    evidence: EvidenceSnapshot
    proof: ChangeProof


def audit_target(target_root: str | Path) -> AutoTradingSystemAudit:
    """Verify the whole authored Auto Trading constitution against real evidence.

    All graph facts are seeded deliberately: a system audit asks every authored
    invariant to prove itself. Missing evidence therefore becomes UNKNOWN instead
    of silently skipping a rule.
    """

    evidence = collect_evidence(target_root)
    engine = create_engine()
    change = Change(
        id=f"auto.system_audit.{evidence.snapshot_id}",
        type=ChangeType.STATE_CHANGE,
        summary="Read-only Auto Trading system constitution verification",
        changed_fact_ids=tuple(sorted(engine.graph.facts)),
        commit_sha=evidence.commit_sha,
        metadata={
            "target_root": evidence.target_root,
            "dirty_worktree": evidence.dirty_worktree,
            "evidence_snapshot_id": evidence.snapshot_id,
        },
    )
    proof = engine.analyze(change, fact_values=evidence.fact_values)
    return AutoTradingSystemAudit(evidence=evidence, proof=proof)


def render_audit(audit: AutoTradingSystemAudit) -> str:
    engine = create_engine()
    proof = audit.proof
    evidence = audit.evidence
    lines = [
        "AEGISGRAPH AUTO TRADING SYSTEM PROOF",
        f"Target: {evidence.target_root}",
        f"Evidence Snapshot: {evidence.snapshot_id}",
        f"Target Commit: {evidence.commit_sha or 'UNKNOWN'}",
        f"Dirty Worktree: {evidence.dirty_worktree}",
        "Boundary: READ_ONLY_TARGET",
        f"VERDICT: {proof.verdict.value.upper()}",
        "",
        "INVARIANT RESULTS",
    ]
    for check in proof.invariant_checks:
        invariant = engine.graph.invariants[check.invariant_id]
        expression = f" | Formula: {invariant.expression}" if invariant.expression else ""
        lines.append(
            f"{check.status.value.upper():7} {check.invariant_id}: {check.message}{expression}"
        )
    if evidence.warnings:
        lines.extend(["", "EVIDENCE WARNINGS"])
        lines.extend(f"- {warning}" for warning in evidence.warnings)
    if proof.repair_contract:
        contract = proof.repair_contract
        lines.extend(["", "REPAIR CONTRACT", "Must Change:"])
        lines.extend(f"- {item}" for item in contract.must_change)
        lines.append("Must Preserve:")
        lines.extend(f"- {item}" for item in contract.must_preserve)
        lines.append("Must Not Change:")
        lines.extend(f"- {item}" for item in contract.must_not_change)
        lines.append("Required Verification:")
        lines.extend(f"- {item}" for item in contract.required_verification)
        lines.append("Required Evidence:")
        lines.extend(f"- {item}" for item in contract.required_evidence)
    lines.extend(["", "EVIDENCE PROVENANCE"])
    for fact_id in sorted(evidence.fact_values):
        origins = "; ".join(evidence.sources.get(fact_id, ("unknown",)))
        lines.append(f"{fact_id} = {evidence.fact_values[fact_id]} <- {origins}")
    return "\n".join(lines)
