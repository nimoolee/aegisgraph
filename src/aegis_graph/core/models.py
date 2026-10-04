"""Minimal generic domain model for AegisGraph v0.1.

The core deliberately contains no trading- or platform-specific semantics.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aegis_graph.immutability import freeze_mapping, freeze_tuple


class Criticality(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceSource(str, Enum):
    EXPLICIT = "explicit"
    STATIC = "static"
    OBSERVED = "observed"
    REPLAY = "replay"
    AI_INFERRED = "ai_inferred"


class RelationshipType(str, Enum):
    SOURCE_FROM = "source_from"
    DERIVED_FROM = "derived_from"
    DEPENDS_ON = "depends_on"
    CONTROLS = "controls"
    READS = "reads"
    WRITES = "writes"
    DISPLAYS = "displays"
    VALIDATES = "validates"
    TRANSITIONS = "transitions"
    INDEPENDENT_OF = "independent_of"


class ChangeType(str, Enum):
    SOURCE_CHANGE = "source_change"
    RULE_CHANGE = "rule_change"
    NODE_CHANGE = "node_change"
    NODE_ADDED = "node_added"
    NODE_DEPRECATED = "node_deprecated"
    RELATIONSHIP_CHANGE = "relationship_change"
    INVARIANT_CHANGE = "invariant_change"
    TEMPORAL_CHANGE = "temporal_change"
    STATE_CHANGE = "state_change"
    CODE_CHANGE = "code_change"


@dataclass(frozen=True, slots=True)
class Metadata:
    version: str = "1"
    provenance: ConfidenceSource = ConfidenceSource.EXPLICIT
    confidence: float = 1.0
    criticality: Criticality = Criticality.MEDIUM
    valid_from: str | None = None
    valid_to: str | None = None
    commit_sha: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("metadata version must be a non-empty string")
        if not isinstance(self.provenance, ConfidenceSource):
            raise TypeError("metadata provenance must be ConfidenceSource")
        if not isinstance(self.criticality, Criticality):
            raise TypeError("metadata criticality must be Criticality")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise TypeError("metadata confidence must be a real number")
        if not math.isfinite(float(self.confidence)) or not 0 <= self.confidence <= 1:
            raise ValueError("metadata confidence must be finite and between 0 and 1")


@dataclass(frozen=True, slots=True)
class FactNode:
    id: str
    name: str
    description: str = ""
    kind: str = "fact"
    status: str = "active"
    metadata: Metadata = field(default_factory=Metadata)


@dataclass(frozen=True, slots=True)
class Relationship:
    id: str
    source: str
    target: str
    type: RelationshipType
    metadata: Metadata = field(default_factory=Metadata)


@dataclass(frozen=True, slots=True)
class Context:
    id: str
    kind: str
    attributes: Mapping[str, Any] = field(default_factory=dict)
    metadata: Metadata = field(default_factory=Metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", freeze_mapping(self.attributes))


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    expression: str | None = None
    applies_when: str | None = None
    context_ids: tuple[str, ...] = ()
    metadata: Metadata = field(default_factory=Metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", freeze_tuple(self.inputs))
        object.__setattr__(self, "outputs", freeze_tuple(self.outputs))
        object.__setattr__(self, "context_ids", freeze_tuple(self.context_ids))


@dataclass(frozen=True, slots=True)
class Invariant:
    id: str
    name: str
    facts: tuple[str, ...]
    expression: str | None = None
    applies_when: str | None = None
    context_ids: tuple[str, ...] = ()
    metadata: Metadata = field(default_factory=Metadata)

    def __post_init__(self) -> None:
        object.__setattr__(self, "facts", freeze_tuple(self.facts))
        object.__setattr__(self, "context_ids", freeze_tuple(self.context_ids))


@dataclass(frozen=True, slots=True)
class Change:
    id: str
    type: ChangeType
    summary: str
    changed_fact_ids: tuple[str, ...] = ()
    changed_rule_ids: tuple[str, ...] = ()
    changed_relationship_ids: tuple[str, ...] = ()
    changed_invariant_ids: tuple[str, ...] = ()
    changed_context_ids: tuple[str, ...] = ()
    commit_sha: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("change id must be a non-empty string")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("change summary must be a non-empty string")
        if not isinstance(self.type, ChangeType):
            raise TypeError("change type must be ChangeType")
        object.__setattr__(self, "changed_fact_ids", freeze_tuple(self.changed_fact_ids))
        object.__setattr__(self, "changed_rule_ids", freeze_tuple(self.changed_rule_ids))
        object.__setattr__(
            self,
            "changed_relationship_ids",
            freeze_tuple(self.changed_relationship_ids),
        )
        object.__setattr__(
            self,
            "changed_invariant_ids",
            freeze_tuple(self.changed_invariant_ids),
        )
        object.__setattr__(self, "changed_context_ids", freeze_tuple(self.changed_context_ids))
        for label, values in (
            ("fact", self.changed_fact_ids),
            ("rule", self.changed_rule_ids),
            ("relationship", self.changed_relationship_ids),
            ("invariant", self.changed_invariant_ids),
            ("context", self.changed_context_ids),
        ):
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f"changed {label} ids must be non-empty strings")
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))
