"""Models for semantics discovered from implementation evidence.

Discovered semantics are candidates, never product truth by themselves.  This is
intentionally separate from ``core.models`` where accepted semantic facts/rules
used by the verifier live.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from aegis_graph.immutability import freeze_mapping, freeze_tuple


class SemanticStatus(str, Enum):
    """Lifecycle of a semantic statement in the living software model."""

    DISCOVERED = "discovered"
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    CONFLICTED = "conflicted"
    UNDEFINED = "undefined"
    UNIMPLEMENTED = "unimplemented"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CodeAnchor:
    """Exact implementation provenance for one discovered statement."""

    path: str
    line: int
    column: int = 0
    function: str | None = None
    class_name: str | None = None
    context: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", freeze_tuple(self.context))


@dataclass(frozen=True, slots=True)
class CandidateConcept:
    """A code-level symbol that may represent a stable software/business fact."""

    id: str
    symbol: str
    status: SemanticStatus = SemanticStatus.DISCOVERED
    confidence: float = 0.5
    anchors: tuple[CodeAnchor, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchors", freeze_tuple(self.anchors))


@dataclass(frozen=True, slots=True)
class CandidateFormula:
    """A formula observed in implementation code, scoped to its code context."""

    id: str
    output_symbol: str
    input_symbols: tuple[str, ...]
    expression: str
    anchor: CodeAnchor
    status: SemanticStatus = SemanticStatus.CANDIDATE
    confidence: float = 0.7

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_symbols", freeze_tuple(self.input_symbols))


@dataclass(frozen=True, slots=True)
class CandidateRelationship:
    """One candidate semantic edge inferred from observed data flow."""

    id: str
    source_symbol: str
    target_symbol: str
    relationship_type: str
    anchor: CodeAnchor
    status: SemanticStatus = SemanticStatus.CANDIDATE
    confidence: float = 0.7


@dataclass(frozen=True, slots=True)
class CandidateFunction:
    """A discovered function signature used for interprocedural value flow."""

    id: str
    name: str
    parameters: tuple[str, ...]
    anchor: CodeAnchor

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", freeze_tuple(self.parameters))


@dataclass(frozen=True, slots=True)
class CandidateCall:
    """One observed call site with argument expressions and fact inputs."""

    id: str
    callee: str
    argument_expressions: tuple[str, ...]
    argument_symbols: tuple[tuple[str, ...], ...]
    anchor: CodeAnchor

    def __post_init__(self) -> None:
        object.__setattr__(self, "argument_expressions", freeze_tuple(self.argument_expressions))
        object.__setattr__(self, "argument_symbols", freeze_tuple(self.argument_symbols))


@dataclass(frozen=True, slots=True)
class DiscoveryReport:
    """Read-only discovery result for one target snapshot."""

    target_root: str
    language: str
    files_scanned: int
    concepts: tuple[CandidateConcept, ...]
    formulas: tuple[CandidateFormula, ...]
    relationships: tuple[CandidateRelationship, ...]
    functions: tuple[CandidateFunction, ...] = ()
    calls: tuple[CandidateCall, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "concepts", freeze_tuple(self.concepts))
        object.__setattr__(self, "formulas", freeze_tuple(self.formulas))
        object.__setattr__(self, "relationships", freeze_tuple(self.relationships))
        object.__setattr__(self, "functions", freeze_tuple(self.functions))
        object.__setattr__(self, "calls", freeze_tuple(self.calls))
        object.__setattr__(self, "warnings", freeze_tuple(self.warnings))
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))
