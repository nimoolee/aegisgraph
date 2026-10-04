"""In-memory semantic graph for AegisGraph v0.1.

The graph stores authored semantic truth. It is intentionally deterministic and
contains no product-specific business concepts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from aegis_graph.core.models import (
    Context,
    FactNode,
    Invariant,
    Relationship,
    RelationshipType,
    Rule,
)


class GraphIntegrityError(ValueError):
    """Raised when a graph object references missing or duplicate identities."""


@dataclass(slots=True)
class SoftwareGraph:
    """Small, deterministic graph store used by the v0.1 impact engine."""

    _facts: dict[str, FactNode] = field(default_factory=dict, init=False, repr=False)
    _relationships: dict[str, Relationship] = field(default_factory=dict, init=False, repr=False)
    _rules: dict[str, Rule] = field(default_factory=dict, init=False, repr=False)
    _invariants: dict[str, Invariant] = field(default_factory=dict, init=False, repr=False)
    _contexts: dict[str, Context] = field(default_factory=dict, init=False, repr=False)

    @property
    def facts(self) -> Mapping[str, FactNode]:
        return MappingProxyType(self._facts)

    @property
    def relationships(self) -> Mapping[str, Relationship]:
        return MappingProxyType(self._relationships)

    @property
    def rules(self) -> Mapping[str, Rule]:
        return MappingProxyType(self._rules)

    @property
    def invariants(self) -> Mapping[str, Invariant]:
        return MappingProxyType(self._invariants)

    @property
    def contexts(self) -> Mapping[str, Context]:
        return MappingProxyType(self._contexts)

    def add_fact(self, fact: FactNode) -> None:
        self._validate_identity(fact.id, "fact")
        self._validate_nonempty(fact.name, "fact name")
        self._ensure_new_id(fact.id)
        self._facts[fact.id] = fact

    def add_relationship(self, relationship: Relationship) -> None:
        self._validate_identity(relationship.id, "relationship")
        if not isinstance(relationship.type, RelationshipType):
            raise GraphIntegrityError("relationship type must be RelationshipType")
        self._ensure_new_id(relationship.id)
        self._require_facts(relationship.source, relationship.target)
        self._relationships[relationship.id] = relationship

    def add_rule(self, rule: Rule) -> None:
        self._validate_rule(rule)
        self._ensure_new_id(rule.id)
        self._require_facts(*rule.inputs, *rule.outputs)
        self._require_contexts(*rule.context_ids)
        self._rules[rule.id] = rule

    def replace_rule(self, rule: Rule, *, expected_current_version: str) -> None:
        self._validate_rule(rule)
        current = self._rules.get(rule.id)
        if current is None:
            raise GraphIntegrityError(f"unknown rule id: {rule.id}")
        if current.metadata.version != expected_current_version:
            raise GraphIntegrityError(
                f"rule version conflict for {rule.id}: expected {expected_current_version}, "
                f"found {current.metadata.version}"
            )
        self._require_facts(*rule.inputs, *rule.outputs)
        self._require_contexts(*rule.context_ids)
        self._rules[rule.id] = rule

    def add_invariant(self, invariant: Invariant) -> None:
        self._validate_invariant(invariant)
        self._ensure_new_id(invariant.id)
        self._require_facts(*invariant.facts)
        self._require_contexts(*invariant.context_ids)
        self._invariants[invariant.id] = invariant

    def replace_invariant(self, invariant: Invariant, *, expected_current_version: str) -> None:
        self._validate_invariant(invariant)
        current = self._invariants.get(invariant.id)
        if current is None:
            raise GraphIntegrityError(f"unknown invariant id: {invariant.id}")
        if current.metadata.version != expected_current_version:
            raise GraphIntegrityError(
                f"invariant version conflict for {invariant.id}: expected {expected_current_version}, "
                f"found {current.metadata.version}"
            )
        self._require_facts(*invariant.facts)
        self._require_contexts(*invariant.context_ids)
        self._invariants[invariant.id] = invariant

    def add_context(self, context: Context) -> None:
        self._validate_identity(context.id, "context")
        self._validate_nonempty(context.kind, "context kind")
        self._ensure_new_id(context.id)
        self._contexts[context.id] = context

    @staticmethod
    def _validate_nonempty(value: str, label: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise GraphIntegrityError(f"{label} must be a non-empty string")

    def _validate_identity(self, object_id: str, kind: str) -> None:
        self._validate_nonempty(object_id, f"{kind} id")

    def _validate_rule(self, rule: Rule) -> None:
        self._validate_identity(rule.id, "rule")
        self._validate_nonempty(rule.name, "rule name")
        if not rule.outputs:
            raise GraphIntegrityError("rule requires at least one output fact")

    def _validate_invariant(self, invariant: Invariant) -> None:
        self._validate_identity(invariant.id, "invariant")
        self._validate_nonempty(invariant.name, "invariant name")
        if not invariant.facts:
            raise GraphIntegrityError("invariant requires at least one fact")

    def _ensure_new_id(self, object_id: str) -> None:
        all_ids = (
            self._facts
            | self._relationships
            | self._rules
            | self._invariants
            | self._contexts
        )
        if object_id in all_ids:
            raise GraphIntegrityError(f"duplicate semantic id: {object_id}")

    def _require_facts(self, *fact_ids: str) -> None:
        for fact_id in fact_ids:
            self._validate_nonempty(fact_id, "fact reference")
        missing = sorted({fact_id for fact_id in fact_ids if fact_id not in self._facts})
        if missing:
            raise GraphIntegrityError(f"unknown fact ids: {', '.join(missing)}")

    def _require_contexts(self, *context_ids: str) -> None:
        for context_id in context_ids:
            self._validate_nonempty(context_id, "context reference")
        missing = sorted(
            {context_id for context_id in context_ids if context_id not in self._contexts}
        )
        if missing:
            raise GraphIntegrityError(f"unknown context ids: {', '.join(missing)}")
