from pathlib import Path

from aegis_graph.audit import append_invocation, load_invocations, new_record, summarize_invocations


def test_invocation_audit_is_append_only_and_summarizable(tmp_path: Path) -> None:
    path = tmp_path / "invocations.jsonl"
    append_invocation(new_record(mode="semantic_discovery", target="/tmp/a", duration_ms=12), path)
    append_invocation(new_record(mode="accepted_rule_proof", target="/tmp/a", verdict="fail", duration_ms=34), path)
    records = load_invocations(path)
    assert len(records) == 2
    assert records[0].mode == "semantic_discovery"
    assert records[1].verdict == "fail"
    summary = summarize_invocations(records)
    assert summary["total"] == 2
    assert summary["fail"] == 1
    assert summary["modes"] == {"accepted_rule_proof": 1, "semantic_discovery": 1}


def test_invocation_loader_ignores_malformed_rows(tmp_path: Path) -> None:
    path = tmp_path / "invocations.jsonl"
    path.write_text('{bad json}\n', encoding="utf-8")
    assert load_invocations(path) == ()
