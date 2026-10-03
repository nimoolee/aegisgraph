"""Change Proof result models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aegis_graph.impact.analyzer import ImpactResult
from aegis_graph.invariants.executor import InvariantCheck


class ProofVerdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RepairDirective:
    """Domain-authored semantic constraints handed to a Developer AI after FAIL."""

    invariant_id: str
    must_change: tuple[str, ...] = ()
    must_preserve: tuple[str, ...] = ()
    must_not_change: tuple[str, ...] = ()
    required_verification: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepairContract:
    """Implementation-neutral verification constraints; never architecture advice or a code patch."""

    # Historical class name retained for API compatibility. Semantically this is a
    # Verification Contract: outcomes/constraints/evidence, never a repair design.

    change_id: str
    violated_invariant_ids: tuple[str, ...]
    must_change: tuple[str, ...]
    must_preserve: tuple[str, ...]
    must_not_change: tuple[str, ...]
    required_verification: tuple[str, ...]
    required_evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChangeProof:
    """A structured proof envelope.

    v0.1 M1 only proves impact selection. Until verification evidence is executed,
    the verdict must remain UNKNOWN by design.
    """

    id: str
    change_id: str
    commit_sha: str | None
    impact: ImpactResult
    invariant_checks: tuple[InvariantCheck, ...]
    verdict: ProofVerdict
    reasons: tuple[str, ...]
    repair_contract: RepairContract | None = None
