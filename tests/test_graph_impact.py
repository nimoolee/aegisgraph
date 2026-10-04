from dataclasses import asdict

import pytest

from aegis_graph.core.models import (
    Change,
    ChangeType,
    Context,
    FactNode,
    Invariant,
    Metadata,
    Relationship,
    RelationshipType,
    Rule,
)
from aegis_graph.engine import AegisEngine
from aegis_graph.graph.store import GraphIntegrityError, SoftwareGraph
from aegis_graph.impact.analyzer import ImpactPath, ImpactResult
from aegis_graph.invariants.executor import InvariantCheck, InvariantStatus
from aegis_graph.proof.builder import build_impact_proof
from aegis_graph.proof.models import ProofVerdict, RepairDirective


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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("changed_rule_ids", ("rule.missing",), "unknown rule ids"),
        ("changed_relationship_ids", ("rel.missing",), "unknown relationship ids"),
        ("changed_invariant_ids", ("inv.missing",), "unknown invariant ids"),
        ("changed_context_ids", ("context.missing",), "unknown context ids"),
    ],
)
def test_unknown_change_references_fail_closed(field: str, value: tuple[str, ...], message: str) -> None:
    graph = build_cash_graph()
    kwargs = {field: value}
    with pytest.raises(ValueError, match=message):
        AegisEngine(graph).analyze(
            Change(
                id=f"change.unknown.{field}",
                type=ChangeType.NODE_CHANGE,
                summary="Unknown semantic reference",
                **kwargs,
            )
        )


@pytest.mark.parametrize(
    "bad_return",
    [
        None,
        "yes",
        1,
        (True,),
        (True, ""),
        (True, "ok", "extra"),
        (1, "not-bool"),
    ],
)
def test_invalid_validator_contract_remains_unknown(bad_return: object) -> None:
    graph = build_cash_graph()
    engine = AegisEngine(graph)
    engine.register_invariant_validator("inv.order_cash", lambda facts: bad_return)  # type: ignore[arg-type]
    proof = engine.analyze(
        Change(
            id="change.validator.contract",
            type=ChangeType.NODE_CHANGE,
            summary="Malformed integration validator",
            changed_fact_ids=("cash.trading",),
        ),
        fact_values={"cash.trading": 1, "order.eligibility": True},
    )
    assert proof.verdict is ProofVerdict.UNKNOWN
    assert proof.invariant_checks[0].status.value == "unknown"
    assert "validator error" in proof.invariant_checks[0].message


def test_invalid_invariant_check_status_cannot_be_smuggled_into_a_pass() -> None:
    with pytest.raises(TypeError, match="InvariantStatus"):
        InvariantCheck(
            invariant_id="inv.order_cash",
            status="fail",  # type: ignore[arg-type]
            message="should fail",
        )


def test_validator_exception_remains_unknown() -> None:
    graph = build_cash_graph()
    engine = AegisEngine(graph)

    def broken_validator(_facts):
        raise RuntimeError("boom")

    engine.register_invariant_validator("inv.order_cash", broken_validator)
    proof = engine.analyze(
        Change(
            id="change.validator.exception",
            type=ChangeType.NODE_CHANGE,
            summary="Validator raises",
            changed_fact_ids=("cash.trading",),
        ),
        fact_values={"cash.trading": 1, "order.eligibility": True},
    )
    assert proof.verdict is ProofVerdict.UNKNOWN
    assert "RuntimeError: boom" in proof.invariant_checks[0].message


def test_impact_reachability_is_not_truncated_by_long_dependency_chain() -> None:
    graph = SoftwareGraph()
    chain_length = 20
    for index in range(chain_length):
        graph.add_fact(FactNode(id=f"fact.{index}", name=f"Fact {index}"))
    for index in range(chain_length - 1):
        graph.add_relationship(
            Relationship(
                id=f"rel.{index}",
                source=f"fact.{index + 1}",
                target=f"fact.{index}",
                type=RelationshipType.DEPENDS_ON,
            )
        )
    graph.add_invariant(
        Invariant(
            id="inv.deep",
            name="Deep dependency remains covered",
            facts=(f"fact.{chain_length - 1}",),
        )
    )

    proof = AegisEngine(graph).analyze(
        Change(
            id="change.deep",
            type=ChangeType.NODE_CHANGE,
            summary="Change first fact in a long chain",
            changed_fact_ids=("fact.0",),
        )
    )
    assert f"fact.{chain_length - 1}" in proof.impact.affected_fact_ids
    assert "inv.deep" in proof.impact.affected_invariant_ids


def test_change_proof_cannot_pass_with_missing_invariant_check() -> None:
    impact = ImpactResult(
        change_id="change.incomplete-proof",
        seed_fact_ids=("fact.a",),
        affected_fact_ids=("fact.a",),
        affected_rule_ids=(),
        affected_invariant_ids=("inv.a", "inv.b"),
    )
    proof = build_impact_proof(
        Change(
            id="change.incomplete-proof",
            type=ChangeType.NODE_CHANGE,
            summary="Incomplete proof evidence",
            changed_fact_ids=("fact.a",),
        ),
        impact,
        (
            InvariantCheck(
                invariant_id="inv.a",
                status=InvariantStatus.PASS,
                message="ok",
            ),
        ),
    )
    assert proof.verdict is ProofVerdict.UNKNOWN
    assert any("missing checks: inv.b" in reason for reason in proof.reasons)


def test_change_proof_cannot_pass_with_unexpected_or_duplicate_checks() -> None:
    impact = ImpactResult(
        change_id="change.bad-proof-set",
        seed_fact_ids=("fact.a",),
        affected_fact_ids=("fact.a",),
        affected_rule_ids=(),
        affected_invariant_ids=("inv.a",),
    )
    proof = build_impact_proof(
        Change(
            id="change.bad-proof-set",
            type=ChangeType.NODE_CHANGE,
            summary="Mismatched proof evidence",
            changed_fact_ids=("fact.a",),
        ),
        impact,
        (
            InvariantCheck("inv.a", InvariantStatus.PASS, "ok"),
            InvariantCheck("inv.a", InvariantStatus.PASS, "duplicate"),
            InvariantCheck("inv.other", InvariantStatus.PASS, "unexpected"),
        ),
    )
    assert proof.verdict is ProofVerdict.UNKNOWN
    assert any("unexpected checks: inv.other" in reason for reason in proof.reasons)
    assert any("duplicate checks: inv.a" in reason for reason in proof.reasons)


def test_impact_result_mappings_are_immutable_after_construction() -> None:
    source_paths = {"fact.a": ImpactPath(fact_ids=("fact.a",))}
    impact = ImpactResult(
        change_id="change.immutable-impact",
        seed_fact_ids=("fact.a",),
        affected_fact_ids=("fact.a",),
        affected_rule_ids=(),
        affected_invariant_ids=(),
        paths=source_paths,
    )
    source_paths["fact.b"] = ImpactPath(fact_ids=("fact.b",))

    assert "fact.b" not in impact.paths
    with pytest.raises(TypeError):
        impact.paths["fact.b"] = ImpactPath(fact_ids=("fact.b",))  # type: ignore[index]


def test_graph_storage_cannot_be_mutated_around_integrity_api() -> None:
    graph = SoftwareGraph()
    graph.add_fact(FactNode(id="fact.safe", name="Safe"))

    with pytest.raises(TypeError):
        graph.facts["fact.bypass"] = FactNode(id="fact.bypass", name="Bypass")  # type: ignore[index]

    assert "fact.bypass" not in graph.facts


@pytest.mark.parametrize("bad_id", ["", "   "])
def test_graph_rejects_blank_semantic_ids(bad_id: str) -> None:
    graph = SoftwareGraph()
    with pytest.raises(GraphIntegrityError, match="non-empty string"):
        graph.add_fact(FactNode(id=bad_id, name="Bad"))


def test_graph_rejects_empty_rule_outputs_and_invariant_facts() -> None:
    graph = SoftwareGraph()
    graph.add_fact(FactNode(id="fact.a", name="A"))

    with pytest.raises(GraphIntegrityError, match="at least one output"):
        graph.add_rule(Rule(id="rule.empty", name="Empty", inputs=("fact.a",), outputs=()))
    with pytest.raises(GraphIntegrityError, match="at least one fact"):
        graph.add_invariant(Invariant(id="inv.empty", name="Empty", facts=()))


def test_context_and_change_metadata_are_detached_and_immutable() -> None:
    source = {"nested": {"phase": "A"}, "items": [1, 2]}
    context = Context(id="ctx.safe", kind="phase", attributes=source)
    change = Change(
        id="change.safe",
        type=ChangeType.STATE_CHANGE,
        summary="immutable metadata",
        metadata=source,
    )
    source["nested"]["phase"] = "B"
    source["items"].append(3)

    assert context.attributes["nested"]["phase"] == "A"
    assert tuple(context.attributes["items"]) == (1, 2)
    assert change.metadata["nested"]["phase"] == "A"
    with pytest.raises(TypeError):
        context.attributes["new"] = "x"  # type: ignore[index]

    assert asdict(context)["attributes"]["nested"]["phase"] == "A"
    assert asdict(change)["metadata"]["nested"]["phase"] == "A"


def test_semantic_metadata_detaches_and_does_not_expose_mutable_extension_values() -> None:
    payload = bytearray(b"abc")
    change = Change(
        id="change.mutable-extension",
        type=ChangeType.CODE_CHANGE,
        summary="snapshot mutable extension value",
        metadata={"payload": payload},
    )

    payload[0] = ord("z")
    first = change.metadata["payload"]
    assert isinstance(first, bytearray)
    assert bytes(first) == b"abc"

    first[1] = ord("y")
    second = change.metadata["payload"]
    assert bytes(second) == b"abc"


def test_accepted_and_proof_sequences_detach_from_caller_lists() -> None:
    rule_inputs = ["cash.trading"]
    rule_outputs = ["orderable"]
    rule = Rule(
        id="rule.detached",
        name="Detached rule",
        inputs=rule_inputs,  # type: ignore[arg-type]
        outputs=rule_outputs,  # type: ignore[arg-type]
    )
    rule_inputs.append("forged.input")
    rule_outputs.append("forged.output")
    assert rule.inputs == ("cash.trading",)
    assert rule.outputs == ("orderable",)

    affected = ["cash.trading"]
    impact = ImpactResult(
        change_id="change.detached",
        seed_fact_ids=affected,  # type: ignore[arg-type]
        affected_fact_ids=affected,  # type: ignore[arg-type]
        affected_rule_ids=[],  # type: ignore[arg-type]
        affected_invariant_ids=[],  # type: ignore[arg-type]
    )
    affected.append("forged.fact")
    assert impact.seed_fact_ids == ("cash.trading",)
    assert impact.affected_fact_ids == ("cash.trading",)

    directives = ["preserve cash conservation"]
    directive = RepairDirective(
        invariant_id="inv.detached",
        must_preserve=directives,  # type: ignore[arg-type]
    )
    directives.append("forged directive")
    assert directive.must_preserve == ("preserve cash conservation",)


def test_semantic_metadata_rejects_cycles_and_nonstring_keys() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError, match="cyclic semantic data"):
        Context(id="ctx.cycle", kind="phase", attributes=cyclic)

    with pytest.raises(TypeError, match="keys must be strings"):
        Context(id="ctx.bad-key", kind="phase", attributes={1: "one"})  # type: ignore[dict-item]

    with pytest.raises(ValueError, match="non-empty"):
        Change(
            id="change.bad-key",
            type=ChangeType.CODE_CHANGE,
            summary="bad metadata key",
            metadata={" ": "value"},
        )


def test_change_rejects_blank_identity_and_bad_reference_types() -> None:
    with pytest.raises(ValueError, match="change id"):
        Change(id=" ", type=ChangeType.CODE_CHANGE, summary="x")
    with pytest.raises(ValueError, match="changed fact ids"):
        Change(
            id="change.bad-ref",
            type=ChangeType.CODE_CHANGE,
            summary="bad ref",
            changed_fact_ids=("",),
        )


def test_graph_rejects_invalid_reference_and_relationship_types() -> None:
    graph = SoftwareGraph()
    graph.add_fact(FactNode(id="fact.a", name="A"))
    with pytest.raises(GraphIntegrityError, match="fact reference"):
        graph.add_rule(Rule(id="rule.bad-ref", name="Bad", inputs=("",), outputs=("fact.a",)))
    with pytest.raises(GraphIntegrityError, match="relationship type"):
        graph.add_relationship(
            Relationship(
                id="rel.bad-type",
                source="fact.a",
                target="fact.a",
                type="depends_on",  # type: ignore[arg-type]
            )
        )


def test_metadata_rejects_nonfinite_or_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        Metadata(confidence=float("nan"))
    with pytest.raises(ValueError, match="between 0 and 1"):
        Metadata(confidence=1.01)
