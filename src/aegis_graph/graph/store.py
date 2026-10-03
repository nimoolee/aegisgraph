"""In-memory semantic graph for AegisGraph v0.1.

The graph stores authored semantic truth. It is intentionally deterministic and
contains no product-specific business concepts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis_graph.core.models import Context, FactNode, Invariant, Relationship, Rule


class GraphIntegrityError(ValueError):
    """Raised when a graph object references missing or duplicate identities."""


@dataclass(slots=True)
class SoftwareGraph:
    """Small, deterministic graph store used by the v0.1 impact engine."""

    facts: dict[str, FactNode] = field(default_factory=dict)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    rules: dict[str, Rule] = field(default_factory=dict)
    invariants: dict[str, Invariant] = field(default_factory=dict)
    contexts: dict[str, Context] = field(default_factory=dict)

    def add_fact(self, fact: FactNode) -> None:
        self._ensure_new_id(fact.id)
        self.facts[fact.id] = fact

    def add_relationship(self, relationship: Relationship) -> None:
        self._ensure_new_id(relationship.id)
        self._require_facts(relationship.source, relationship.target)
        self.relationships[relationship.id] = relationship

    def add_rule(self, rule: Rule) -> None:
        self._ensure_new_id(rule.id)
        self._require_facts(*rule.inputs, *rule.outputs)
        self._require_contexts(*rule.context_ids)
        self.rules[rule.id] = rule

    def replace_rule(self, rule: Rule, *, expected_current_version: str) -> None:
        current = self.rules.get(rule.id)
        if current is None:
            raise GraphIntegrityError(f"unknown rule id: {rule.id}")
        if current.metadata.version != expected_current_version:
            raise GraphIntegrityError(
                f"rule version conflict for {rule.id}: expected {expected_current_version}, "
                f"found {current.metadata.version}"
            )
        self._require_facts(*rule.inputs, *rule.outputs)
        self._require_contexts(*rule.context_ids)
        self.rules[rule.id] = rule

    def add_invariant(self, invariant: Invariant) -> None:
        self._ensure_new_id(invariant.id)
        self._require_facts(*invariant.facts)
        self._require_contexts(*invariant.context_ids)
        self.invariants[invariant.id] = invariant

    def replace_invariant(self, invariant: Invariant, *, expected_current_version: str) -> None:
        current = self.invariants.get(invariant.id)
        if current is None:
            raise GraphIntegrityError(f"unknown invariant id: {invariant.id}")
        if current.metadata.version != expected_current_version:
            raise GraphIntegrityError(
                f"invariant version conflict for {invariant.id}: expected {expected_current_version}, "
                f"found {current.metadata.version}"
            )
        self._require_facts(*invariant.facts)
        self._require_contexts(*invariant.context_ids)
        self.invariants[invariant.id] = invariant

    def add_context(self, context: Context) -> None:
        self._ensure_new_id(context.id)
        self.contexts[context.id] = context

    def _ensure_new_id(self, object_id: str) -> None:
        all_ids = (
            self.facts
            | self.relationships
            | self.rules
            | self.invariants
            | self.contexts
        )
        if object_id in all_ids:
            raise GraphIntegrityError(f"duplicate semantic id: {object_id}")

    def _require_facts(self, *fact_ids: str) -> None:
        missing = sorted({fact_id for fact_id in fact_ids if fact_id not in self.facts})
        if missing:
            raise GraphIntegrityError(f"unknown fact ids: {', '.join(missing)}")

    def _require_contexts(self, *context_ids: str) -> None:
        missing = sorted(
            {context_id for context_id in context_ids if context_id not in self.contexts}
        )
        if missing:
            raise GraphIntegrityError(f"unknown context ids: {', '.join(missing)}")
