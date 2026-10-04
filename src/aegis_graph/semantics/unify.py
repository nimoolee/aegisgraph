"""Conservative semantic unification for implementation-discovered symbols.

The unifier intentionally prefers false negatives over false merges.  Local symbols
remain scoped by file/function unless there is direct value-flow evidence connecting
them to a stable storage/projection symbol.  No trading vocabulary is embedded here.
"""

from __future__ import annotations

import ast
import hashlib
import re
from collections import defaultdict

from aegis_graph.discovery.models import (
    CandidateFormula,
    CandidateFunction,
    CodeAnchor,
    DiscoveryReport,
)
from aegis_graph.semantics.models import (
    SemanticMember,
    UnificationReport,
    UnifiedConcept,
    UnifiedFormula,
    UnifiedRelationship,
)

_GENERIC_TOKENS = {
    "account",
    "balance",
    "current",
    "data",
    "raw",
    "result",
    "return",
    "state",
    "total",
    "value",
}

_EXACT_WRAPPERS = {
    "Decimal",
    "float",
    "int",
    "str",
}

_NORMALIZING_WRAPPERS = {
    "amount",
    "dec",
    "money",
    "_nonnegative_decimal",
}


def _stable_id(prefix: str, *parts: object) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return f"{prefix}.{hashlib.sha1(raw.encode('utf-8'), usedforsecurity=False).hexdigest()[:16]}"


def _scope(anchor: CodeAnchor) -> str:
    owner = anchor.class_name or "<module>"
    return f"{anchor.path}::{owner}::{anchor.function or '<module>'}"


def _is_stable_storage(symbol: str) -> bool:
    return symbol.startswith(('state["', "self."))


def _member_key(symbol: str, anchor: CodeAnchor) -> str:
    # Persisted keyed state is stable across functions in one target process. Object
    # attributes are only stable within their owning class: ``A.config`` and
    # ``B.config`` are different concepts even though both appear in source as
    # ``self.config``. Bare locals/returns remain function-scoped until stronger
    # cross-scope evidence exists.
    if symbol.startswith('state["'):
        return f"storage::{symbol}"
    if symbol.startswith("self."):
        owner = anchor.class_name or "<unknown-class>"
        return f"object::{anchor.path}::{owner}::{symbol}"
    return f"{_scope(anchor)}::{symbol}"


def _tokens(symbol: str) -> set[str]:
    quoted = re.findall(r'["\']([^"\']+)["\']', symbol)
    text = "_".join(quoted) if quoted else symbol
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    tokens = {part.lower() for part in re.split(r"[^A-Za-z0-9]+", text) if part}
    return tokens - _GENERIC_TOKENS


def _lexically_related(left: str, right: str) -> bool:
    a = _tokens(left)
    b = _tokens(right)
    return bool(a and b and a.intersection(b))


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _alias_kind(formula: CandidateFormula) -> tuple[str | None, float]:
    """Classify a one-input formula as an alias/projection when evidence is strong."""

    if len(formula.input_symbols) != 1:
        return None, 0.0
    input_symbol = formula.input_symbols[0]
    output_symbol = formula.output_symbol
    try:
        expr = ast.parse(formula.expression, mode="eval").body
    except SyntaxError:
        return None, 0.0

    if isinstance(expr, (ast.Name, ast.Attribute, ast.Subscript)):
        return "direct", 0.99

    # Direct representation conversions preserve the underlying semantic quantity.
    current = expr
    wrappers: list[str] = []
    while isinstance(current, ast.Call):
        name = _call_name(current.func)
        if name in _EXACT_WRAPPERS and len(current.args) == 1:
            wrappers.append(name or "")
            current = current.args[0]
            continue
        break
    if wrappers and isinstance(current, (ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
        return "representation", 0.96

    if isinstance(expr, ast.Call):
        name = _call_name(expr.func)
        if (
            isinstance(expr.func, ast.Attribute)
            and expr.func.attr == "get"
            and expr.args
            and isinstance(expr.args[0], ast.Constant)
            and isinstance(expr.args[0].value, str)
        ):
            return "keyed_storage_read", 0.97
        if name in _NORMALIZING_WRAPPERS:
            # A named normalization of exactly one discovered input still represents
            # that input quantity even when the local variable has an opaque name.
            return "normalized_projection", 0.84
        if name == "max" and _lexically_related(output_symbol, input_symbol):
            # A non-negative clamp often preserves concept identity but changes its
            # admissible domain, so keep confidence below direct projections.
            return "bounded_projection", 0.80

    # API/returned-field projection is a strong semantic naming signal when it is
    # merely wrapping one implementation value.
    if output_symbol.startswith('return["') and _lexically_related(output_symbol, input_symbol):
        return "return_projection", 0.90

    return None, 0.0


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: str) -> str:
        self.add(item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            parent = self.parent[item]
            self.parent[item] = root
            item = parent
        return root

    def union(self, left: str, right: str) -> None:
        a = self.find(left)
        b = self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def _display_name(members: list[SemanticMember]) -> str:
    # Prefer stable storage keys, then explicit return keys, then the most descriptive
    # lexical symbol.  This is only a display hint, not an accepted business name.
    storage = [m.symbol for m in members if _is_stable_storage(m.symbol)]
    if storage:
        return min(storage, key=lambda value: (len(value), value))
    returned = [m.symbol for m in members if m.symbol.startswith('return["')]
    if returned:
        return min(returned, key=lambda value: (len(value), value))
    return min(
        (m.symbol for m in members),
        key=lambda value: (-len(_tokens(value)), len(value), value),
    )


def _direct_argument(expression: str, symbols: tuple[str, ...]) -> bool:
    """Whether one call argument is a direct representation of one discovered fact."""

    if len(symbols) != 1:
        return False
    try:
        node = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return False
    while isinstance(node, ast.Call):
        name = _call_name(node.func)
        if name in _EXACT_WRAPPERS and len(node.args) == 1:
            node = node.args[0]
            continue
        break
    return isinstance(node, (ast.Name, ast.Attribute, ast.Subscript))


def unify_discovery(report: DiscoveryReport) -> UnificationReport:
    """Collapse strongly evidenced aliases into candidate semantic concepts."""

    uf = _UnionFind()
    members_by_key: dict[str, SemanticMember] = {}
    formula_occurrences: list[tuple[CandidateFormula, str, tuple[str, ...], str | None, float]] = []
    alias_evidence: dict[str, list[str]] = defaultdict(list)
    warnings: list[str] = []

    # Function parameters and call arguments are first-class code facts even if a
    # particular parameter has no assignment of its own.
    for function in report.functions:
        for parameter in function.parameters:
            key = _member_key(parameter, function.anchor)
            members_by_key.setdefault(
                key,
                SemanticMember(
                    key=key,
                    symbol=parameter,
                    anchor=function.anchor,
                    scope=_scope(function.anchor),
                ),
            )
            uf.add(key)
    for call in report.calls:
        for symbols in call.argument_symbols:
            for symbol in symbols:
                key = _member_key(symbol, call.anchor)
                members_by_key.setdefault(
                    key,
                    SemanticMember(
                        key=key,
                        symbol=symbol,
                        anchor=call.anchor,
                        scope=_scope(call.anchor),
                    ),
                )
                uf.add(key)

    for formula in report.formulas:
        output_key = _member_key(formula.output_symbol, formula.anchor)
        output_member = SemanticMember(
            key=output_key,
            symbol=formula.output_symbol,
            anchor=formula.anchor,
            scope=_scope(formula.anchor),
        )
        members_by_key.setdefault(output_key, output_member)
        uf.add(output_key)

        input_keys: list[str] = []
        for symbol in formula.input_symbols:
            key = _member_key(symbol, formula.anchor)
            members_by_key.setdefault(
                key,
                SemanticMember(key=key, symbol=symbol, anchor=formula.anchor, scope=_scope(formula.anchor)),
            )
            uf.add(key)
            input_keys.append(key)

        alias_kind, alias_confidence = _alias_kind(formula)
        if alias_kind and len(input_keys) == 1:
            input_key = input_keys[0]
            # Direct/representation projections are safe.  Domain-normalizing aliases
            # additionally require lexical support, enforced by _alias_kind.
            uf.union(output_key, input_key)
            alias_evidence[output_key].append(
                f"{alias_kind}:{formula.anchor.path}:{formula.anchor.line}:{formula.expression}"
            )
            alias_evidence[input_key].append(
                f"{alias_kind}:{formula.anchor.path}:{formula.anchor.line}:{formula.expression}"
            )
        formula_occurrences.append(
            (formula, output_key, tuple(input_keys), alias_kind, alias_confidence)
        )

    grouped: dict[str, list[SemanticMember]] = defaultdict(list)
    for key, member in members_by_key.items():
        grouped[uf.find(key)].append(member)

    concepts: list[UnifiedConcept] = []
    key_to_concept: dict[str, str] = {}
    for root in sorted(grouped):
        deduped = list({member.key: member for member in grouped[root]}.values())
        deduped.sort(key=lambda item: (item.symbol, item.scope, item.anchor.line))
        concept_id = _stable_id("semantic", *sorted(member.key for member in deduped))
        confidence = 0.55 if len(deduped) == 1 else 0.78
        evidence = sorted(
            {
                evidence
                for member in deduped
                for evidence in alias_evidence.get(member.key, ())
            }
        )
        if evidence:
            confidence = min(0.99, 0.78 + min(0.18, 0.03 * len(evidence)))
        concept = UnifiedConcept(
            id=concept_id,
            display_name=_display_name(deduped),
            members=tuple(deduped),
            confidence=confidence,
            evidence=tuple(evidence),
        )
        concepts.append(concept)
        for member in deduped:
            key_to_concept[member.key] = concept_id

    unified_formulas: list[UnifiedFormula] = []
    for (
        candidate_formula,
        occurrence_output_key,
        occurrence_input_keys,
        occurrence_alias_kind,
        occurrence_alias_confidence,
    ) in formula_occurrences:
        output_concept = key_to_concept[occurrence_output_key]
        input_concepts = tuple(
            dict.fromkeys(key_to_concept[member_key] for member_key in occurrence_input_keys)
        )
        is_alias = bool(
            occurrence_alias_kind
            and len(input_concepts) == 1
            and input_concepts[0] == output_concept
        )
        unified_formulas.append(
            UnifiedFormula(
                id=_stable_id(
                    "semantic_formula", candidate_formula.id, output_concept, input_concepts
                ),
                output_concept_id=output_concept,
                output_symbol=candidate_formula.output_symbol,
                input_symbols=candidate_formula.input_symbols,
                input_concept_ids=input_concepts,
                expression=candidate_formula.expression,
                context=candidate_formula.anchor.context,
                anchor=candidate_formula.anchor,
                source_formula_id=candidate_formula.id,
                is_alias_projection=is_alias,
                confidence=max(
                    candidate_formula.confidence,
                    occurrence_alias_confidence if is_alias else 0.0,
                ),
            )
        )

    rel_groups: dict[
        tuple[str, str, str, tuple[str, ...]], list[UnifiedFormula]
    ] = defaultdict(list)
    for unified_formula in unified_formulas:
        for input_concept in unified_formula.input_concept_ids:
            if input_concept == unified_formula.output_concept_id:
                continue
            relationship_key = (
                unified_formula.output_concept_id,
                input_concept,
                "derived_from",
                unified_formula.context,
            )
            rel_groups[relationship_key].append(unified_formula)

    # Interprocedural parameter flow is represented as a relationship rather than a
    # union. Generic helpers may receive semantically different values at different
    # call sites; merging them would collapse unrelated business concepts.
    functions_by_name: dict[str, list[CandidateFunction]] = defaultdict(list)
    for function in report.functions:
        functions_by_name[function.name].append(function)
    call_relations: list[
        tuple[str, str, tuple[str, ...], tuple[CodeAnchor, ...], float]
    ] = []
    for call in report.calls:
        definitions = functions_by_name.get(call.callee, ())
        if len(definitions) != 1:
            continue
        function = definitions[0]
        for index, (expression, symbols) in enumerate(
            zip(call.argument_expressions, call.argument_symbols, strict=True)
        ):
            if index >= len(function.parameters) or not _direct_argument(expression, symbols):
                continue
            argument_symbol = symbols[0]
            parameter_symbol = function.parameters[index]
            parameter_key = _member_key(parameter_symbol, function.anchor)
            argument_key = _member_key(argument_symbol, call.anchor)
            if parameter_key not in key_to_concept or argument_key not in key_to_concept:
                continue
            call_source = key_to_concept[parameter_key]
            call_target = key_to_concept[argument_key]
            if call_source == call_target:
                continue
            call_relations.append(
                (
                    call_source,
                    call_target,
                    call.anchor.context,
                    (call.anchor, function.anchor),
                    0.92,
                )
            )

    relationships: list[UnifiedRelationship] = []
    for relationship_key, rows in sorted(rel_groups.items(), key=lambda item: item[0]):
        relation_source, relation_target, relation_type, relation_context = relationship_key
        relation_anchors = tuple(dict.fromkeys(row.anchor for row in rows))
        relationships.append(
            UnifiedRelationship(
                id=_stable_id(
                    "semantic_relationship",
                    relation_source,
                    relation_target,
                    relation_type,
                    relation_context,
                ),
                source_concept_id=relation_source,
                target_concept_id=relation_target,
                relationship_type=relation_type,
                context=relation_context,
                anchors=relation_anchors,
                confidence=max(row.confidence for row in rows),
            )
        )
    for (
        call_source,
        call_target,
        call_context,
        call_anchors,
        call_confidence,
    ) in call_relations:
        relationships.append(
            UnifiedRelationship(
                id=_stable_id(
                    "semantic_relationship",
                    call_source,
                    call_target,
                    "parameter_from",
                    call_context,
                    call_anchors[0].path,
                    call_anchors[0].line,
                ),
                source_concept_id=call_source,
                target_concept_id=call_target,
                relationship_type="parameter_from",
                context=call_context,
                anchors=call_anchors,
                confidence=call_confidence,
            )
        )

    symbol_to_concept: dict[str, str] = {}
    collisions: set[str] = set()
    for concept in concepts:
        for member in concept.members:
            prior = symbol_to_concept.get(member.symbol)
            if prior is None:
                symbol_to_concept[member.symbol] = concept.id
            elif prior != concept.id:
                collisions.add(member.symbol)
    for symbol in collisions:
        symbol_to_concept.pop(symbol, None)
        warnings.append(
            f"symbol {symbol!r} is scope-ambiguous; use scoped member identity instead"
        )

    return UnificationReport(
        target_root=report.target_root,
        concepts=tuple(sorted(concepts, key=lambda item: (item.display_name, item.id))),
        formulas=tuple(
            sorted(
                unified_formulas,
                key=lambda item: (item.anchor.path, item.anchor.line, item.id),
            )
        ),
        relationships=tuple(relationships),
        symbol_to_concept=symbol_to_concept,
        warnings=tuple(warnings),
        metadata={
            **report.metadata,
            "discovery_concepts": str(len(report.concepts)),
            "unified_concepts": str(len(concepts)),
        },
    )
