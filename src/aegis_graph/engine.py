"""Public orchestration API for the first AegisGraph vertical slice."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aegis_graph.core.models import Change
from aegis_graph.graph.store import SoftwareGraph
from aegis_graph.impact.analyzer import ImpactAnalyzer
from aegis_graph.invariants.executor import InvariantExecutor, InvariantValidator
from aegis_graph.proof.builder import build_impact_proof
from aegis_graph.policy import READ_ONLY_TARGET_POLICY, ProductBoundary
from aegis_graph.proof.models import ChangeProof, RepairDirective


class AegisEngine:
    """Analyze one semantic Change and return an explainable Change Proof."""

    def __init__(self, graph: SoftwareGraph) -> None:
        self.graph = graph
        self.impact = ImpactAnalyzer(graph)
        self.invariants = InvariantExecutor(graph)
        self.boundary: ProductBoundary = READ_ONLY_TARGET_POLICY
        self._repair_directives: dict[str, RepairDirective] = {}

    def register_invariant_validator(
        self, invariant_id: str, validator: InvariantValidator
    ) -> None:
        self.invariants.register(invariant_id, validator)

    def register_repair_directive(self, directive: RepairDirective) -> None:
        if directive.invariant_id not in self.graph.invariants:
            raise ValueError(f"unknown invariant id: {directive.invariant_id}")
        self._repair_directives[directive.invariant_id] = directive

    def analyze(
        self,
        change: Change,
        *,
        fact_values: Mapping[str, Any] | None = None,
    ) -> ChangeProof:
        impact = self.impact.analyze(change)
        checks = self.invariants.verify(impact.affected_invariant_ids, fact_values)
        return build_impact_proof(change, impact, checks, self._repair_directives)
