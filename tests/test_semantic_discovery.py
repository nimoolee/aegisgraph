import os
import subprocess
from pathlib import Path

import pytest

from aegis_graph.discovery import (
    CandidateCall,
    CandidateConcept,
    CandidateFormula,
    CodeAnchor,
    DiscoveryReport,
    SemanticStatus,
    discover_python,
    python_ast,
)
from aegis_graph.discovery.render import render_discovery
from aegis_graph.semantics import unify_discovery


def write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_discovers_formula_without_business_predefinition(tmp_path: Path) -> None:
    write(
        tmp_path,
        "runner.py",
        '''
def snapshot(state, balance, mode):
    cash = max(0, balance)
    if mode == "SAFE":
        trade = max(0, state.get("trade_account_balance"))
        headroom = min(trade, cash)
        orderable = headroom if headroom >= 5 else 0
    return {"orderable_balance": orderable}
''',
    )

    report = discover_python(tmp_path)
    formula = next(row for row in report.formulas if row.output_symbol == "headroom")
    assert formula.expression == "min(trade, cash)"
    assert formula.input_symbols == ("cash", "trade")
    assert "mode == 'SAFE'" in formula.anchor.context

    trade_formula = next(row for row in report.formulas if row.output_symbol == "trade")
    assert 'state["trade_account_balance"]' in trade_formula.input_symbols

    projection = next(
        row for row in report.formulas if row.output_symbol == 'return["orderable_balance"]'
    )
    assert projection.input_symbols == ("orderable",)


def test_same_output_in_different_contexts_remains_distinct(tmp_path: Path) -> None:
    write(
        tmp_path,
        "policy.py",
        '''
def calculate(mode, trading, cash, locked):
    if mode == "SAFE":
        orderable = min(trading, cash)
    else:
        orderable = max(0, cash - locked)
    return orderable
''',
    )
    report = discover_python(tmp_path)
    rows = [row for row in report.formulas if row.output_symbol == "orderable"]
    assert len(rows) == 2
    assert {row.expression for row in rows} == {
        "min(trading, cash)",
        "max(0, cash - locked)",
    }
    assert rows[0].anchor.context != rows[1].anchor.context


def test_tests_are_supporting_evidence_not_default_definition_source(tmp_path: Path) -> None:
    write(tmp_path, "app.py", "value = source + 1\n")
    write(tmp_path, "tests/test_app.py", "value = source + 999\n")

    report = discover_python(tmp_path)
    expressions = {row.expression for row in report.formulas}
    assert "source + 1" in expressions
    assert "source + 999" not in expressions

    with_tests = discover_python(tmp_path, include_tests=True)
    assert "source + 999" in {row.expression for row in with_tests.formulas}


def test_git_boundary_excludes_ignored_runtime_snapshots(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write(tmp_path, ".gitignore", "runtime/\n")
    write(tmp_path, "app.py", "current = min(left, right)\n")
    write(tmp_path, "runtime/old.py", "current = left - right\n")

    report = discover_python(tmp_path)
    expressions = {row.expression for row in report.formulas}
    assert "min(left, right)" in expressions
    assert "left - right" not in expressions
    assert report.metadata["source_selection"] == "git_worktree"
    with pytest.raises(TypeError):
        report.metadata["source_selection"] = "forged"  # type: ignore[index]


def test_discovery_honors_python_source_encoding(tmp_path: Path) -> None:
    path = tmp_path / "latin1.py"
    path.write_bytes(
        '# -*- coding: latin-1 -*-\nlabel = source + "café"\n'.encode("latin-1")
    )
    report = discover_python(tmp_path)
    assert not report.warnings
    formula = next(row for row in report.formulas if row.output_symbol == "label")
    assert "café" in formula.expression


def test_discovery_skips_symlink_sources_outside_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("leaked = secret + password\n", encoding="utf-8")
    link = target / "linked.py"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")

    report = discover_python(target)
    assert "secret + password" not in {row.expression for row in report.formulas}
    assert any("symbolic-link source skipped" in warning for warning in report.warnings)


def test_discovery_reports_source_size_limit_as_incomplete(
    tmp_path: Path, monkeypatch
) -> None:
    write(tmp_path, "large.py", "result = left + right\n")
    monkeypatch.setattr(python_ast, "MAX_SOURCE_BYTES", 5)
    report = discover_python(tmp_path)
    assert report.files_scanned == 0
    assert any("source size" in warning for warning in report.warnings)


def test_discovery_file_count_limit_marks_scan_incomplete(
    tmp_path: Path, monkeypatch
) -> None:
    write(tmp_path, "a.py", "a = source + 1\n")
    write(tmp_path, "b.py", "b = source + 2\n")
    monkeypatch.setattr(python_ast, "MAX_SOURCE_FILES", 1)

    report = discover_python(tmp_path)
    assert report.files_scanned == 1
    assert any("source file limit exceeded" in warning for warning in report.warnings)


def test_discovery_total_source_budget_marks_scan_incomplete(
    tmp_path: Path, monkeypatch
) -> None:
    first = write(tmp_path, "a.py", "a = source + 1\n")
    write(tmp_path, "b.py", "b = source + 2\n")
    monkeypatch.setattr(python_ast, "MAX_TOTAL_SOURCE_BYTES", first.stat().st_size)

    report = discover_python(tmp_path)
    assert report.files_scanned == 1
    assert any("total source size exceeds" in warning for warning in report.warnings)


def test_semantic_lifecycle_has_incomplete_software_states() -> None:
    assert SemanticStatus.CANDIDATE.value == "candidate"
    assert SemanticStatus.CONFLICTED.value == "conflicted"
    assert SemanticStatus.UNDEFINED.value == "undefined"
    assert SemanticStatus.UNIMPLEMENTED.value == "unimplemented"
    assert SemanticStatus.UNKNOWN.value == "unknown"


def test_discovery_renderer_handles_filter_limit_and_no_match(tmp_path: Path) -> None:
    write(tmp_path, "app.py", "total = cash + profit\nother = debit - credit\n")
    report = discover_python(tmp_path)

    rendered = render_discovery(report, contains="total", limit=1)
    assert "AEGISGRAPH SEMANTIC DISCOVERY" in rendered
    assert "total = cash + profit" in rendered
    assert "other = debit - credit" not in rendered

    assert "<no matching candidate formulas>" in render_discovery(
        report, contains="definitely-missing", limit=-1
    )


def test_discovery_value_objects_detach_from_caller_mutation() -> None:
    context = ["mode == 'SAFE'"]
    inputs = ["left"]
    anchors: list[CodeAnchor] = []
    argument_symbols = [["source"]]
    formulas: list[CandidateFormula] = []

    anchor = CodeAnchor("app.py", 1, function="calculate", context=context)  # type: ignore[arg-type]
    formula = CandidateFormula(
        id="formula.detached",
        output_symbol="metric",
        input_symbols=inputs,  # type: ignore[arg-type]
        expression="left + 1",
        anchor=anchor,
    )
    concept = CandidateConcept(
        id="concept.detached",
        symbol="metric",
        anchors=anchors,  # type: ignore[arg-type]
    )
    call = CandidateCall(
        id="call.detached",
        callee="helper",
        argument_expressions=["source"],  # type: ignore[arg-type]
        argument_symbols=argument_symbols,  # type: ignore[arg-type]
        anchor=anchor,
    )
    formulas.append(formula)
    report = DiscoveryReport(
        target_root="/tmp/detached",
        language="python",
        files_scanned=1,
        concepts=[concept],  # type: ignore[arg-type]
        formulas=formulas,  # type: ignore[arg-type]
        relationships=[],  # type: ignore[arg-type]
        calls=[call],  # type: ignore[arg-type]
    )

    context.append("forged-context")
    inputs.append("forged-input")
    anchors.append(anchor)
    argument_symbols[0].append("forged-symbol")
    formulas.append(
        CandidateFormula(
            id="formula.forged",
            output_symbol="metric",
            input_symbols=("right",),
            expression="right * 2",
            anchor=CodeAnchor("other.py", 2, function="other"),
        )
    )

    assert anchor.context == ("mode == 'SAFE'",)
    assert formula.input_symbols == ("left",)
    assert concept.anchors == ()
    assert call.argument_symbols == (("source",),)
    assert report.formulas == (formula,)
    assert isinstance(report.formulas, tuple)

    unified = unify_discovery(report)
    assert len(unified.formulas) == 1
