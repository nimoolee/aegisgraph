from aegis_graph.audit.invocations import InvocationRecord, summarize_invocations
from aegis_graph.core.models import FactNode, Invariant, Rule
from aegis_graph.graph.store import SoftwareGraph
from aegis_graph.invariants.executor import InvariantCheck, InvariantStatus
from aegis_graph.impact.analyzer import ImpactResult
from aegis_graph.proof.models import ChangeProof, ProofVerdict
from aegis_graph.ui import build_graph_payload, render_graph_html
from decimal import Decimal
from aegis_graph.ui.auto_trading_labels import AUTO_TRADING_DISPLAY_LABELS


def test_graph_payload_includes_semantics_and_verification_status() -> None:
    graph = SoftwareGraph()
    graph.add_fact(FactNode(id="cash", name="Cash"))
    graph.add_fact(FactNode(id="orderable", name="Orderable"))
    graph.add_rule(Rule(id="rule.cash", name="Orderable cash", inputs=("cash",), outputs=("orderable",), expression="orderable = cash"))
    graph.add_invariant(Invariant(id="inv.cash", name="Cash nonnegative", facts=("cash",), expression="cash >= 0"))
    impact = ImpactResult(
        change_id="change.cash",
        seed_fact_ids=("cash",),
        affected_fact_ids=("cash", "orderable"),
        affected_rule_ids=("rule.cash",),
        affected_invariant_ids=("inv.cash",),
    )
    proof = ChangeProof(
        id="proof:change.cash",
        change_id="change.cash",
        commit_sha="abc",
        impact=impact,
        invariant_checks=(InvariantCheck("inv.cash", InvariantStatus.FAIL, "cash=-1"),),
        verdict=ProofVerdict.FAIL,
        reasons=("failed",),
    )
    payload = build_graph_payload(graph, proof=proof, fact_values={"cash": -1})
    invariant = next(node for node in payload["nodes"] if node["id"] == "inv.cash")
    fact = next(node for node in payload["nodes"] if node["id"] == "cash")
    assert invariant["status"] == "fail"
    assert invariant["impacted"] is True
    assert fact["details"]["value"] == -1
    assert payload["summary"]["fail"] == 1
    assert payload["summary"]["verdict"] == "fail"

    localized = build_graph_payload(graph, display_labels={"cash": "现金 · Cash"})
    cash = next(node for node in localized["nodes"] if node["id"] == "cash")
    assert cash["label"] == "现金 · Cash"
    assert cash["details"]["name"] == "Cash"
    assert cash["details"]["display_name"] == "现金 · Cash"


def test_html_is_self_contained_and_exposes_clickable_detail_surface() -> None:
    payload = {"summary": {"facts": 0, "rules": 0, "invariants": 0, "contexts": 0, "relationships": 0, "verdict": "unverified", "pass": 0, "fail": 0, "unknown": 0}, "nodes": [], "edges": []}
    html = render_graph_html(payload, title="Aegis Test")
    assert "Aegis Test" in html
    assert "REG Dashboard" in html
    assert "selectNode" in html
    assert "https://" not in html


def test_html_serializes_decimal_runtime_evidence_safely() -> None:
    payload = {"summary": {"facts": 1, "rules": 0, "invariants": 0, "contexts": 0, "relationships": 0, "verdict": "unverified", "pass": 0, "fail": 0, "unknown": 0}, "nodes": [{"id": "cash", "label": "Cash", "type": "fact", "status": "active", "impacted": False, "details": {"value": Decimal("10.606")}}], "edges": []}
    html = render_graph_html(payload)
    assert '10.606' in html


def test_graph_payload_exposes_invocation_audit_summary() -> None:
    assert AUTO_TRADING_DISPLAY_LABELS["auto.capital.flat"] == "资金归属已完成对账 · Capital Attribution Reconciled"
    assert AUTO_TRADING_DISPLAY_LABELS["auto.cash.safety"] == "安全资金账本 · Safety Cash Ledger"

    graph = SoftwareGraph()
    records = (
        InvocationRecord(timestamp="2026-10-03T10:00:00+00:00", mode="accepted_rule_proof", target="/tmp/x", verdict="fail"),
        InvocationRecord(timestamp="2026-10-03T10:01:00+00:00", mode="semantic_discovery", target="/tmp/x"),
    )
    payload = build_graph_payload(graph, invocations=records)
    assert payload["invocation_summary"]["total"] == 2
    assert payload["invocation_summary"]["fail"] == 1
    assert payload["invocations"][0]["mode"] == "semantic_discovery"
    assert summarize_invocations(records)["modes"]["accepted_rule_proof"] == 1
    html = render_graph_html(payload)
    assert "已记录运行 Tracked Runs" in html
    assert "事实 Fact" in html
    assert "不变量 Invariant" in html
    assert "来源 Provenance" in html
    assert "audit-strip" in html
