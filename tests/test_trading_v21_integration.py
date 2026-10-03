from aegis_graph.core.models import Change, ChangeType
from aegis_graph.integrations.trading_v21 import create_engine
from aegis_graph.proof.models import ProofVerdict


def healthy_values() -> dict[str, object]:
    return {
        "v21.clob.available_balance": "12.50",
        "v21.cash.execution_balance": "12.50",
        "v21.account.snapshot.execution_balance": "12.50",
        "v21.request.buy_amount": "5.00",
        "v21.window.latest": True,
        "v21.backend.connected": True,
        "v21.execution.auth_ready": True,
        "v21.market.identity_valid": True,
        "v21.market.book_executable": True,
        "v21.market.active": True,
        "v21.order.manual_buy_eligibility": True,
        "v21.ui.manual_buy_button_enabled": True,
    }


def execution_balance_change() -> Change:
    return Change(
        id="v21.change.execution_balance",
        type=ChangeType.SOURCE_CHANGE,
        summary="Execution balance source/formula changed",
        changed_fact_ids=("v21.cash.execution_balance",),
    )


def test_real_v21_cash_chain_produces_pass_with_consistent_evidence() -> None:
    proof = create_engine().analyze(execution_balance_change(), fact_values=healthy_values())

    assert proof.verdict is ProofVerdict.PASS
    assert proof.impact.affected_fact_ids == (
        "v21.account.snapshot.execution_balance",
        "v21.cash.execution_balance",
        "v21.order.manual_buy_eligibility",
        "v21.ui.manual_buy_button_enabled",
    )
    assert proof.impact.paths["v21.ui.manual_buy_button_enabled"].fact_ids == (
        "v21.cash.execution_balance",
        "v21.account.snapshot.execution_balance",
        "v21.order.manual_buy_eligibility",
        "v21.ui.manual_buy_button_enabled",
    )


def test_real_v21_cash_chain_fails_when_balance_change_breaks_downstream_truth() -> None:
    values = healthy_values()
    values["v21.cash.execution_balance"] = "0"
    values["v21.account.snapshot.execution_balance"] = "0"
    # Simulate a downstream UI/eligibility state that incorrectly remained enabled.
    values["v21.order.manual_buy_eligibility"] = True
    values["v21.ui.manual_buy_button_enabled"] = True

    proof = create_engine().analyze(execution_balance_change(), fact_values=values)

    assert proof.verdict is ProofVerdict.FAIL
    failures = {check.invariant_id for check in proof.invariant_checks if check.status.value == "fail"}
    assert "v21.inv.execution_balance_is_clob_first" in failures
    assert "v21.inv.manual_buy_gate_matches_inputs" in failures
