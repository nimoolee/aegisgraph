"""Replay the confirmed same-token manual+bot SELL ownership incident."""

from aegis_graph.core.models import Change, ChangeType
from aegis_graph.integrations.auto_trading import create_engine


PHYSICAL_PROCEEDS = "41.03646"
MANUAL_PROCEEDS = "31.37607664660993"
BOT_PROCEEDS = "9.66038335339007"
PHYSICAL_SHARES = "41.48"
MANUAL_TOTAL_SHARES = "31.715203"
BOT_TOTAL_SHARES = "9.7676"
BOT_SOLD_SHARES = "9.764797"
BOT_REDEEM_DUST = "0.002803"


def row(*, candidate_repair: bool) -> dict[str, object]:
    values: dict[str, object] = {
        "auto.cash.trading": "3.6134716466099324",
        "auto.cash.clob_free": "104.527332",
        "auto.cash.orderable": "0",
        "auto.order.minimum": "5",
        "auto.position.manual_exists": False,
        "auto.position.bot_same_round": False,
        "auto.order.already_submitted": False,
        "auto.signal.execution_decision": "BLOCKED:TRADING_CASH_BELOW_MINIMUM",
        "auto.cash.physical_sell_proceeds": PHYSICAL_PROCEEDS,
        "auto.position.physical_sell_shares": PHYSICAL_SHARES,
        "auto.position.manual_total_shares": MANUAL_TOTAL_SHARES,
        "auto.position.bot_total_shares": BOT_TOTAL_SHARES,
        "auto.settlement.mixed_sell_verified": True,
        "auto.settlement.pending": True,
    }
    if candidate_repair:
        values.update({
            "auto.cash.manual_sell_proceeds": MANUAL_PROCEEDS,
            "auto.cash.bot_sell_proceeds": BOT_PROCEEDS,
            "auto.cash.unknown_sell_proceeds": "0",
            "auto.position.manual_sell_shares": MANUAL_TOTAL_SHARES,
            "auto.position.bot_sold_shares": BOT_SOLD_SHARES,
            "auto.position.unknown_sell_shares": "0",
            "auto.settlement.expected_redeem_shares": BOT_REDEEM_DUST,
        })
    else:
        values.update({
            "auto.cash.manual_sell_proceeds": MANUAL_PROCEEDS,
            "auto.cash.bot_sell_proceeds": "0",
            "auto.cash.unknown_sell_proceeds": "0",
            "auto.position.manual_sell_shares": PHYSICAL_SHARES,
            "auto.position.bot_sold_shares": "0",
            "auto.position.unknown_sell_shares": "0",
            "auto.settlement.expected_redeem_shares": BOT_TOTAL_SHARES,
        })
    return values


def show(label: str, *, candidate_repair: bool) -> None:
    proof = create_engine().analyze(
        Change(
            id=f"demo.{label.lower()}",
            type=ChangeType.NODE_CHANGE,
            summary=label,
            changed_fact_ids=(
                "auto.cash.physical_sell_proceeds",
                "auto.position.manual_sell_shares",
                "auto.position.bot_sold_shares",
            ),
        ),
        fact_values=row(candidate_repair=candidate_repair),
    )
    print(f"\n=== {label} ===")
    print("VERDICT:", proof.verdict.value.upper())
    for check in proof.invariant_checks:
        print(f"{check.status.value.upper():7} {check.invariant_id}: {check.message}")
    if proof.repair_contract:
        contract = proof.repair_contract
        print("\nREPAIR CONTRACT")
        for title, values in (
            ("Must Change", contract.must_change),
            ("Must Preserve", contract.must_preserve),
            ("Must Not Change", contract.must_not_change),
            ("Required Verification", contract.required_verification),
            ("Required Evidence", contract.required_evidence),
        ):
            print(f"{title}:")
            for value in values:
                print(f"  - {value}")


if __name__ == "__main__":
    show("OBSERVED FAILURE", candidate_repair=False)
    show("CANDIDATE EVIDENCE RE-VERIFICATION", candidate_repair=True)
