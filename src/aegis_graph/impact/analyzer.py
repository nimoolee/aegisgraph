"""Deterministic semantic change-impact analysis."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from aegis_graph.core.models import Change, Relationship, RelationshipType
from aegis_graph.graph.store import SoftwareGraph

MAX_PATH_DEPTH = 12
MAX_PATHS_PER_FACT = 8


# For dependency-shaped edges, the edge reads as:
#   source --depends_on/derived_from/...--> target
# therefore a change to target propagates back to source.
_REVERSE_PROPAGATION = {
    RelationshipType.SOURCE_FROM,
    RelationshipType.DERIVED_FROM,
    RelationshipType.DEPENDS_ON,
    RelationshipType.READS,
    RelationshipType.DISPLAYS,
    RelationshipType.VALIDATES,
}

# For causal/action edges, the edge reads as:
#   source --controls/writes/transitions--> target
# therefore a change to source propagates forward to target.
_FORWARD_PROPAGATION = {
    RelationshipType.CONTROLS,
    RelationshipType.WRITES,
    RelationshipType.TRANSITIONS,
}


@dataclass(frozen=True, slots=True)
class ImpactPath:
    """One explainable propagation path from a changed seed to an affected fact."""

    fact_ids: tuple[str, ...]
    via: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImpactResult:
    change_id: str
    seed_fact_ids: tuple[str, ...]
    affected_fact_ids: tuple[str, ...]
    affected_rule_ids: tuple[str, ...]
    affected_invariant_ids: tuple[str, ...]
    paths: dict[str, ImpactPath] = field(default_factory=dict)
    alternate_paths: dict[str, tuple[ImpactPath, ...]] = field(default_factory=dict)

    def paths_for(self, fact_id: str) -> tuple[ImpactPath, ...]:
        primary = self.paths.get(fact_id)
        if primary is None:
            return ()
        return (primary, *self.alternate_paths.get(fact_id, ()))


class ImpactAnalyzer:
    """Computes semantic blast radius without pretending to prove correctness."""

    def __init__(self, graph: SoftwareGraph) -> None:
        self.graph = graph

    def analyze(self, change: Change) -> ImpactResult:
        seeds = set(change.changed_fact_ids)

        # A rule change changes the semantics of its outputs.
        for rule_id in change.changed_rule_ids:
            rule = self.graph.rules.get(rule_id)
            if rule is not None:
                seeds.update(rule.outputs)

        # Changing an edge can affect both ends because the semantic connection itself
        # has changed; subsequent propagation still respects the edge-type policy.
        for relationship_id in change.changed_relationship_ids:
            relationship = self.graph.relationships.get(relationship_id)
            if relationship is not None:
                seeds.add(relationship.source)
                seeds.add(relationship.target)

        # A context/temporal change activates or deactivates rules. Their outputs are
        # semantic seeds because behaviour at those outputs may have changed.
        changed_contexts = set(change.changed_context_ids)
        if changed_contexts:
            for rule in self.graph.rules.values():
                if changed_contexts.intersection(rule.context_ids):
                    seeds.update(rule.outputs)

        self._validate_seed_facts(seeds)
        paths_by_fact = self._propagate(seeds)
        affected_facts = set(paths_by_fact)

        affected_rules = set(change.changed_rule_ids)
        for rule in self.graph.rules.values():
            if affected_facts.intersection(rule.inputs) or affected_facts.intersection(
                rule.outputs
            ):
                affected_rules.add(rule.id)

        affected_invariants = set(change.changed_invariant_ids)
        for invariant in self.graph.invariants.values():
            if affected_facts.intersection(invariant.facts):
                affected_invariants.add(invariant.id)
            elif changed_contexts.intersection(invariant.context_ids):
                affected_invariants.add(invariant.id)

        return ImpactResult(
            change_id=change.id,
            seed_fact_ids=tuple(sorted(seeds)),
            affected_fact_ids=tuple(sorted(affected_facts)),
            affected_rule_ids=tuple(sorted(affected_rules)),
            affected_invariant_ids=tuple(sorted(affected_invariants)),
            paths={key: paths_by_fact[key][0] for key in sorted(paths_by_fact)},
            alternate_paths={
                key: tuple(paths_by_fact[key][1:])
                for key in sorted(paths_by_fact)
                if len(paths_by_fact[key]) > 1
            },
        )

    def _validate_seed_facts(self, seeds: set[str]) -> None:
        missing = sorted(seed for seed in seeds if seed not in self.graph.facts)
        if missing:
            raise ValueError(f"change references unknown fact ids: {', '.join(missing)}")

    def _propagate(self, seeds: set[str]) -> dict[str, list[ImpactPath]]:
        paths: dict[str, list[ImpactPath]] = {
            seed: [ImpactPath(fact_ids=(seed,))] for seed in sorted(seeds)
        }
        queue: deque[ImpactPath] = deque(paths[seed][0] for seed in sorted(seeds))

        while queue:
            current_path = queue.popleft()
            changed = current_path.fact_ids[-1]
            if len(current_path.fact_ids) >= MAX_PATH_DEPTH:
                continue

            candidates = self._semantic_neighbors(changed)
            for rule in sorted(self.graph.rules.values(), key=lambda item: item.id):
                if changed in rule.inputs:
                    for output in sorted(rule.outputs):
                        candidates.append((output, f"rule:{rule.id}"))

            for next_fact, edge_label in candidates:
                # Only simple paths: never loop through a fact already on this path.
                if next_fact in current_path.fact_ids:
                    continue
                candidate = ImpactPath(
                    fact_ids=(*current_path.fact_ids, next_fact),
                    via=(*current_path.via, edge_label),
                )
                existing = paths.setdefault(next_fact, [])
                if candidate in existing or len(existing) >= MAX_PATHS_PER_FACT:
                    continue
                existing.append(candidate)
                queue.append(candidate)

        return paths

    def _semantic_neighbors(self, changed: str) -> list[tuple[str, str]]:
        neighbors: list[tuple[str, str]] = []
        for edge in sorted(self.graph.relationships.values(), key=lambda item: item.id):
            next_fact = self._propagation_target(changed, edge)
            if next_fact is not None:
                neighbors.append((next_fact, f"edge:{edge.id}:{edge.type.value}"))
        return neighbors

    @staticmethod
    def _propagation_target(changed: str, edge: Relationship) -> str | None:
        if edge.type in _REVERSE_PROPAGATION and changed == edge.target:
            return edge.source
        if edge.type in _FORWARD_PROPAGATION and changed == edge.source:
            return edge.target
        return None
