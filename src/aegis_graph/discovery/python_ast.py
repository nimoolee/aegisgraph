"""Read-only Python AST semantic discovery.

v0.1 deliberately does not know any trading vocabulary.  It extracts candidate
concepts, formulas and data-flow relationships from code structure while keeping
file/function/conditional provenance.  Naming/unification into accepted business
concepts is a later layer.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import replace
import hashlib
from pathlib import Path
import subprocess
from typing import Iterable

from aegis_graph.discovery.models import (
    CandidateCall,
    CandidateFunction,
    CandidateConcept,
    CandidateFormula,
    CandidateRelationship,
    CodeAnchor,
    DiscoveryReport,
)


_EXCLUDED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "site-packages",
    "dist",
    "build",
    "__pycache__",
}


def _stable_id(prefix: str, *parts: object) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}.{digest}"


def _symbol(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _symbol(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        base = _symbol(node.value)
        if not base:
            return None
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            return f'{base}["{key.value}"]'
        try:
            return f"{base}[{ast.unparse(key)}]"
        except Exception:
            return base
    return None


def _assignment_targets(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript)):
        symbol = _symbol(node)
        return (symbol,) if symbol else ()
    if isinstance(node, (ast.Tuple, ast.List)):
        result: list[str] = []
        for item in node.elts:
            result.extend(_assignment_targets(item))
        return tuple(result)
    return ()


class _InputCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        self.symbols.add(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        symbol = _symbol(node)
        if symbol:
            self.symbols.add(symbol)
        # The complete attribute is more useful than also adding its base object.

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        symbol = _symbol(node)
        if symbol:
            self.symbols.add(symbol)
        # The complete keyed fact is more useful than also adding the container.

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        # ``state.get("trade_cash")`` is a common implicit fact read.  Treat the
        # keyed value as the input rather than the generic ``state.get`` method.
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            base = _symbol(node.func.value)
            if base:
                self.symbols.add(f'{base}["{node.args[0].value}"]')
            for arg in node.args[1:]:
                self.visit(arg)
            for keyword in node.keywords:
                self.visit(keyword.value)
            return
        # For ordinary method calls, the receiver is an input fact as well.  This is
        # essential for recognizing sequential refinements such as amount.quantize().
        if isinstance(node.func, ast.Attribute):
            self.visit(node.func.value)
        # Function names such as min/max/Decimal are operators, not fact inputs.
        for arg in node.args:
            self.visit(arg)
        for keyword in node.keywords:
            self.visit(keyword.value)


def _input_symbols(node: ast.AST) -> tuple[str, ...]:
    collector = _InputCollector()
    collector.visit(node)
    return tuple(sorted(collector.symbols))


def _confidence(expr: ast.AST, inputs: tuple[str, ...]) -> float:
    if not inputs:
        return 0.45
    if isinstance(expr, (ast.BinOp, ast.BoolOp, ast.Compare, ast.IfExp)):
        return 0.9
    if isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Name) and expr.func.id in {"min", "max", "sum"}:
            return 0.95
        return 0.78
    if isinstance(expr, (ast.Name, ast.Attribute, ast.Subscript)):
        return 0.72
    return 0.82


class _FileVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self.function_stack: list[str] = []
        self.class_stack: list[str] = []
        self.context_stack: list[str] = []
        self.formulas: list[CandidateFormula] = []
        self.functions: list[CandidateFunction] = []
        self.calls: list[CandidateCall] = []
        self.relationships: list[CandidateRelationship] = []
        self._concept_anchors: dict[str, list[CodeAnchor]] = defaultdict(list)
        self._concept_confidence: dict[str, float] = defaultdict(lambda: 0.5)

    def _anchor(self, node: ast.AST) -> CodeAnchor:
        return CodeAnchor(
            path=self.relative_path,
            line=getattr(node, "lineno", 0),
            column=getattr(node, "col_offset", 0),
            function=self.function_stack[-1] if self.function_stack else None,
            class_name=".".join(self.class_stack) if self.class_stack else None,
            context=tuple(self.context_stack),
        )

    def _remember_concept(self, symbol: str, anchor: CodeAnchor, confidence: float) -> None:
        if anchor not in self._concept_anchors[symbol]:
            self._concept_anchors[symbol].append(anchor)
        self._concept_confidence[symbol] = max(self._concept_confidence[symbol], confidence)

    def _record_formula(self, output: str, expr: ast.AST, node: ast.AST) -> None:
        inputs = tuple(symbol for symbol in _input_symbols(expr) if symbol != output)
        if not inputs:
            return
        try:
            expression = ast.unparse(expr)
        except Exception:
            return
        anchor = self._anchor(node)
        confidence = _confidence(expr, inputs)
        formula = CandidateFormula(
            id=_stable_id(
                "formula",
                self.relative_path,
                anchor.line,
                output,
                expression,
                anchor.context,
            ),
            output_symbol=output,
            input_symbols=inputs,
            expression=expression,
            anchor=anchor,
            confidence=confidence,
        )
        self.formulas.append(formula)
        self._remember_concept(output, anchor, confidence)
        for input_symbol in inputs:
            self._remember_concept(input_symbol, anchor, min(confidence, 0.8))
            self.relationships.append(
                CandidateRelationship(
                    id=_stable_id(
                        "relationship",
                        self.relative_path,
                        anchor.line,
                        output,
                        input_symbol,
                        anchor.context,
                    ),
                    source_symbol=output,
                    target_symbol=input_symbol,
                    relationship_type="derived_from",
                    anchor=anchor,
                    confidence=confidence,
                )
            )

    def _record_return_dict(self, node: ast.Return, value: ast.Dict) -> None:
        for key, expr in zip(value.keys, value.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                self._record_formula(f'return["{key.value}"]', expr, node)

    def _record_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        parameters = tuple(
            arg.arg
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        )
        anchor = CodeAnchor(
            path=self.relative_path,
            line=getattr(node, "lineno", 0),
            column=getattr(node, "col_offset", 0),
            function=node.name,
            class_name=".".join(self.class_stack) if self.class_stack else None,
            context=tuple(self.context_stack),
        )
        self.functions.append(
            CandidateFunction(
                id=_stable_id(
                    "function",
                    self.relative_path,
                    anchor.class_name or "<module>",
                    node.name,
                    anchor.line,
                ),
                name=node.name,
                parameters=parameters,
                anchor=anchor,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.class_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._record_function(node)
        self.function_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._record_function(node)
        self.function_stack.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.function_stack.pop()

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        try:
            condition = ast.unparse(node.test)
        except Exception:
            condition = "<condition>"
        self.visit(node.test)
        self.context_stack.append(condition)
        for statement in node.body:
            self.visit(statement)
        self.context_stack.pop()
        if node.orelse:
            self.context_stack.append(f"not ({condition})")
            for statement in node.orelse:
                self.visit(statement)
            self.context_stack.pop()

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        self.context_stack.append("try")
        for statement in node.body:
            self.visit(statement)
        self.context_stack.pop()
        for handler in node.handlers:
            try:
                label = ast.unparse(handler.type) if handler.type is not None else "*"
            except Exception:
                label = "*"
            self.context_stack.append(f"except {label}")
            for statement in handler.body:
                self.visit(statement)
            self.context_stack.pop()
        if node.orelse:
            self.context_stack.append("try else")
            for statement in node.orelse:
                self.visit(statement)
            self.context_stack.pop()
        if node.finalbody:
            self.context_stack.append("finally")
            for statement in node.finalbody:
                self.visit(statement)
            self.context_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Name):
            callee = node.func.id
        elif isinstance(node.func, ast.Attribute):
            callee = node.func.attr
        else:
            callee = ""
        if callee:
            expressions: list[str] = []
            symbols: list[tuple[str, ...]] = []
            for arg in node.args:
                try:
                    expressions.append(ast.unparse(arg))
                except Exception:
                    expressions.append("<expression>")
                symbols.append(_input_symbols(arg))
            anchor = self._anchor(node)
            self.calls.append(
                CandidateCall(
                    id=_stable_id(
                        "call",
                        self.relative_path,
                        anchor.line,
                        anchor.column,
                        callee,
                        tuple(expressions),
                    ),
                    callee=callee,
                    argument_expressions=tuple(expressions),
                    argument_symbols=tuple(symbols),
                    anchor=anchor,
                )
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            for output in _assignment_targets(target):
                self._record_formula(output, node.value, node)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if node.value is not None:
            for output in _assignment_targets(node.target):
                self._record_formula(output, node.value, node)
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        for output in _assignment_targets(node.target):
            synthetic = ast.BinOp(left=node.target, op=node.op, right=node.value)
            ast.copy_location(synthetic, node)
            self._record_formula(output, synthetic, node)
        self.visit(node.value)

    def visit_Return(self, node: ast.Return) -> None:  # noqa: N802
        if isinstance(node.value, ast.Dict):
            self._record_return_dict(node, node.value)
        if node.value is not None:
            self.visit(node.value)

    def concepts(self) -> tuple[CandidateConcept, ...]:
        rows = []
        for symbol in sorted(self._concept_anchors):
            rows.append(
                CandidateConcept(
                    id=_stable_id("concept", symbol),
                    symbol=symbol,
                    confidence=self._concept_confidence[symbol],
                    anchors=tuple(self._concept_anchors[symbol]),
                )
            )
        return tuple(rows)


def _git_worktree_python_files(root: Path) -> tuple[Path, ...] | None:
    """Return current Git worktree Python files, including non-ignored new files.

    Git is the preferred boundary because ignored runtime snapshots/backups are
    historical evidence, not current implementation semantics.  ``None`` means
    the target is not a usable Git worktree and discovery should fall back to a
    filesystem scan.
    """

    try:
        probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if probe.stdout.strip() != "true":
            return None
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                "*.py",
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    paths: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8", errors="surrogateescape"))
        path = root / relative
        if path.is_file():
            paths.append(path)
    return tuple(sorted(paths))


def _python_files(root: Path, *, include_tests: bool) -> tuple[Iterable[Path], str]:
    git_files = _git_worktree_python_files(root)
    candidates: Iterable[Path]
    source_selection: str
    if git_files is not None:
        candidates = git_files
        source_selection = "git_worktree"
    else:
        candidates = sorted(root.rglob("*.py"))
        source_selection = "filesystem"

    selected: list[Path] = []
    for path in candidates:
        relative = path.relative_to(root)
        parts = set(relative.parts)
        if parts.intersection(_EXCLUDED_PARTS):
            continue
        if not include_tests and (
            "tests" in relative.parts
            or path.name.startswith("test_")
            or path.name.endswith("_test.py")
        ):
            continue
        selected.append(path)
    return tuple(selected), source_selection


def discover_python(target_root: str | Path, *, include_tests: bool = False) -> DiscoveryReport:
    """Discover implementation semantics from Python without modifying the target."""

    root = Path(target_root).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)

    concepts_by_symbol: dict[str, CandidateConcept] = {}
    formulas: list[CandidateFormula] = []
    relationships: list[CandidateRelationship] = []
    functions: list[CandidateFunction] = []
    calls: list[CandidateCall] = []
    warnings: list[str] = []
    files_scanned = 0
    python_files, source_selection = _python_files(root, include_tests=include_tests)

    for path in python_files:
        files_scanned += 1
        relative = str(path.relative_to(root))
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=relative)
        except (OSError, SyntaxError) as exc:
            warnings.append(f"{relative}: {type(exc).__name__}: {exc}")
            continue

        visitor = _FileVisitor(relative)
        visitor.visit(tree)
        formulas.extend(visitor.formulas)
        relationships.extend(visitor.relationships)
        functions.extend(visitor.functions)
        calls.extend(visitor.calls)
        for concept in visitor.concepts():
            prior = concepts_by_symbol.get(concept.symbol)
            if prior is None:
                concepts_by_symbol[concept.symbol] = concept
                continue
            anchors = tuple(dict.fromkeys((*prior.anchors, *concept.anchors)))
            concepts_by_symbol[concept.symbol] = replace(
                prior,
                confidence=max(prior.confidence, concept.confidence),
                anchors=anchors,
            )

    formulas.sort(key=lambda item: (item.anchor.path, item.anchor.line, item.output_symbol))
    relationships.sort(
        key=lambda item: (item.anchor.path, item.anchor.line, item.source_symbol, item.target_symbol)
    )
    return DiscoveryReport(
        target_root=str(root),
        language="python",
        files_scanned=files_scanned,
        concepts=tuple(concepts_by_symbol[key] for key in sorted(concepts_by_symbol)),
        formulas=tuple(formulas),
        relationships=tuple(relationships),
        functions=tuple(sorted(functions, key=lambda item: (item.anchor.path, item.anchor.line, item.name))),
        calls=tuple(sorted(calls, key=lambda item: (item.anchor.path, item.anchor.line, item.anchor.column))),
        warnings=tuple(warnings),
        metadata={"source_selection": source_selection},
    )
