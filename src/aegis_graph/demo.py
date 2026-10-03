"""Small product-generic proof demo used by the public CLI and docs."""

from __future__ import annotations

from aegis_graph.core.models import Change, ChangeType, FactNode, Invariant
from aegis_graph.engine import AegisEngine
from aegis_graph.graph.store import SoftwareGraph
from aegis_graph.proof.models import ChangeProof, RepairDirective


def build_demo_engine() -> AegisEngine:
    graph = SoftwareGraph()
    graph.add_fact(FactNode("payments.refund_path", "Refund execution path", kind="architecture"))
    graph.add_invariant(
        Invariant(
            id="payments.inv.refunds_use_gateway",
            name="Refunds must go through PaymentGateway",
            facts=("payments.refund_path",),
            expression="refund_path == 'payment_gateway'",
        )
    )
    engine = AegisEngine(graph)
    engine.register_invariant_validator(
        "payments.inv.refunds_use_gateway",
        lambda facts: (
            facts["payments.refund_path"] == "payment_gateway",
            f"refund_path={facts['payments.refund_path']}",
        ),
    )
    engine.register_repair_directive(
        RepairDirective(
            invariant_id="payments.inv.refunds_use_gateway",
            must_change=("Restore refund routing through the approved payment gateway.",),
            must_preserve=("Keep the externally visible refund behavior unchanged.",),
            must_not_change=("Do not weaken the gateway invariant to make the proof pass.",),
            required_verification=("Re-run the refund-path invariant after the implementation change.",),
            required_evidence=("Observed refund execution path",),
        )
    )
    return engine


def run_demo() -> tuple[ChangeProof, ChangeProof]:
    engine = build_demo_engine()
    change = Change(
        id="demo.refund_change",
        type=ChangeType.CODE_CHANGE,
        summary="AI agent changed refund implementation",
        changed_fact_ids=("payments.refund_path",),
    )
    broken = engine.analyze(change, fact_values={"payments.refund_path": "stripe_direct"})
    fixed = engine.analyze(change, fact_values={"payments.refund_path": "payment_gateway"})
    return broken, fixed


def render_demo() -> str:
    broken, fixed = run_demo()
    contract = broken.repair_contract
    lines = [
        "AEGISGRAPH QUICK DEMO",
        "Scenario: an AI coding agent bypassed an approved PaymentGateway.",
        "The code may compile and local tests may still pass; the semantic invariant must not.",
        "",
        f"1) Broken implementation -> {broken.verdict.value.upper()}",
    ]
    for check in broken.invariant_checks:
        lines.append(f"   {check.status.value.upper():7} {check.invariant_id}: {check.message}")
    if contract:
        lines.extend([
            "   Repair Contract:",
            *[f"   - Must change: {item}" for item in contract.must_change],
            *[f"   - Must preserve: {item}" for item in contract.must_preserve],
        ])
    lines.extend([
        "",
        f"2) Repaired implementation -> {fixed.verdict.value.upper()}",
    ])
    for check in fixed.invariant_checks:
        lines.append(f"   {check.status.value.upper():7} {check.invariant_id}: {check.message}")
    lines.extend(["", "Every change needs proof."])
    return "\n".join(lines)
