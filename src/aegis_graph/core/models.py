"""Minimal generic domain model for AegisGraph v0.1.

The core deliberately contains no trading- or platform-specific semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    attributes: dict[str, Any] = field(default_factory=dict)
    metadata: Metadata = field(default_factory=Metadata)


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


@dataclass(frozen=True, slots=True)
class Invariant:
    id: str
    name: str
    facts: tuple[str, ...]
    expression: str | None = None
    applies_when: str | None = None
    context_ids: tuple[str, ...] = ()
    metadata: Metadata = field(default_factory=Metadata)


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
    metadata: dict[str, Any] = field(default_factory=dict)
