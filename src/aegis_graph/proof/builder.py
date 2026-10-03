"""Build structured Change Proof envelopes from deterministic impact analysis."""

from __future__ import annotations

from collections.abc import Mapping

from aegis_graph.core.models import Change
from aegis_graph.impact.analyzer import ImpactResult
from aegis_graph.invariants.executor import InvariantCheck, InvariantStatus
from aegis_graph.proof.models import ChangeProof, ProofVerdict, RepairContract, RepairDirective


def _dedupe(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def build_repair_contract(
    change: Change,
    failed_invariant_ids: tuple[str, ...],
    directives: Mapping[str, RepairDirective] | None = None,
) -> RepairContract | None:
    """Aggregate semantic repair requirements without generating target code."""

    if not failed_invariant_ids:
        return None
    registry = directives or {}
    must_change: list[str] = []
    must_preserve: list[str] = []
    must_not_change: list[str] = [
        "Do not disable, weaken, or delete a failed invariant merely to obtain PASS.",
        "Do not rewrite or suppress evidence to manufacture a successful proof.",
        "Do not prescribe target architecture, refactors, modules, classes, functions, or implementation steps; state only semantic constraints and verification obligations.",
    ]
    required_verification: list[str] = []
    required_evidence: list[str] = []

    for invariant_id in failed_invariant_ids:
        directive = registry.get(invariant_id)
        if directive is None:
            must_change.append(f"Resolve the semantic violation of {invariant_id}.")
            required_verification.append(f"Re-run invariant {invariant_id} after the Developer AI change.")
            continue
        must_change.extend(directive.must_change)
        must_preserve.extend(directive.must_preserve)
        must_not_change.extend(directive.must_not_change)
        required_verification.extend(directive.required_verification)
        required_evidence.extend(directive.required_evidence)

    return RepairContract(
        change_id=change.id,
        violated_invariant_ids=failed_invariant_ids,
        must_change=_dedupe(must_change),
        must_preserve=_dedupe(must_preserve),
        must_not_change=_dedupe(must_not_change),
        required_verification=_dedupe(required_verification),
        required_evidence=_dedupe(required_evidence),
    )


def build_impact_proof(
    change: Change,
    impact: ImpactResult,
    invariant_checks: tuple[InvariantCheck, ...] = (),
    repair_directives: Mapping[str, RepairDirective] | None = None,
) -> ChangeProof:
    """Create a proof envelope from impact and executable verification evidence."""

    statuses = {check.status for check in invariant_checks}
    if InvariantStatus.FAIL in statuses:
        verdict = ProofVerdict.FAIL
        reasons = ("one or more affected invariants failed",)
    elif InvariantStatus.UNKNOWN in statuses:
        verdict = ProofVerdict.UNKNOWN
        reasons = ("one or more affected invariants lack conclusive evidence",)
    elif impact.affected_invariant_ids and invariant_checks:
        verdict = ProofVerdict.PASS
        reasons = ("all affected executable invariants passed",)
    else:
        verdict = ProofVerdict.UNKNOWN
        reasons = (
            "semantic impact analysis completed",
            "no conclusive invariant evidence is available yet",
        )

    failed_invariant_ids = tuple(
        sorted(check.invariant_id for check in invariant_checks if check.status is InvariantStatus.FAIL)
    )
    repair_contract = build_repair_contract(change, failed_invariant_ids, repair_directives)

    return ChangeProof(
        id=f"proof:{change.id}",
        change_id=change.id,
        commit_sha=change.commit_sha,
        impact=impact,
        invariant_checks=invariant_checks,
        verdict=verdict,
        reasons=reasons,
        repair_contract=repair_contract,
    )
