"""Human-readable candidate knowledge-graph rendering."""

from __future__ import annotations

from aegis_graph.semantics.models import ConflictReport, UnificationReport


def render_unification(
    report: UnificationReport,
    *,
    contains: str | None = None,
    limit: int = 40,
) -> str:
    needle = contains.lower() if contains else None
    concepts = []
    for concept in report.concepts:
        haystack = " ".join(
            [concept.display_name, *[member.symbol for member in concept.members]]
        ).lower()
        if needle is None or needle in haystack:
            concepts.append(concept)
    concepts.sort(key=lambda item: (-len(item.members), -item.confidence, item.display_name))

    formulas_by_output: dict[str, list] = {}
    for formula in report.formulas:
        formulas_by_output.setdefault(formula.output_concept_id, []).append(formula)

    lines = [
        "AEGISGRAPH SEMANTIC UNIFICATION",
        f"Target: {report.target_root}",
        "Boundary: READ_ONLY_TARGET",
        f"Discovery Concepts: {report.metadata.get('discovery_concepts', '?')}",
        f"Unified Candidate Concepts: {len(report.concepts)}",
        f"Unified Relationships: {len(report.relationships)}",
        "",
        "CANDIDATE KNOWLEDGE GRAPH",
    ]
    for concept in concepts[: max(0, limit)]:
        lines.append(
            f"\n[{concept.confidence:.2f}] {concept.id}  display={concept.display_name}"
        )
        lines.append("  members:")
        for member in concept.members[:12]:
            lines.append(
                f"    - {member.symbol} <- {member.anchor.path}:{member.anchor.line} "
                f"function={member.anchor.function or '<module>'}"
            )
        rows = [row for row in formulas_by_output.get(concept.id, ()) if not row.is_alias_projection]
        if rows:
            lines.append("  definition candidates:")
            for row in rows[:8]:
                context = " AND ".join(row.context) or "<unconditional>"
                lines.append(
                    f"    - {row.expression} @ {row.anchor.path}:{row.anchor.line} context={context}"
                )
    if not concepts:
        lines.append("<no matching unified concepts>")
    if report.warnings:
        lines.extend(["", f"Warnings: {len(report.warnings)} scope ambiguities retained conservatively"])
    return "\n".join(lines)


def render_conflicts(report: ConflictReport, unification: UnificationReport) -> str:
    concepts = {item.id: item for item in unification.concepts}
    lines = [
        "AEGISGRAPH SEMANTIC CONFLICT REPORT",
        f"Target: {report.target_root}",
        "Boundary: READ_ONLY_TARGET",
        f"Conflicts: {len(report.conflicts)}",
    ]
    for conflict in report.conflicts:
        concept = concepts[conflict.concept_id]
        context = " AND ".join(conflict.context) or "<unconditional>"
        lines.append(f"\nCONFLICT {conflict.id}")
        lines.append(f"Concept: {concept.display_name} ({concept.id})")
        lines.append(f"Context: {context}")
        for expression, anchor in zip(conflict.expressions, conflict.anchors):
            lines.append(
                f"  - {expression} <- {anchor.path}:{anchor.line} "
                f"function={anchor.function or '<module>'}"
            )
        lines.append(f"Reason: {conflict.reason}")
    return "\n".join(lines)
