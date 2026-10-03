from pathlib import Path
import subprocess

from aegis_graph.discovery import SemanticStatus, discover_python


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


def test_semantic_lifecycle_has_incomplete_software_states() -> None:
    assert SemanticStatus.CANDIDATE.value == "candidate"
    assert SemanticStatus.CONFLICTED.value == "conflicted"
    assert SemanticStatus.UNDEFINED.value == "undefined"
    assert SemanticStatus.UNIMPLEMENTED.value == "unimplemented"
    assert SemanticStatus.UNKNOWN.value == "unknown"
