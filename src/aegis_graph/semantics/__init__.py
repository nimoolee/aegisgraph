"""Semantic unification and conflict detection for discovered implementation facts."""

from aegis_graph.semantics.change_management import (
    SemanticChangeError,
    SemanticChangeManager,
)
from aegis_graph.semantics.conflicts import detect_conflicts
from aegis_graph.semantics.models import (
    ConflictReport,
    ManagedRuleKind,
    RuleApproval,
    RuleChangeProof,
    RuleChangeVerdict,
    SemanticConflict,
    SemanticMember,
    SemanticRuleDiff,
    SemanticRuleSpec,
    SemanticRuleVersion,
    UnificationReport,
    UnifiedConcept,
    UnifiedFormula,
    UnifiedRelationship,
)
from aegis_graph.semantics.unify import unify_discovery

__all__ = [
    "ConflictReport",
    "ManagedRuleKind",
    "RuleApproval",
    "RuleChangeProof",
    "RuleChangeVerdict",
    "SemanticChangeError",
    "SemanticChangeManager",
    "SemanticConflict",
    "SemanticMember",
    "SemanticRuleDiff",
    "SemanticRuleSpec",
    "SemanticRuleVersion",
    "UnificationReport",
    "UnifiedConcept",
    "UnifiedFormula",
    "UnifiedRelationship",
    "detect_conflicts",
    "unify_discovery",
]
