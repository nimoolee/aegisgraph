from aegis_graph.core.models import Change, ChangeType
from aegis_graph.integrations.auto_trading import create_engine
from aegis_graph.proof.models import ProofVerdict


def base_values() -> dict[str, object]:
    return {
        "auto.cash.trading": "6.00",
        "auto.cash.clob_free": "20.00",
        "auto.cash.safety": "14.00",
        "auto.capital.flat": False,
        "auto.cash.orderable": "6.00",
        "auto.order.minimum": "5.00",
        "auto.position.manual_exists": True,
        "auto.position.bot_same_round": False,
        "auto.order.already_submitted": False,
        "auto.signal.execution_decision": "BUY",
    }


def mixed_incident_values(*, fixed: bool) -> dict[str, object]:
    values = base_values()
    values.update({
        "auto.cash.physical_sell_proceeds": "41.03646",
        "auto.position.physical_sell_shares": "41.48",
        "auto.position.manual_total_shares": "31.715203",
        "auto.position.bot_total_shares": "9.7676",
        "auto.settlement.mixed_sell_verified": True,
        "auto.settlement.pending": True,
    })
    if fixed:
        values.update({
            "auto.cash.manual_sell_proceeds": "31.37607664660993",
            "auto.cash.bot_sell_proceeds": "9.66038335339007",
            "auto.cash.unknown_sell_proceeds": "0",
            "auto.position.manual_sell_shares": "31.715203",
            "auto.position.bot_sold_shares": "9.764797",
            "auto.position.unknown_sell_shares": "0",
            "auto.settlement.expected_redeem_shares": "0.002803",
        })
    else:
        # Historical broken behavior: the whole physical SELL was counted as
        # manual shares, the bot proceeds vanished from logical ownership, and
        # the full bot lot remained waiting for REDEEM.
        values.update({
            "auto.cash.manual_sell_proceeds": "31.37607664660993",
            "auto.cash.bot_sell_proceeds": "0",
            "auto.cash.unknown_sell_proceeds": "0",
            "auto.position.manual_sell_shares": "41.48",
            "auto.position.bot_sold_shares": "0",
            "auto.position.unknown_sell_shares": "0",
            "auto.settlement.expected_redeem_shares": "9.7676",
        })
    return values


def test_manual_position_is_modeled_as_non_propagating_independence_constraint() -> None:
    engine = create_engine()
    proof = engine.analyze(
        Change(
            id="auto.change.manual_position",
            type=ChangeType.NODE_CHANGE,
            summary="Manual position semantics changed",
            changed_fact_ids=("auto.position.manual_exists",),
        ),
        fact_values=base_values(),
    )

    assert proof.verdict is ProofVerdict.PASS
    # INDEPENDENT_OF does not claim the execution decision itself changed.
    assert proof.impact.affected_fact_ids == ("auto.position.manual_exists",)
    assert proof.impact.affected_invariant_ids == ("auto.inv.manual_position_never_vetoes_signal",)


def test_trading_cash_change_propagates_to_orderable_and_signal_decision() -> None:
    engine = create_engine()
    proof = engine.analyze(
        Change(
            id="auto.change.trading_cash",
            type=ChangeType.NODE_CHANGE,
            summary="Trading cash changed",
            changed_fact_ids=("auto.cash.trading",),
        ),
        fact_values=base_values(),
    )

    assert proof.verdict is ProofVerdict.PASS
    decision_paths = {
        path.fact_ids for path in proof.impact.paths_for("auto.signal.execution_decision")
    }
    assert (
        "auto.cash.trading",
        "auto.cash.orderable",
        "auto.signal.execution_decision",
    ) in decision_paths
    assert (
        "auto.cash.trading",
        "auto.signal.execution_decision",
    ) in decision_paths


def test_manual_position_regression_is_detected() -> None:
    values = base_values()
    values["auto.signal.execution_decision"] = "BLOCKED:MANUAL_POSITION_EXISTS"

    proof = create_engine().analyze(
        Change(
            id="auto.change.manual_regression",
            type=ChangeType.NODE_CHANGE,
            summary="Manual position accidentally starts blocking the bot",
            changed_fact_ids=("auto.position.manual_exists",),
        ),
        fact_values=values,
    )

    assert proof.verdict is ProofVerdict.FAIL
    assert proof.invariant_checks[0].invariant_id == "auto.inv.manual_position_never_vetoes_signal"


def test_true_low_trading_cash_requires_explicit_reason() -> None:
    values = base_values()
    values.update({
        "auto.cash.trading": "4.99",
        "auto.cash.orderable": "0",
        "auto.signal.execution_decision": "BLOCKED:TRADING_CASH_BELOW_MINIMUM",
    })
    proof = create_engine().analyze(
        Change(
            id="auto.change.low_cash",
            type=ChangeType.NODE_CHANGE,
            summary="Trading cash falls below minimum",
            changed_fact_ids=("auto.cash.trading",),
        ),
        fact_values=values,
    )
    assert proof.verdict is ProofVerdict.PASS


def test_real_mixed_lot_incident_fails_change_proof_before_fix() -> None:
    proof = create_engine().analyze(
        Change(
            id="auto.incident.mixed_same_token_sell.before_fix",
            type=ChangeType.NODE_CHANGE,
            summary="Physical same-token SELL was attributed entirely to manual ownership",
            changed_fact_ids=(
                "auto.cash.physical_sell_proceeds",
                "auto.position.manual_sell_shares",
                "auto.position.bot_sold_shares",
            ),
        ),
        fact_values=mixed_incident_values(fixed=False),
    )
    assert proof.verdict is ProofVerdict.FAIL
    failed = {row.invariant_id for row in proof.invariant_checks if row.status.value == "fail"}
    assert "auto.inv.mixed_sell_cash_conservation" in failed
    assert "auto.inv.manual_sell_does_not_exceed_manual_ownership" in failed
    assert proof.repair_contract is not None
    assert "auto.inv.mixed_sell_cash_conservation" in proof.repair_contract.violated_invariant_ids
    assert any("physical same-token SELL" in item for item in proof.repair_contract.must_change)
    assert any("Do not disable" in item for item in proof.repair_contract.must_not_change)
    assert any("Physical SELL receipt" in item for item in proof.repair_contract.required_evidence)


def test_real_mixed_lot_incident_passes_after_ownership_partition_fix() -> None:
    proof = create_engine().analyze(
        Change(
            id="auto.incident.mixed_same_token_sell.after_fix",
            type=ChangeType.NODE_CHANGE,
            summary="Split one physical SELL by manual and bot ownership",
            changed_fact_ids=(
                "auto.cash.physical_sell_proceeds",
                "auto.position.manual_sell_shares",
                "auto.position.bot_sold_shares",
            ),
        ),
        fact_values=mixed_incident_values(fixed=True),
    )
    assert proof.verdict is ProofVerdict.PASS
    assert proof.repair_contract is None


def test_verified_full_bot_sell_cannot_remain_settlement_pending() -> None:
    values = mixed_incident_values(fixed=True)
    values.update({
        "auto.position.bot_sold_shares": "9.7676",
        "auto.settlement.expected_redeem_shares": "0",
        "auto.settlement.pending": True,
    })
    # Keep share conservation exact by moving the tiny remainder out of manual.
    values["auto.position.manual_sell_shares"] = "31.7124"
    values["auto.position.manual_total_shares"] = "31.715203"
    proof = create_engine().analyze(
        Change(
            id="auto.incident.verified_zero_redeem_stuck",
            type=ChangeType.NODE_CHANGE,
            summary="All bot shares were sold but settlement remained pending",
            changed_fact_ids=("auto.settlement.expected_redeem_shares", "auto.settlement.pending"),
        ),
        fact_values=values,
    )
    assert proof.verdict is ProofVerdict.FAIL
    assert any(
        row.invariant_id == "auto.inv.verified_zero_redeem_not_stuck_pending"
        and row.status.value == "fail"
        for row in proof.invariant_checks
    )
