"""First real AegisGraph reference integration: Trading V2.1 cash-to-BUY chain.

This module is intentionally outside Core. It captures authored business semantics
from a specific reference system and anchors them to observed source code.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

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


REFERENCE_COMMIT = "785b6863953ff9e3f08e04cfdfd2383ce5cb3923"

# Human-readable evidence anchors captured from the reference repository.
# They are intentionally integration metadata, not hard-coded AegisGraph Core logic.
SOURCE_ANCHORS: dict[str, tuple[str, ...]] = {
    "v21.cash.execution_balance": (
        "backend/src/poly5m/execution/buy.py:171-175",
    ),
    "v21.account.snapshot.execution_balance": (
        "backend/src/poly5m/transport/server.py:78-94",
        "frontend/src/stores/domains.ts:9-20",
    ),
    "v21.order.manual_buy_eligibility": (
        "frontend/src/components/AccountPanel/presentation.ts:53-62",
    ),
    "v21.ui.manual_buy_button_enabled": (
        "frontend/src/components/AccountPanel/AccountPanel.tsx:62-85",
    ),
}


def _static_metadata(criticality: Criticality) -> Metadata:
    return Metadata(
        version="1",
        provenance=ConfidenceSource.STATIC,
        confidence=1.0,
        criticality=criticality,
        commit_sha=REFERENCE_COMMIT,
    )


def build_graph() -> SoftwareGraph:
    graph = SoftwareGraph()

    facts = (
        FactNode("v21.clob.available_balance", "CLOB Available Balance", kind="external_source", metadata=_static_metadata(Criticality.CRITICAL)),
        FactNode("v21.cash.execution_balance", "Execution Balance", kind="money", metadata=_static_metadata(Criticality.CRITICAL)),
        FactNode("v21.account.snapshot.execution_balance", "Account Snapshot Execution Balance", kind="transport", metadata=_static_metadata(Criticality.HIGH)),
        FactNode("v21.request.buy_amount", "Requested Buy Amount", kind="money", metadata=_static_metadata(Criticality.HIGH)),
        FactNode("v21.window.latest", "Latest Window Selected", kind="boolean", metadata=_static_metadata(Criticality.MEDIUM)),
        FactNode("v21.backend.connected", "Backend Connected", kind="boolean", metadata=_static_metadata(Criticality.HIGH)),
        FactNode("v21.execution.auth_ready", "Execution Auth Ready", kind="boolean", metadata=_static_metadata(Criticality.CRITICAL)),
        FactNode("v21.market.identity_valid", "Market Identity Valid", kind="boolean", metadata=_static_metadata(Criticality.CRITICAL)),
        FactNode("v21.market.book_executable", "Order Book Executable", kind="boolean", metadata=_static_metadata(Criticality.CRITICAL)),
        FactNode("v21.market.active", "Market Active", kind="boolean", metadata=_static_metadata(Criticality.HIGH)),
        FactNode("v21.order.manual_buy_eligibility", "Manual Buy Eligibility", kind="decision", metadata=_static_metadata(Criticality.CRITICAL)),
        FactNode("v21.ui.manual_buy_button_enabled", "Manual Buy Button Enabled", kind="view", metadata=_static_metadata(Criticality.HIGH)),
    )
    for fact in facts:
        graph.add_fact(fact)

    relationships = (
        Relationship(
            id="v21.rel.execution_balance_from_clob",
            source="v21.cash.execution_balance",
            target="v21.clob.available_balance",
            type=RelationshipType.SOURCE_FROM,
            metadata=_static_metadata(Criticality.CRITICAL),
        ),
        Relationship(
            id="v21.rel.snapshot_from_execution_balance",
            source="v21.account.snapshot.execution_balance",
            target="v21.cash.execution_balance",
            type=RelationshipType.DERIVED_FROM,
            metadata=_static_metadata(Criticality.HIGH),
        ),
        Relationship(
            id="v21.rel_buy_eligibility_needs_balance",
            source="v21.order.manual_buy_eligibility",
            target="v21.account.snapshot.execution_balance",
            type=RelationshipType.DEPENDS_ON,
            metadata=_static_metadata(Criticality.CRITICAL),
        ),
        Relationship(
            id="v21.rel_ui_displays_buy_eligibility",
            source="v21.ui.manual_buy_button_enabled",
            target="v21.order.manual_buy_eligibility",
            type=RelationshipType.DISPLAYS,
            metadata=_static_metadata(Criticality.HIGH),
        ),
    )
    for relationship in relationships:
        graph.add_relationship(relationship)

    graph.add_rule(
        Rule(
            id="v21.rule.manual_buy_eligibility",
            name="Manual BUY eligibility formula",
            inputs=(
                "v21.account.snapshot.execution_balance",
                "v21.request.buy_amount",
                "v21.window.latest",
                "v21.backend.connected",
                "v21.execution.auth_ready",
                "v21.market.identity_valid",
                "v21.market.book_executable",
                "v21.market.active",
            ),
            outputs=("v21.order.manual_buy_eligibility",),
            expression=(
                "latest && backend_connected && auth_ready && amount > 0 && "
                "execution_balance >= amount && identity_valid && book_executable && market_active"
            ),
            metadata=_static_metadata(Criticality.CRITICAL),
        )
    )

    graph.add_invariant(
        Invariant(
            id="v21.inv.execution_balance_is_clob_first",
            name="Execution balance must preserve the authoritative CLOB balance",
            facts=("v21.clob.available_balance", "v21.cash.execution_balance"),
            metadata=_static_metadata(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="v21.inv.manual_buy_gate_matches_inputs",
            name="Manual BUY eligibility must match all execution-readiness inputs",
            facts=(
                "v21.account.snapshot.execution_balance",
                "v21.request.buy_amount",
                "v21.window.latest",
                "v21.backend.connected",
                "v21.execution.auth_ready",
                "v21.market.identity_valid",
                "v21.market.book_executable",
                "v21.market.active",
                "v21.order.manual_buy_eligibility",
            ),
            metadata=_static_metadata(Criticality.CRITICAL),
        )
    )
    graph.add_invariant(
        Invariant(
            id="v21.inv.ui_buy_button_matches_eligibility",
            name="BUY button view must match manual buy eligibility",
            facts=("v21.order.manual_buy_eligibility", "v21.ui.manual_buy_button_enabled"),
            metadata=_static_metadata(Criticality.HIGH),
        )
    )

    return graph


def create_engine() -> AegisEngine:
    engine = AegisEngine(build_graph())
    engine.register_invariant_validator(
        "v21.inv.execution_balance_is_clob_first",
        _validate_clob_first_balance,
    )
    engine.register_invariant_validator(
        "v21.inv.manual_buy_gate_matches_inputs",
        _validate_manual_buy_gate,
    )
    engine.register_invariant_validator(
        "v21.inv.ui_buy_button_matches_eligibility",
        _validate_ui_buy_button,
    )
    return engine


def _money(value: Any) -> Decimal:
    return Decimal(str(value))


def _validate_clob_first_balance(facts: Mapping[str, Any]) -> tuple[bool, str]:
    clob = _money(facts["v21.clob.available_balance"])
    execution = _money(facts["v21.cash.execution_balance"])
    passed = clob == execution
    return passed, f"CLOB={clob} execution_balance={execution}"


def _validate_manual_buy_gate(facts: Mapping[str, Any]) -> tuple[bool, str]:
    balance = _money(facts["v21.account.snapshot.execution_balance"])
    amount = _money(facts["v21.request.buy_amount"])
    expected = (
        bool(facts["v21.window.latest"])
        and bool(facts["v21.backend.connected"])
        and bool(facts["v21.execution.auth_ready"])
        and amount > 0
        and balance >= amount
        and bool(facts["v21.market.identity_valid"])
        and bool(facts["v21.market.book_executable"])
        and bool(facts["v21.market.active"])
    )
    actual = bool(facts["v21.order.manual_buy_eligibility"])
    return expected == actual, f"expected_eligibility={expected} actual={actual} balance={balance} amount={amount}"


def _validate_ui_buy_button(facts: Mapping[str, Any]) -> tuple[bool, str]:
    expected = bool(facts["v21.order.manual_buy_eligibility"])
    actual = bool(facts["v21.ui.manual_buy_button_enabled"])
    return expected == actual, f"eligibility={expected} ui_enabled={actual}"
