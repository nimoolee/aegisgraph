from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import aegis_graph.cli as cli
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


def test_check_never_writes_audit_state_into_target(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text("total = cash + profit\n", encoding="utf-8")
    state_dir = tmp_path / "aegis-state"
    monkeypatch.setenv("AEGISGRAPH_STATE_DIR", str(state_dir))
    monkeypatch.chdir(target)

    assert main(["check", "."]) == 0
    assert not (target / "runtime").exists()
    assert (state_dir / "aegis-invocations.jsonl").is_file()


def test_check_returns_unknown_when_source_evidence_is_incomplete(tmp_path: Path, capsys) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    assert main(["check", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "SyntaxError" in captured.err
    assert "SCAN STATUS: UNKNOWN" in captured.err


def test_check_returns_tool_error_for_missing_target(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing"
    assert main(["check", str(missing)]) == 2
    assert "AEGISGRAPH ERROR" in capsys.readouterr().err


def test_check_empty_target_is_unknown_not_pass(tmp_path: Path, capsys) -> None:
    assert main(["check", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "no Python source files selected" in captured.err
    assert "SCAN STATUS: UNKNOWN" in captured.err


def test_check_returns_fail_when_a_conflict_is_proven_even_with_scan_warning(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    monkeypatch.setenv("AEGISGRAPH_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(
        cli,
        "detect_conflicts",
        lambda _report: SimpleNamespace(conflicts=(object(),)),
    )
    monkeypatch.setattr(cli, "render_conflicts", lambda *_args: "synthetic conflict")

    assert main(["check", str(target)]) == 1
    captured = capsys.readouterr()
    assert "synthetic conflict" in captured.out
    assert "SyntaxError" in captured.err


def test_audit_override_inside_target_is_rejected_without_mutating_target(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text("total = cash + profit\n", encoding="utf-8")
    monkeypatch.setenv("AEGISGRAPH_STATE_DIR", str(target / "runtime"))

    assert main(["check", str(target)]) == 0
    assert not (target / "runtime").exists()
    assert "AUDIT WARNING" in capsys.readouterr().err
