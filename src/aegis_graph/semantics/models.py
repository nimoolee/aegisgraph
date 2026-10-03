"""Models for turning code-level discoveries into candidate semantic concepts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from aegis_graph.discovery.models import CodeAnchor, SemanticStatus

if TYPE_CHECKING:
    from aegis_graph.impact.analyzer import ImpactResult


@dataclass(frozen=True, slots=True)
class SemanticMember:
    """One scoped implementation symbol participating in a unified concept."""

    key: str
    symbol: str
    anchor: CodeAnchor
    scope: str


@dataclass(frozen=True, slots=True)
class UnifiedConcept:
    """A conservative cluster of implementation symbols believed to mean one thing."""

    id: str
    display_name: str
    members: tuple[SemanticMember, ...]
    confidence: float
    status: SemanticStatus = SemanticStatus.CANDIDATE
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UnifiedFormula:
    """A discovered formula rewritten in terms of candidate semantic concepts."""

    id: str
    output_concept_id: str
    output_symbol: str
    input_symbols: tuple[str, ...]
    input_concept_ids: tuple[str, ...]
    expression: str
    context: tuple[str, ...]
    anchor: CodeAnchor
    source_formula_id: str
    is_alias_projection: bool = False
    confidence: float = 0.7


@dataclass(frozen=True, slots=True)
class UnifiedRelationship:
    """A candidate semantic edge after symbol-level aliases have been collapsed."""

    id: str
    source_concept_id: str
    target_concept_id: str
    relationship_type: str
    context: tuple[str, ...]
    anchors: tuple[CodeAnchor, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class UnificationReport:
    """Candidate software-world model produced without an authored Constitution."""

    target_root: str
    concepts: tuple[UnifiedConcept, ...]
    formulas: tuple[UnifiedFormula, ...]
    relationships: tuple[UnifiedRelationship, ...]
    symbol_to_concept: dict[str, str]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SemanticConflict:
    """Two or more incompatible candidate definitions in the same semantic context."""

    id: str
    concept_id: str
    context: tuple[str, ...]
    formula_ids: tuple[str, ...]
    expressions: tuple[str, ...]
    anchors: tuple[CodeAnchor, ...]
    reason: str
    status: SemanticStatus = SemanticStatus.CONFLICTED


@dataclass(frozen=True, slots=True)
class ConflictReport:
    target_root: str
    conflicts: tuple[SemanticConflict, ...]
    metadata: dict[str, str] = field(default_factory=dict)


class ManagedRuleKind(str, Enum):
    RULE = "rule"
    INVARIANT = "invariant"


class RuleChangeVerdict(str, Enum):
    APPROVAL_REQUIRED = "approval_required"
    ACCEPTED = "accepted"
    NO_CHANGE = "no_change"


@dataclass(frozen=True, slots=True)
class SemanticRuleSpec:
    """Product-generic semantic rule/invariant content, independent of lifecycle."""

    semantic_id: str
    kind: ManagedRuleKind
    name: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()
    expression: str | None = None
    applies_when: str | None = None
    context_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticRuleVersion:
    """Immutable proposed semantic content. Acceptance is recorded separately."""

    semantic_id: str
    version: int
    spec: SemanticRuleSpec
    proposed_by: str
    evidence_ids: tuple[str, ...] = ()
    commit_sha: str | None = None

    @property
    def version_id(self) -> str:
        return f"{self.semantic_id}@v{self.version}"


@dataclass(frozen=True, slots=True)
class RuleApproval:
    """Explicit human/product approval for one exact immutable rule version."""

    approval_id: str
    semantic_id: str
    version: int
    approved_by: str
    reason: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticRuleDiff:
    semantic_id: str
    from_version: int | None
    to_version: int
    changed_fields: tuple[str, ...]

    @property
    def has_semantic_change(self) -> bool:
        return bool(self.changed_fields)


@dataclass(frozen=True, slots=True)
class RuleChangeProof:
    """Proof gate for changing accepted semantics before target code is changed."""

    semantic_id: str
    candidate_version: int
    previous_accepted_version: int | None
    diff: SemanticRuleDiff
    impact: ImpactResult
    required_verification_ids: tuple[str, ...]
    verdict: RuleChangeVerdict
    reasons: tuple[str, ...]
    approval: RuleApproval | None = None
