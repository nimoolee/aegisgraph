import pytest

from aegis_graph.core.models import (
    Change,
    ChangeType,
    Context,
    FactNode,
    Invariant,
    Relationship,
    RelationshipType,
    Rule,
)
from aegis_graph.engine import AegisEngine
from aegis_graph.graph.store import GraphIntegrityError, SoftwareGraph
from aegis_graph.proof.models import ProofVerdict


def build_cash_graph() -> SoftwareGraph:
    graph = SoftwareGraph()
    for fact_id in (
        "cash.trading",
        "order.eligibility",
        "order.auto",
        "ui.cash",
        "market.phase",
        "unrelated.tooltip",
    ):
        graph.add_fact(FactNode(id=fact_id, name=fact_id))

    graph.add_relationship(
        Relationship(
            id="rel.order_needs_cash",
            source="order.eligibility",
            target="cash.trading",
            type=RelationshipType.DEPENDS_ON,
        )
    )
    graph.add_relationship(
        Relationship(
            id="rel.eligibility_controls_auto_order",
            source="order.eligibility",
            target="order.auto",
            type=RelationshipType.CONTROLS,
        )
    )
    graph.add_relationship(
        Relationship(
            id="rel.ui_displays_cash",
            source="ui.cash",
            target="cash.trading",
            type=RelationshipType.DISPLAYS,
        )
    )
    graph.add_invariant(
        Invariant(
            id="inv.order_cash",
            name="Cash must remain valid for order eligibility",
            facts=("cash.trading", "order.eligibility"),
        )
    )
    graph.add_invariant(
        Invariant(
            id="inv.unrelated",
            name="Unrelated tooltip invariant",
            facts=("unrelated.tooltip",),
        )
    )
    return graph


def test_dependency_and_control_edges_propagate_in_semantic_directions() -> None:
    graph = build_cash_graph()
    proof = AegisEngine(graph).analyze(
        Change(
            id="change.cash",
            type=ChangeType.NODE_CHANGE,
            summary="Change trading cash semantics",
            changed_fact_ids=("cash.trading",),
        )
    )

    assert proof.impact.affected_fact_ids == (
        "cash.trading",
        "order.auto",
        "order.eligibility",
        "ui.cash",
    )
    assert proof.impact.affected_invariant_ids == ("inv.order_cash",)
    assert proof.verdict is ProofVerdict.UNKNOWN

    auto_path = proof.impact.paths["order.auto"]
    assert auto_path.fact_ids == ("cash.trading", "order.eligibility", "order.auto")
    assert auto_path.via == (
        "edge:rel.order_needs_cash:depends_on",
        "edge:rel.eligibility_controls_auto_order:controls",
    )


def test_rule_change_seeds_outputs_then_propagates() -> None:
    graph = build_cash_graph()
    graph.add_fact(FactNode(id="cash.source", name="Cash Source"))
    graph.add_rule(
        Rule(
            id="rule.cash",
            name="Derive trading cash",
            inputs=("cash.source",),
            outputs=("cash.trading",),
        )
    )

    proof = AegisEngine(graph).analyze(
        Change(
            id="change.rule",
            type=ChangeType.RULE_CHANGE,
            summary="Change trading cash formula",
            changed_rule_ids=("rule.cash",),
        )
    )

    assert "cash.trading" in proof.impact.seed_fact_ids
    assert "order.auto" in proof.impact.affected_fact_ids
    assert "rule.cash" in proof.impact.affected_rule_ids


def test_temporal_context_change_seeds_context_rules_and_invariants() -> None:
    graph = build_cash_graph()
    graph.add_context(Context(id="phase.core", kind="temporal"))
    graph.add_rule(
        Rule(
            id="rule.core_entry",
            name="Core-window entry rule",
            inputs=("market.phase", "cash.trading"),
            outputs=("order.eligibility",),
            context_ids=("phase.core",),
        )
    )
    graph.add_invariant(
        Invariant(
            id="inv.core_entry",
            name="Core-window entry invariant",
            facts=("order.eligibility",),
            context_ids=("phase.core",),
        )
    )

    proof = AegisEngine(graph).analyze(
        Change(
            id="change.time",
            type=ChangeType.TEMPORAL_CHANGE,
            summary="Move the core-window boundary",
            changed_context_ids=("phase.core",),
        )
    )

    assert "order.eligibility" in proof.impact.seed_fact_ids
    assert "order.auto" in proof.impact.affected_fact_ids
    assert "inv.core_entry" in proof.impact.affected_invariant_ids


def test_executable_invariant_can_turn_unknown_proof_into_pass() -> None:
    graph = build_cash_graph()
    engine = AegisEngine(graph)
    engine.register_invariant_validator(
        "inv.order_cash",
        lambda facts: (
            facts["cash.trading"] >= 0 and facts["order.eligibility"] is True,
            "cash and order eligibility are consistent",
        ),
    )

    proof = engine.analyze(
        Change(
            id="change.cash.pass",
            type=ChangeType.NODE_CHANGE,
            summary="Recalculate trading cash",
            changed_fact_ids=("cash.trading",),
        ),
        fact_values={"cash.trading": 12.5, "order.eligibility": True},
    )

    assert proof.verdict is ProofVerdict.PASS
    assert len(proof.invariant_checks) == 1
    assert proof.invariant_checks[0].status.value == "pass"


def test_failed_invariant_makes_change_proof_fail() -> None:
    graph = build_cash_graph()
    engine = AegisEngine(graph)
    engine.register_invariant_validator(
        "inv.order_cash",
        lambda facts: facts["cash.trading"] >= 0,
    )

    proof = engine.analyze(
        Change(
            id="change.cash.fail",
            type=ChangeType.NODE_CHANGE,
            summary="Broken trading cash calculation",
            changed_fact_ids=("cash.trading",),
        ),
        fact_values={"cash.trading": -1.0, "order.eligibility": True},
    )

    assert proof.verdict is ProofVerdict.FAIL
    assert proof.invariant_checks[0].status.value == "fail"
    assert proof.repair_contract is not None
    assert proof.repair_contract.violated_invariant_ids == ("inv.order_cash",)
    assert any("Do not disable" in item for item in proof.repair_contract.must_not_change)
    assert any("Do not prescribe target architecture" in item for item in proof.repair_contract.must_not_change)


def test_missing_runtime_evidence_remains_unknown() -> None:
    graph = build_cash_graph()
    engine = AegisEngine(graph)
    engine.register_invariant_validator(
        "inv.order_cash",
        lambda facts: facts["cash.trading"] >= 0,
    )

    proof = engine.analyze(
        Change(
            id="change.cash.missing",
            type=ChangeType.NODE_CHANGE,
            summary="Cash change without complete evidence",
            changed_fact_ids=("cash.trading",),
        ),
        fact_values={"cash.trading": 10.0},
    )

    assert proof.verdict is ProofVerdict.UNKNOWN
    assert "missing evidence" in proof.invariant_checks[0].message


def test_engine_exposes_read_only_target_boundary() -> None:
    engine = AegisEngine(build_cash_graph())
    assert engine.boundary.target_access == "read_only"
    assert engine.boundary.may_modify_target is False
    assert engine.boundary.may_generate_target_patch is False
    assert engine.boundary.may_emit_repair_contract is True
    assert engine.boundary.may_prescribe_target_architecture is False
    assert engine.boundary.may_prescribe_target_implementation is False
    assert engine.boundary.may_emit_structural_risk is True
    assert engine.boundary.may_emit_implementation_neutral_constraints is True


def test_pass_proof_has_no_repair_contract() -> None:
    graph = build_cash_graph()
    engine = AegisEngine(graph)
    engine.register_invariant_validator("inv.order_cash", lambda facts: True)
    proof = engine.analyze(
        Change(
            id="change.no.repair",
            type=ChangeType.NODE_CHANGE,
            summary="Healthy change",
            changed_fact_ids=("cash.trading",),
        ),
        fact_values={"cash.trading": 1, "order.eligibility": True},
    )
    assert proof.verdict is ProofVerdict.PASS
    assert proof.repair_contract is None


def test_graph_rejects_dangling_semantic_references() -> None:
    graph = SoftwareGraph()
    graph.add_fact(FactNode(id="fact.a", name="A"))

    with pytest.raises(GraphIntegrityError, match="unknown fact ids"):
        graph.add_relationship(
            Relationship(
                id="rel.bad",
                source="fact.a",
                target="fact.missing",
                type=RelationshipType.DEPENDS_ON,
            )
        )


def test_unknown_fact_in_change_fails_closed() -> None:
    graph = build_cash_graph()

    with pytest.raises(ValueError, match="unknown fact ids"):
        AegisEngine(graph).analyze(
            Change(
                id="change.unknown",
                type=ChangeType.NODE_CHANGE,
                summary="Unknown semantic target",
                changed_fact_ids=("cash.not_registered",),
            )
        )
