"""Product boundary policy for AegisGraph.

AegisGraph judges software changes; it does not author the target change it judges.
The target-system access contract is intentionally read-only, and verifier output is
implementation-neutral: Aegis may report structural risk but never prescribe target
architecture or implementation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductBoundary:
    """Capabilities AegisGraph is allowed to exercise against a target system."""

    target_access: str = "read_only"
    may_modify_target: bool = False
    may_generate_target_patch: bool = False
    may_emit_repair_contract: bool = True
    may_prescribe_target_architecture: bool = False
    may_prescribe_target_implementation: bool = False
    may_emit_structural_risk: bool = True
    may_emit_implementation_neutral_constraints: bool = True


READ_ONLY_TARGET_POLICY = ProductBoundary()
