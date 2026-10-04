import json
import os
from pathlib import Path

import pytest

from aegis_graph.integrations.auto_trading_audit import audit_target, render_audit
from aegis_graph.integrations.auto_trading_evidence import collect_evidence
from aegis_graph.proof.models import ProofVerdict


def _write_target(root: Path) -> None:
    runtime = root / "runtime"
    runtime.mkdir(parents=True)
    token = "mixed-token"
    state = {
        "account_balance": 20.0,
        "trade_account_balance": 6.0,
        "safe_account_balance": 14.0,
        "bot_positions": {},
        "pending_settlements": [],
        "orderable_balance": 6.0,
        "external_positions": {},
        "manual_funding": {token: {
            "round_id": "round-1", "condition_id": "condition-1",
            "activity_buy_shares": 6.0, "activity_sold_shares": 10.0,
            "cash_returned": 5.4,
        }},
        "bot_buy_fills": {token: {
            "round_id": "round-1", "condition_id": "condition-1",
            "filled_shares": 4.0,
            "mixed_sell_receipt_shares": 4.0,
            "mixed_sell_receipt_proceeds": 3.6,
            "response_ms": 100,
        }},
        "settlement_cash_sync_pending": None,
    }
    (runtime / "live_test_state.json").write_text(json.dumps(state), encoding="utf-8")
    event = {
        "kind": "MANUAL_CASH_RETURN", "token_id": token, "return_type": "TRADE",
        "activity_key": "tx|TRADE|mixed-token|9.0", "proceeds": 5.4,
    }
    (runtime / "live_test_orders.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")


def test_evidence_adapter_reads_target_without_embedding_expected_answer(tmp_path: Path) -> None:
    _write_target(tmp_path)
    evidence = collect_evidence(tmp_path)
    assert evidence.fact_values["auto.position.physical_sell_shares"] == 10.0
    assert evidence.fact_values["auto.position.manual_total_shares"] == 6.0
    assert evidence.fact_values["auto.position.bot_sold_shares"] == 4.0
    assert str(evidence.fact_values["auto.cash.physical_sell_proceeds"]) == "9.0"
    with pytest.raises(TypeError):
        evidence.fact_values["auto.cash.trading"] = 999  # type: ignore[index]
    with pytest.raises(TypeError):
        evidence.sources["auto.cash.trading"] = ("forged",)  # type: ignore[index]


def test_evidence_adapter_separates_physical_from_manual_owned_sell_shares(tmp_path: Path) -> None:
    _write_target(tmp_path)
    path = tmp_path / "runtime" / "live_test_state.json"
    state = json.loads(path.read_text())
    funding = state["manual_funding"]["mixed-token"]
    funding["physical_sold_shares_observed"] = 10.0
    funding["activity_sold_shares"] = 6.0
    fill = state["bot_buy_fills"]["mixed-token"]
    fill["sell_receipt_shares"] = 4.0
    fill["sell_receipt_proceeds"] = 3.6
    fill.pop("mixed_sell_receipt_shares", None)
    fill.pop("mixed_sell_receipt_proceeds", None)
    path.write_text(json.dumps(state), encoding="utf-8")
    evidence = collect_evidence(tmp_path)
    assert evidence.fact_values["auto.position.physical_sell_shares"] == 10.0
    assert evidence.fact_values["auto.position.manual_sell_shares"] == 6.0
    assert evidence.fact_values["auto.position.bot_sold_shares"] == 4.0


def test_positive_unattributed_cash_defers_flat_partition_check(tmp_path: Path) -> None:
    _write_target(tmp_path)
    state_path = tmp_path / "runtime" / "live_test_state.json"
    state = json.loads(state_path.read_text())
    state["account_balance"] = 40.202
    state["cash_inflow_unattributed"] = 20.202
    state["manual_cash_pending"] = 20.202
    state_path.write_text(json.dumps(state), encoding="utf-8")
    evidence = collect_evidence(tmp_path)
    assert evidence.fact_values["auto.capital.flat"] is False


def test_flat_cash_partition_invariant_rejects_phantom_trading_cash(tmp_path: Path) -> None:
    _write_target(tmp_path)
    state_path = tmp_path / "runtime" / "live_test_state.json"
    state = json.loads(state_path.read_text())
    state["safe_account_balance"] = 14.0
    state["trade_account_balance"] = 19.5653
    state["account_balance"] = 20.0
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proof = audit_target(tmp_path).proof
    failed = {check.invariant_id for check in proof.invariant_checks if check.status.value == "fail"}
    assert "auto.inv.flat_cash_partition_conservation" in failed


def test_evidence_adapter_reads_latest_persisted_execution_decision(tmp_path: Path) -> None:
    _write_target(tmp_path)
    state_path = tmp_path / "runtime" / "live_test_state.json"
    state = json.loads(state_path.read_text())
    state["fired_rounds"] = ["round-exec"]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    ledger = tmp_path / "runtime" / "live_test_orders.jsonl"
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": "ORDER_SUBMIT", "signal": {"round_id": "round-exec"}}) + "\n")
    evidence = collect_evidence(tmp_path)
    assert evidence.fact_values["auto.order.already_submitted"] is True
    assert evidence.fact_values["auto.position.bot_same_round"] is False
    assert evidence.fact_values["auto.signal.execution_decision"] == "BUY"


def test_system_audit_uses_invariants_to_reject_contradictory_persisted_ownership(tmp_path: Path) -> None:
    _write_target(tmp_path)
    proof = audit_target(tmp_path).proof
    assert proof.verdict is ProofVerdict.FAIL
    failed = {check.invariant_id for check in proof.invariant_checks if check.status.value == "fail"}
    assert "auto.inv.mixed_sell_share_conservation" in failed
    assert "auto.inv.manual_sell_does_not_exceed_manual_ownership" in failed
    assert proof.repair_contract is not None


def test_malformed_ledger_marks_evidence_incomplete_and_prevents_pass(tmp_path: Path) -> None:
    _write_target(tmp_path)
    ledger = tmp_path / "runtime" / "live_test_orders.jsonl"
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write("{broken json}\n")

    evidence = collect_evidence(tmp_path)
    audit = audit_target(tmp_path)
    assert evidence.complete is False
    assert any("malformed JSON" in warning for warning in evidence.warnings)
    assert audit.proof.verdict is not ProofVerdict.PASS


def test_missing_runtime_evidence_returns_unknown_instead_of_crashing(tmp_path: Path) -> None:
    audit = audit_target(tmp_path)
    assert audit.evidence.complete is False
    assert audit.proof.verdict is ProofVerdict.UNKNOWN
    assert any("is missing" in warning for warning in audit.evidence.warnings)


def test_audit_renderer_makes_incomplete_evidence_and_unknown_visible(tmp_path: Path) -> None:
    audit = audit_target(tmp_path)
    rendered = render_audit(audit)

    assert "Evidence Complete: False" in rendered
    assert "VERDICT: UNKNOWN" in rendered
    assert "EVIDENCE WARNINGS" in rendered
    assert "is missing" in rendered


def test_evidence_snapshot_id_hashes_ledger_contents_not_metadata_only(tmp_path: Path) -> None:
    _write_target(tmp_path)
    ledger = tmp_path / "runtime" / "live_test_orders.jsonl"
    first = collect_evidence(tmp_path)
    stat = ledger.stat()
    original = ledger.read_text(encoding="utf-8")
    changed = original.replace("9.0", "8.0")
    assert len(changed) == len(original)
    ledger.write_text(changed, encoding="utf-8")
    os.utime(ledger, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    second = collect_evidence(tmp_path)
    assert second.snapshot_id != first.snapshot_id


def test_oversized_ledger_line_marks_evidence_incomplete(tmp_path: Path, monkeypatch) -> None:
    from aegis_graph.integrations import auto_trading_evidence

    _write_target(tmp_path)
    monkeypatch.setattr(auto_trading_evidence, "MAX_LEDGER_LINE_BYTES", 32)
    ledger = tmp_path / "runtime" / "live_test_orders.jsonl"
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": "X", "payload": "x" * 100}) + "\n")

    evidence = collect_evidence(tmp_path)
    assert evidence.complete is False
    assert any("safety limit" in warning for warning in evidence.warnings)


def test_malformed_mixed_sell_timestamp_marks_evidence_incomplete_without_crash(
    tmp_path: Path,
) -> None:
    _write_target(tmp_path)
    state_path = tmp_path / "runtime" / "live_test_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["bot_buy_fills"]["mixed-token"]["response_ms"] = "not-a-number"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    audit = audit_target(tmp_path)
    assert audit.evidence.complete is False
    assert audit.proof.verdict is not ProofVerdict.PASS
    assert any("response_ms" in warning for warning in audit.evidence.warnings)


def test_malformed_present_state_fields_are_incomplete_not_defaulted_to_clean(
    tmp_path: Path,
) -> None:
    _write_target(tmp_path)
    state_path = tmp_path / "runtime" / "live_test_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["external_positions"] = ["not-a-mapping"]
    state["cash_inflow_unattributed"] = "not-a-number"
    state["manual_funding_detection_pending"] = "false"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    audit = audit_target(tmp_path)
    assert audit.evidence.complete is False
    assert audit.proof.verdict is not ProofVerdict.PASS
    assert any("external_positions" in warning for warning in audit.evidence.warnings)
    assert any("cash_inflow_unattributed" in warning for warning in audit.evidence.warnings)
    assert any(
        "manual_funding_detection_pending" in warning
        for warning in audit.evidence.warnings
    )


def test_state_change_during_collection_marks_snapshot_incomplete(tmp_path: Path, monkeypatch) -> None:
    from aegis_graph.integrations import auto_trading_evidence

    _write_target(tmp_path)
    state_path = tmp_path / "runtime" / "live_test_state.json"
    original_ledger_rows = auto_trading_evidence._ledger_rows

    def mutate_state_after_state_read(path: Path):
        result = original_ledger_rows(path)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["trade_account_balance"] = 7.0
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return result

    monkeypatch.setattr(auto_trading_evidence, "_ledger_rows", mutate_state_after_state_read)
    evidence = collect_evidence(tmp_path)

    assert evidence.complete is False
    assert evidence.fact_values["auto.cash.trading"] == 6.0
    assert any("state changed during evidence collection" in warning for warning in evidence.warnings)


def test_state_snapshot_id_hashes_exact_bytes_used_for_facts(tmp_path: Path) -> None:
    _write_target(tmp_path)
    first = collect_evidence(tmp_path)
    state_path = tmp_path / "runtime" / "live_test_state.json"
    original = state_path.read_text(encoding="utf-8")
    changed = original.replace('"trade_account_balance": 6.0', '"trade_account_balance": 7.0')
    assert len(changed) == len(original)
    state_path.write_text(changed, encoding="utf-8")

    second = collect_evidence(tmp_path)
    assert first.fact_values["auto.cash.trading"] == 6.0
    assert second.fact_values["auto.cash.trading"] == 7.0
    assert second.snapshot_id != first.snapshot_id
