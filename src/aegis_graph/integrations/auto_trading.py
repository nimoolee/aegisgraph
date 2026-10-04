"""Hand-authored semantics for a sanitized Auto Trading reference benchmark.

This module preserves a real-world verification shape without exposing the original
private target repository, incident identifiers, or source paths. Product discovery
must not use it as an answer key or source of truth; AegisGraph Core remains
domain-agnostic.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from aegis_graph.core.models import (
    ConfidenceSource,
    Criticality,
    FactNode,
    Invariant,
    Metadata,
    Relationship,
    RelationshipType,
    Rule,
)
from aegis_graph.engine import AegisEngine
from aegis_graph.graph.store import SoftwareGraph
from aegis_graph.proof.models import RepairDirective

SOURCE_ANCHORS: dict[str, tuple[str, ...]] = {
    "auto.cash.trading": ("sanitized-reference:capital-ledger/trading",),
    "auto.cash.clob_free": ("sanitized-reference:physical-cash/clob-free",),
    "auto.position.manual_exists": ("sanitized-reference:ownership/manual-position",),
    "auto.signal.execution_decision": ("sanitized-reference:execution/decision",),
    "auto.cash.physical_sell_proceeds": ("sanitized-reference:mixed-sell/physical-receipt",),
    "auto.cash.manual_sell_proceeds": ("sanitized-reference:mixed-sell/manual-attribution",),
    "auto.cash.bot_sell_proceeds": ("sanitized-reference:mixed-sell/bot-attribution",),
    "auto.position.bot_total_shares": ("sanitized-reference:bot-fill/owned-shares",),
    "auto.position.bot_sold_shares": ("sanitized-reference:mixed-sell/bot-owned-shares",),
    "auto.settlement.expected_redeem_shares": ("sanitized-reference:settlement/expected-redeem",),
}


def _static(criticality: Criticality) -> Metadata:
    return Metadata(
        provenance=ConfidenceSource.STATIC,
        confidence=1.0,
        criticality=criticality,
    )


def build_graph() -> SoftwareGraph:
    graph = SoftwareGraph()
    for fact in (
        FactNode("auto.cash.trading", "Automatic Strategy Trading Cash", kind="money", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.cash.clob_free", "Physical CLOB Free Cash", kind="money", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.cash.safety", "Safety Cash Ledger", kind="money", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.capital.flat", "No Live Position Or Settlement Owns Cash", kind="boolean", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.capital.sweep_formula_valid", "Recorded Safety Sweeps Obey Doubling Formula", kind="boolean", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.capital.sweep_count", "Recorded Safety Sweep Count", kind="count", metadata=_static(Criticality.HIGH)),
        FactNode("auto.cash.orderable", "Orderable Automatic Cash", kind="money", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.order.minimum", "Minimum Executable Order", kind="money", metadata=_static(Criticality.HIGH)),
        FactNode("auto.position.manual_exists", "Manual Position Exists", kind="boolean", metadata=_static(Criticality.HIGH)),
        FactNode("auto.position.bot_same_round", "Bot Position Exists For Same Round", kind="boolean", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.order.already_submitted", "Bot Order Already Submitted", kind="boolean", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.signal.execution_decision", "Automatic Signal Execution Decision", kind="decision", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.cash.physical_sell_proceeds", "Physical Wallet SELL Proceeds", kind="money", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.cash.manual_sell_proceeds", "Manual-Owned SELL Proceeds", kind="money", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.cash.bot_sell_proceeds", "Bot-Owned SELL Proceeds", kind="money", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.cash.unknown_sell_proceeds", "Unknown SELL Proceeds", kind="money", metadata=_static(Criticality.HIGH)),
        FactNode("auto.position.physical_sell_shares", "Physical Wallet SELL Shares", kind="shares", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.position.manual_sell_shares", "Manual-Owned SELL Shares", kind="shares", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.position.manual_total_shares", "Manual Shares Before Mixed SELL", kind="shares", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.position.bot_total_shares", "Bot Shares Before Mixed SELL", kind="shares", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.position.bot_sold_shares", "Bot Shares Consumed By Mixed SELL", kind="shares", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.position.unknown_sell_shares", "Unknown SELL Shares", kind="shares", metadata=_static(Criticality.HIGH)),
        FactNode("auto.settlement.expected_redeem_shares", "Bot Shares Still Expected To REDEEM", kind="shares", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.settlement.pending", "Settlement Cash Sync Pending", kind="boolean", metadata=_static(Criticality.CRITICAL)),
        FactNode("auto.settlement.mixed_sell_verified", "Mixed SELL Receipt Verified", kind="boolean", metadata=_static(Criticality.CRITICAL)),
    ):
        graph.add_fact(fact)

    for relationship in (
        Relationship(
            id="auto.rel.orderable_depends_on_trading_cash",
            source="auto.cash.orderable",
            target="auto.cash.trading",
            type=RelationshipType.DEPENDS_ON,
            metadata=_static(Criticality.CRITICAL),
        ),
        Relationship(
            id="auto.rel.orderable_depends_on_clob_cash",
            source="auto.cash.orderable",
            target="auto.cash.clob_free",
            type=RelationshipType.DEPENDS_ON,
            metadata=_static(Criticality.CRITICAL),
        ),
        Relationship(
            id="auto.rel_decision_depends_on_orderable",
            source="auto.signal.execution_decision",
            target="auto.cash.orderable",
            type=RelationshipType.DEPENDS_ON,
            metadata=_static(Criticality.CRITICAL),
        ),
        Relationship(
            id="auto.rel_manual_position_independent_of_entry",
            source="auto.position.manual_exists",
            target="auto.signal.execution_decision",
            type=RelationshipType.INDEPENDENT_OF,
            metadata=_static(Criticality.CRITICAL),
        ),
    ):
        graph.add_relationship(relationship)

    for relationship in (
        Relationship(
            id="auto.rel_manual_sell_proceeds_derived_from_physical_sell",
            source="auto.cash.manual_sell_proceeds",
            target="auto.cash.physical_sell_proceeds",
            type=RelationshipType.DERIVED_FROM,
            metadata=_static(Criticality.CRITICAL),
        ),
        Relationship(
            id="auto.rel_bot_sell_proceeds_derived_from_physical_sell",
            source="auto.cash.bot_sell_proceeds",
            target="auto.cash.physical_sell_proceeds",
            type=RelationshipType.DERIVED_FROM,
            metadata=_static(Criticality.CRITICAL),
        ),
        Relationship(
            id="auto.rel_unknown_sell_proceeds_derived_from_physical_sell",
            source="auto.cash.unknown_sell_proceeds",
            target="auto.cash.physical_sell_proceeds",
            type=RelationshipType.DERIVED_FROM,
            metadata=_static(Criticality.HIGH),
        ),
        Relationship(
            id="auto.rel_expected_redeem_depends_on_bot_sold",
            source="auto.settlement.expected_redeem_shares",
            target="auto.position.bot_sold_shares",
            type=RelationshipType.DEPENDS_ON,
            metadata=_static(Criticality.CRITICAL),
        ),
    ):
        graph.add_relationship(relationship)

    graph.add_rule(
        Rule(
            id="auto.rule.signal_execution_decision",
            name="Automatic signal execution gate",
            inputs=(
                "auto.cash.trading",
                "auto.cash.clob_free",
                "auto.cash.orderable",
                "auto.order.minimum",
                "auto.position.bot_same_round",
                "auto.order.already_submitted",
            ),
            outputs=("auto.signal.execution_decision",),
            expression=(
                "bot_same_round/already_submitted => COVERED; otherwise orderable >= minimum => BUY; "
                "low trading/clob cash => explicit BLOCKED reason"
            ),
            metadata=_static(Criticality.CRITICAL),
        )
    )

    graph.add_invariant(
        Invariant(
            id="auto.inv.manual_position_never_vetoes_signal",
            name="Manual positions must not veto an otherwise executable automatic signal",
            facts=(
                "auto.position.manual_exists",
                "auto.cash.orderable",
                "auto.order.minimum",
                "auto.position.bot_same_round",
                "auto.order.already_submitted",
                "auto.signal.execution_decision",
            ),
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="auto.inv.orderable_respects_cash",
            name="Automatic orderable cash cannot exceed Trading or physical CLOB cash",
            facts=("auto.cash.trading", "auto.cash.clob_free", "auto.cash.orderable", "auto.order.minimum"),
            expression="orderable = min(trading_cash, clob_free_cash) when that minimum >= minimum_order; otherwise 0",
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="auto.inv.flat_cash_partition_conservation",
            name="At a flat capital boundary physical CLOB cash must equal Safety plus Trading",
            facts=("auto.capital.flat", "auto.cash.clob_free", "auto.cash.safety", "auto.cash.trading"),
            expression="capital_flat => clob_free_cash = safety_cash + trading_cash",
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="auto.inv.safety_sweep_obeys_doubling_formula",
            name="Every recorded Safety sweep must obey the accepted Trading doubling formula",
            facts=("auto.capital.sweep_formula_valid", "auto.capital.sweep_count"),
            expression="every SAFETY_SWEEP: trade_before >= 2*baseline_before; moved=floor(trade_before/2,0.01); baseline_after=trade_after; next_target=2*baseline_after",
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="auto.inv.low_trading_cash_blocks_explicitly",
            name="True low Trading Cash must produce the explicit low-cash block reason",
            facts=(
                "auto.cash.trading",
                "auto.cash.orderable",
                "auto.order.minimum",
                "auto.position.bot_same_round",
                "auto.order.already_submitted",
                "auto.signal.execution_decision",
            ),
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_rule(
        Rule(
            id="auto.rule.mixed_sell_partition",
            name="Partition one physical same-token SELL into manual, bot and unknown ownership",
            inputs=(
                "auto.cash.physical_sell_proceeds",
                "auto.position.physical_sell_shares",
                "auto.position.manual_sell_shares",
                "auto.position.bot_total_shares",
                "auto.position.bot_sold_shares",
            ),
            outputs=(
                "auto.cash.manual_sell_proceeds",
                "auto.cash.bot_sell_proceeds",
                "auto.cash.unknown_sell_proceeds",
                "auto.position.unknown_sell_shares",
                "auto.settlement.expected_redeem_shares",
            ),
            expression="physical SELL is partitioned exactly once by ownership; sold bot shares are removed from future REDEEM",
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="auto.inv.mixed_sell_cash_conservation",
            name="Physical SELL proceeds must equal manual + bot + unknown attributed proceeds",
            facts=(
                "auto.cash.physical_sell_proceeds",
                "auto.cash.manual_sell_proceeds",
                "auto.cash.bot_sell_proceeds",
                "auto.cash.unknown_sell_proceeds",
            ),
            expression="physical_sell_proceeds = manual_sell_proceeds + bot_sell_proceeds + unknown_sell_proceeds",
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="auto.inv.mixed_sell_share_conservation",
            name="Physical SELL shares must equal manual + bot + unknown owned shares",
            facts=(
                "auto.position.physical_sell_shares",
                "auto.position.manual_sell_shares",
                "auto.position.bot_sold_shares",
                "auto.position.unknown_sell_shares",
            ),
            expression="physical_sell_shares = manual_sell_shares + bot_sold_shares + unknown_sell_shares",
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="auto.inv.manual_sell_does_not_exceed_manual_ownership",
            name="Manual-attributed sold shares cannot exceed manual-owned shares",
            facts=(
                "auto.position.manual_total_shares",
                "auto.position.manual_sell_shares",
            ),
            expression="manual_sell_shares <= manual_total_shares",
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="auto.inv.sold_bot_shares_not_waiting_redeem",
            name="Bot shares already consumed by a mixed SELL must not remain in expected REDEEM",
            facts=(
                "auto.position.bot_total_shares",
                "auto.position.bot_sold_shares",
                "auto.settlement.expected_redeem_shares",
            ),
            expression="expected_redeem_shares <= max(0, bot_total_shares - bot_sold_shares)",
            metadata=_static(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="auto.inv.verified_zero_redeem_not_stuck_pending",
            name="A verified mixed SELL with zero remaining REDEEM cannot stay settlement-pending",
            facts=(
                "auto.settlement.mixed_sell_verified",
                "auto.settlement.expected_redeem_shares",
                "auto.settlement.pending",
            ),
            expression="mixed_sell_verified and expected_redeem_shares == 0 => settlement_pending == false",
            metadata=_static(Criticality.CRITICAL),
        )
    )
    return graph


def create_engine() -> AegisEngine:
    engine = AegisEngine(build_graph())
    engine.register_invariant_validator("auto.inv.manual_position_never_vetoes_signal", _manual_position_never_vetoes)
    engine.register_invariant_validator("auto.inv.orderable_respects_cash", _orderable_respects_cash)
    engine.register_invariant_validator("auto.inv.flat_cash_partition_conservation", _flat_cash_partition_conservation)
    engine.register_invariant_validator("auto.inv.safety_sweep_obeys_doubling_formula", _safety_sweep_obeys_doubling_formula)
    engine.register_invariant_validator("auto.inv.low_trading_cash_blocks_explicitly", _low_trading_cash_blocks)
    engine.register_invariant_validator("auto.inv.mixed_sell_cash_conservation", _mixed_sell_cash_conservation)
    engine.register_invariant_validator("auto.inv.mixed_sell_share_conservation", _mixed_sell_share_conservation)
    engine.register_invariant_validator("auto.inv.manual_sell_does_not_exceed_manual_ownership", _manual_sell_does_not_exceed_manual_ownership)
    engine.register_invariant_validator("auto.inv.sold_bot_shares_not_waiting_redeem", _sold_bot_shares_not_waiting_redeem)
    engine.register_invariant_validator("auto.inv.verified_zero_redeem_not_stuck_pending", _verified_zero_redeem_not_stuck_pending)
    engine.register_repair_directive(RepairDirective(
        invariant_id="auto.inv.flat_cash_partition_conservation",
        must_change=("Remove any duplicated or missing cash attribution so a flat wallet has exactly one Safety+Trading partition of physical CLOB cash.",),
        must_preserve=("Keep physical CLOB cash as observed evidence and preserve independent Safety/Trading ownership semantics.",),
        must_not_change=("Do not force equality by reconstructing Trading as CLOB cash minus Safety or by discarding an unexplained receipt.",),
        required_verification=("Replay the causal receipt sequence, then verify the flat cash partition at the next clean boundary.",),
        required_evidence=("Physical CLOB cash", "Safety ledger", "Trading ledger", "Receipt/settlement attribution history"),
    ))
    engine.register_repair_directive(RepairDirective(
        invariant_id="auto.inv.mixed_sell_cash_conservation",
        must_change=("Partition one physical same-token SELL so manual, bot and unknown proceeds account for the receipt exactly once.",),
        must_preserve=("Keep physical CLOB cash as observed evidence; do not reconstruct it from logical ledgers.",),
        must_not_change=("Do not discard unmatched SELL proceeds or credit the same proceeds to more than one logical owner.",),
        required_verification=("Replay a mixed manual+bot same-token SELL and re-check cash conservation.",),
        required_evidence=("Physical SELL receipt", "Manual ownership before SELL", "Bot fill ownership before SELL"),
    ))
    engine.register_repair_directive(RepairDirective(
        invariant_id="auto.inv.manual_sell_does_not_exceed_manual_ownership",
        must_change=("Manual-attributed sold shares must be capped by actual manual-owned shares; any excess needs a separate owner or UNKNOWN attribution.",),
        must_preserve=("Manual and automatic ownership remain logically separate even when the wallet physically merges the token balance.",),
        must_not_change=("Do not rewrite the observed physical SELL size to hide an ownership overflow.",),
        required_verification=("Replay the historical mixed-token SELL and verify manual sold shares never exceed manual ownership.",),
        required_evidence=("Manual BUY share history", "Physical SELL share receipt"),
    ))
    engine.register_repair_directive(RepairDirective(
        invariant_id="auto.inv.sold_bot_shares_not_waiting_redeem",
        must_change=("Any bot-owned shares already consumed by a SELL must be removed from the future REDEEM entitlement.",),
        must_preserve=("Bot cost basis and realized proceeds remain auditable across SELL and settlement states.",),
        must_not_change=("Do not clear settlement with a timeout while the ownership contradiction remains unresolved.",),
        required_verification=("Replay SELL-before-REDEEM and SELL-receipt-after-settlement event orders.",),
        required_evidence=("Bot fill shares", "SELL receipt shares", "Settlement expected payout/redeem shares"),
    ))
    engine.register_repair_directive(RepairDirective(
        invariant_id="auto.inv.verified_zero_redeem_not_stuck_pending",
        must_change=("A verified zero-remaining-REDEEM state must transition out of settlement-pending through the normal state machine.",),
        must_preserve=("Settlement completion still requires verified ownership/evidence rather than a wall-clock shortcut.",),
        must_not_change=("Do not add an unconditional timeout that converts unresolved settlement into PASS.",),
        required_verification=("Verify the zero-redeem terminal transition and subsequent automatic-order eligibility.",),
        required_evidence=("Verified mixed SELL attribution", "Remaining REDEEM entitlement", "Settlement state transition"),
    ))
    return engine


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _manual_position_never_vetoes(facts: Mapping[str, Any]) -> tuple[bool, str]:
    orderable = _d(facts["auto.cash.orderable"])
    minimum = _d(facts["auto.order.minimum"])
    bot_covered = bool(facts["auto.position.bot_same_round"]) or bool(facts["auto.order.already_submitted"])
    decision = str(facts["auto.signal.execution_decision"])
    if orderable >= minimum and not bot_covered:
        passed = decision == "BUY"
        return passed, f"manual_exists={bool(facts['auto.position.manual_exists'])} orderable={orderable} decision={decision}"
    return True, "manual-position independence not challenged by this evidence row"


def _orderable_respects_cash(facts: Mapping[str, Any]) -> tuple[bool, str]:
    trading = max(Decimal("0"), _d(facts["auto.cash.trading"]))
    clob = max(Decimal("0"), _d(facts["auto.cash.clob_free"]))
    orderable = max(Decimal("0"), _d(facts["auto.cash.orderable"]))
    minimum = _d(facts["auto.order.minimum"])
    ceiling = min(trading, clob)
    expected = ceiling if ceiling >= minimum else Decimal("0")
    return orderable == expected, f"trading={trading} clob={clob} expected_orderable={expected} actual={orderable}"


def _flat_cash_partition_conservation(facts: Mapping[str, Any]) -> tuple[bool, str]:
    flat = bool(facts["auto.capital.flat"])
    if not flat:
        return True, "capital partition deferred while a live position/settlement owns cash"
    clob = max(Decimal("0"), _d(facts["auto.cash.clob_free"]))
    safety = max(Decimal("0"), _d(facts["auto.cash.safety"]))
    trading = max(Decimal("0"), _d(facts["auto.cash.trading"]))
    gap = clob - safety - trading
    passed = abs(gap) <= MONEY_TOLERANCE
    return passed, f"clob={clob} safety={safety} trading={trading} gap={gap}"


def _safety_sweep_obeys_doubling_formula(facts: Mapping[str, Any]) -> tuple[bool, str]:
    valid = bool(facts["auto.capital.sweep_formula_valid"])
    count = int(facts["auto.capital.sweep_count"])
    return valid, f"recorded_sweeps={count} formula_valid={valid}"


def _low_trading_cash_blocks(facts: Mapping[str, Any]) -> tuple[bool, str]:
    trading = max(Decimal("0"), _d(facts["auto.cash.trading"]))
    orderable = max(Decimal("0"), _d(facts["auto.cash.orderable"]))
    minimum = _d(facts["auto.order.minimum"])
    bot_covered = bool(facts["auto.position.bot_same_round"]) or bool(facts["auto.order.already_submitted"])
    decision = str(facts["auto.signal.execution_decision"])
    if not bot_covered and orderable < minimum and trading < minimum:
        expected = "BLOCKED:TRADING_CASH_BELOW_MINIMUM"
        return decision == expected, f"expected={expected} actual={decision} trading={trading}"
    return True, "low-Trading-Cash branch not active for this evidence row"

MONEY_TOLERANCE = Decimal("0.00001")
SHARE_TOLERANCE = Decimal("0.00001")


def _mixed_sell_cash_conservation(facts: Mapping[str, Any]) -> tuple[bool, str]:
    physical = max(Decimal("0"), _d(facts["auto.cash.physical_sell_proceeds"]))
    manual = max(Decimal("0"), _d(facts["auto.cash.manual_sell_proceeds"]))
    bot = max(Decimal("0"), _d(facts["auto.cash.bot_sell_proceeds"]))
    unknown = max(Decimal("0"), _d(facts["auto.cash.unknown_sell_proceeds"]))
    attributed = manual + bot + unknown
    passed = abs(physical - attributed) <= MONEY_TOLERANCE
    return passed, f"physical={physical} manual={manual} bot={bot} unknown={unknown} gap={physical-attributed}"


def _mixed_sell_share_conservation(facts: Mapping[str, Any]) -> tuple[bool, str]:
    physical = max(Decimal("0"), _d(facts["auto.position.physical_sell_shares"]))
    manual = max(Decimal("0"), _d(facts["auto.position.manual_sell_shares"]))
    bot = max(Decimal("0"), _d(facts["auto.position.bot_sold_shares"]))
    unknown = max(Decimal("0"), _d(facts["auto.position.unknown_sell_shares"]))
    attributed = manual + bot + unknown
    passed = abs(physical - attributed) <= SHARE_TOLERANCE
    return passed, f"physical={physical} manual={manual} bot={bot} unknown={unknown} gap={physical-attributed}"


def _manual_sell_does_not_exceed_manual_ownership(facts: Mapping[str, Any]) -> tuple[bool, str]:
    total = max(Decimal("0"), _d(facts["auto.position.manual_total_shares"]))
    sold = max(Decimal("0"), _d(facts["auto.position.manual_sell_shares"]))
    passed = sold <= total + SHARE_TOLERANCE
    return passed, f"manual_total={total} manual_sold={sold} excess={max(Decimal('0'), sold-total)}"


def _sold_bot_shares_not_waiting_redeem(facts: Mapping[str, Any]) -> tuple[bool, str]:
    total = max(Decimal("0"), _d(facts["auto.position.bot_total_shares"]))
    sold = max(Decimal("0"), _d(facts["auto.position.bot_sold_shares"]))
    expected_redeem = max(Decimal("0"), _d(facts["auto.settlement.expected_redeem_shares"]))
    maximum_remaining = max(Decimal("0"), total - sold)
    passed = expected_redeem <= maximum_remaining + SHARE_TOLERANCE
    return passed, f"bot_total={total} bot_sold={sold} max_redeem={maximum_remaining} expected_redeem={expected_redeem}"


def _verified_zero_redeem_not_stuck_pending(facts: Mapping[str, Any]) -> tuple[bool, str]:
    verified = bool(facts["auto.settlement.mixed_sell_verified"])
    expected_redeem = max(Decimal("0"), _d(facts["auto.settlement.expected_redeem_shares"]))
    pending = bool(facts["auto.settlement.pending"])
    if verified and expected_redeem <= SHARE_TOLERANCE:
        return not pending, f"verified={verified} expected_redeem={expected_redeem} pending={pending}"
    return True, "zero-redeem verified mixed-SELL branch not active"
