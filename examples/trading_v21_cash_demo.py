"""Tiny human-readable demo of the first real AegisGraph integration."""

from aegis_graph.core.models import Change, ChangeType
from aegis_graph.integrations.trading_v21 import create_engine


change = Change(
    id="demo.execution_balance_change",
    type=ChangeType.SOURCE_CHANGE,
    summary="Execution balance source/formula changed",
    changed_fact_ids=("v21.cash.execution_balance",),
)

values = {
    "v21.clob.available_balance": "12.50",
    "v21.cash.execution_balance": "0",
    "v21.account.snapshot.execution_balance": "0",
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

proof = create_engine().analyze(change, fact_values=values)
print(f"VERDICT: {proof.verdict.value.upper()}")
print("AFFECTED PATH:")
for fact_id in proof.impact.paths["v21.ui.manual_buy_button_enabled"].fact_ids:
    print(f"  -> {fact_id}")
print("INVARIANTS:")
for check in proof.invariant_checks:
    print(f"  {check.status.value.upper():7} {check.invariant_id}: {check.message}")
