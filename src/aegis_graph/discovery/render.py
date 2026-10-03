"""Human-readable rendering for early semantic discovery experiments."""

from __future__ import annotations

from aegis_graph.discovery.models import DiscoveryReport


def render_discovery(
    report: DiscoveryReport,
    *,
    contains: str | None = None,
    limit: int = 80,
) -> str:
    needle = contains.lower() if contains else None
    formulas = [
        item
        for item in report.formulas
        if needle is None
        or needle in item.output_symbol.lower()
        or needle in item.expression.lower()
        or any(needle in symbol.lower() for symbol in item.input_symbols)
    ]
    formulas.sort(key=lambda item: (-item.confidence, item.anchor.path, item.anchor.line))
    lines = [
        "AEGISGRAPH SEMANTIC DISCOVERY",
        f"Target: {report.target_root}",
        "Boundary: READ_ONLY_TARGET",
        f"Language: {report.language}",
        f"Source Selection: {report.metadata.get('source_selection', 'unknown')}",
        f"Files Scanned: {report.files_scanned}",
        f"Candidate Concepts: {len(report.concepts)}",
        f"Candidate Formulas: {len(report.formulas)}",
        f"Candidate Relationships: {len(report.relationships)}",
        "",
        "CANDIDATE FORMULAS",
    ]
    for formula in formulas[: max(0, limit)]:
        context = " AND ".join(formula.anchor.context) or "<unconditional>"
        lines.append(
            f"[{formula.confidence:.2f}] {formula.output_symbol} = {formula.expression}"
        )
        lines.append(
            f"  <- {formula.anchor.path}:{formula.anchor.line} "
            f"function={formula.anchor.function or '<module>'} context={context}"
        )
        lines.append(f"  inputs: {', '.join(formula.input_symbols)}")
    if not formulas:
        lines.append("<no matching candidate formulas>")
    if report.warnings:
        lines.extend(["", "WARNINGS", *[f"- {item}" for item in report.warnings]])
    return "\n".join(lines)
