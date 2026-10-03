from __future__ import annotations

from pathlib import Path

from aegis_graph.cli import main
from aegis_graph.demo import run_demo
from aegis_graph.proof.models import ProofVerdict


def test_demo_shows_fail_then_pass(capsys) -> None:
    broken, fixed = run_demo()
    assert broken.verdict is ProofVerdict.FAIL
    assert fixed.verdict is ProofVerdict.PASS
    assert main(["demo"]) == 0
    output = capsys.readouterr().out
    assert "Broken implementation -> FAIL" in output
    assert "Repaired implementation -> PASS" in output


def test_check_returns_zero_for_simple_python_target(tmp_path: Path, capsys) -> None:
    (tmp_path / "app.py").write_text("total = cash + profit\n", encoding="utf-8")
    assert main(["check", str(tmp_path), "--limit", "3"]) == 0
    output = capsys.readouterr().out
    assert "AEGISGRAPH SEMANTIC CONFLICT REPORT" in output
    assert "Conflicts: 0" in output
