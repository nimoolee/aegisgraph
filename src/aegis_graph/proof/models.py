"""Change Proof result models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aegis_graph.immutability import freeze_tuple
from aegis_graph.impact.analyzer import ImpactResult
from aegis_graph.invariants.executor import InvariantCheck


class ProofVerdict(str, Enum):
    # This is a proof verdict string, never credential material.
    PASS = "pass"  # nosec B105
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "must_change", freeze_tuple(self.must_change))
        object.__setattr__(self, "must_preserve", freeze_tuple(self.must_preserve))
        object.__setattr__(self, "must_not_change", freeze_tuple(self.must_not_change))
        object.__setattr__(
            self,
            "required_verification",
            freeze_tuple(self.required_verification),
        )
        object.__setattr__(self, "required_evidence", freeze_tuple(self.required_evidence))


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

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "violated_invariant_ids",
            freeze_tuple(self.violated_invariant_ids),
        )
        object.__setattr__(self, "must_change", freeze_tuple(self.must_change))
        object.__setattr__(self, "must_preserve", freeze_tuple(self.must_preserve))
        object.__setattr__(self, "must_not_change", freeze_tuple(self.must_not_change))
        object.__setattr__(
            self,
            "required_verification",
            freeze_tuple(self.required_verification),
        )
        object.__setattr__(self, "required_evidence", freeze_tuple(self.required_evidence))


@dataclass(frozen=True, slots=True)
class ChangeProof:
    """A structured proof envelope.

    v1.0 carries semantic impact plus executable invariant evidence. If evidence is
    incomplete, callers must preserve UNKNOWN rather than manufacture PASS.
    """

    id: str
    change_id: str
    commit_sha: str | None
    impact: ImpactResult
    invariant_checks: tuple[InvariantCheck, ...]
    verdict: ProofVerdict
    reasons: tuple[str, ...]
    repair_contract: RepairContract | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "invariant_checks", freeze_tuple(self.invariant_checks))
        object.__setattr__(self, "reasons", freeze_tuple(self.reasons))
