"""Conservative conflict detection over unified candidate semantics."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from aegis_graph.semantics.models import (
    ConflictReport,
    SemanticConflict,
    UnificationReport,
    UnifiedFormula,
)


def _stable_id(prefix: str, *parts: object) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return f"{prefix}.{hashlib.sha1(raw.encode('utf-8'), usedforsecurity=False).hexdigest()[:16]}"


def _normalized_expression(expression: str) -> str:
    return " ".join(expression.split())


def _is_mutable_storage_definition(report: UnificationReport, concept_id: str) -> bool:
    concept = next(item for item in report.concepts if item.id == concept_id)
    return any(
        member.symbol.startswith('state["') or member.symbol.startswith("self.")
        for member in concept.members
    )


def detect_conflicts(report: UnificationReport) -> ConflictReport:
    """Find only same-concept/same-context incompatible formula candidates.

    Mutable state writes (persisted state keys and class-owned ``self`` attributes) are
    excluded in v1.0 because initialization/refresh/debit/credit transitions are not
    competing definitions. Alias/projection formulas are also excluded because they
    describe representation, not a business rule.
    """

    groups: dict[tuple[str, tuple[str, ...]], list[UnifiedFormula]] = defaultdict(list)
    for formula in report.formulas:
        if formula.is_alias_projection:
            continue
        if _is_mutable_storage_definition(report, formula.output_concept_id):
            continue
        if formula.output_concept_id in formula.input_concept_ids:
            continue
        groups[(formula.output_concept_id, formula.context)].append(formula)

    conflicts: list[SemanticConflict] = []
    for (concept_id, context), rows in sorted(groups.items(), key=lambda item: item[0]):
        by_expression: dict[str, list[UnifiedFormula]] = defaultdict(list)
        for row in rows:
            by_expression[_normalized_expression(row.expression)].append(row)
        if len(by_expression) <= 1:
            continue

        # A conflict requires the concept to have already been unified across distinct
        # implementation scopes by stronger evidence.  Sequential assignments inside
        # one function are implementation evolution, not two simultaneous definitions.
        scopes = {(row.anchor.path, row.anchor.function or "<module>") for row in rows}
        if len(scopes) <= 1:
            continue

        selected = [entries[0] for _, entries in sorted(by_expression.items())]
        output_symbol = ", ".join(sorted({row.output_symbol for row in selected}))
        expressions = tuple(row.expression for row in selected)
        anchors = tuple(row.anchor for row in selected)
        conflicts.append(
            SemanticConflict(
                id=_stable_id("semantic_conflict", concept_id, context, expressions),
                concept_id=concept_id,
                context=context,
                formula_ids=tuple(row.id for row in selected),
                expressions=expressions,
                anchors=anchors,
                reason=(
                    f"unified candidate concept ({output_symbol}) has incompatible "
                    "non-alias formulas in the same semantic context across independent scopes"
                ),
            )
        )

    return ConflictReport(
        target_root=report.target_root,
        conflicts=tuple(conflicts),
        metadata={
            "unified_concepts": str(len(report.concepts)),
            "candidate_conflicts": str(len(conflicts)),
        },
    )
