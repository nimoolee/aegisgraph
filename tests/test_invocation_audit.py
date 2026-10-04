from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aegis_graph.audit import (
    append_invocation,
    default_audit_path,
    load_invocations,
    new_record,
    summarize_invocations,
)


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


def test_invocation_loader_warns_when_malformed_rows_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "invocations.jsonl"
    path.write_text('{bad json}\n', encoding="utf-8")
    with pytest.warns(RuntimeWarning, match="malformed"):
        assert load_invocations(path) == ()


def test_default_audit_path_uses_aegis_owned_state_dir(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AEGISGRAPH_STATE_DIR", str(state_dir))
    assert default_audit_path() == state_dir / "aegis-invocations.jsonl"


def test_new_record_canonicalizes_relative_target(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "target"
    target.mkdir()
    monkeypatch.chdir(tmp_path)
    record = new_record(mode="semantic_discovery", target="target")
    assert record.target == str(target.resolve())


def test_concurrent_audit_appends_remain_valid_json_lines(tmp_path: Path) -> None:
    path = tmp_path / "invocations.jsonl"
    target = tmp_path / "target"
    target.mkdir()

    def append_one(index: int) -> None:
        append_invocation(
            new_record(
                mode="semantic_discovery",
                target=str(target),
                note=f"run-{index}",
            ),
            path,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append_one, range(40)))

    records = load_invocations(path)
    assert len(records) == 40
    assert {record.note for record in records} == {f"run-{index}" for index in range(40)}


def test_invalid_invocation_fields_fail_closed(tmp_path: Path) -> None:
    target = str(tmp_path / "target")
    with pytest.raises(ValueError, match="invalid invocation verdict"):
        new_record(mode="x", target=target, verdict="maybe")
    with pytest.raises(ValueError, match="duration_ms"):
        new_record(mode="x", target=target, duration_ms=-1)


def test_invalid_utf8_audit_row_is_warned_and_skipped(tmp_path: Path) -> None:
    path = tmp_path / "invocations.jsonl"
    path.write_bytes(b"\xff\xfe\n")
    with pytest.warns(RuntimeWarning, match="malformed"):
        assert load_invocations(path) == ()


def test_limited_audit_load_keeps_only_latest_records(tmp_path: Path) -> None:
    path = tmp_path / "invocations.jsonl"
    target = tmp_path / "target"
    target.mkdir()
    for index in range(25):
        append_invocation(
            new_record(mode="semantic_discovery", target=str(target), note=f"run-{index}"),
            path,
        )

    latest = load_invocations(path, limit=3)
    assert [record.note for record in latest] == ["run-22", "run-23", "run-24"]
    assert load_invocations(path, limit=0) == ()


def test_oversized_audit_record_is_rejected_before_write(tmp_path: Path) -> None:
    path = tmp_path / "invocations.jsonl"
    target = tmp_path / "target"
    target.mkdir()
    record = new_record(
        mode="semantic_discovery",
        target=str(target),
        note="x" * (1024 * 1024),
    )

    with pytest.raises(ValueError, match="exceeds"):
        append_invocation(record, path)
    assert not path.exists()
