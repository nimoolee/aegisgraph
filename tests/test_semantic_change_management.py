import pytest

from aegis_graph.core.models import FactNode, Invariant, Metadata, Relationship, RelationshipType, Rule
from aegis_graph.graph.store import GraphIntegrityError, SoftwareGraph
from aegis_graph.semantics import (
    ManagedRuleKind,
    RuleApproval,
    RuleChangeVerdict,
    SemanticChangeError,
    SemanticChangeManager,
    SemanticRuleSpec,
)


def build_graph() -> SoftwareGraph:
    graph = SoftwareGraph()
    for fact_id in ("cash.physical", "cash.safety", "cash.trading", "cash.gap", "orderable"):
        graph.add_fact(FactNode(id=fact_id, name=fact_id))
    graph.add_relationship(
        Relationship(
            id="rel.orderable.cash",
            source="orderable",
            target="cash.trading",
            type=RelationshipType.DEPENDS_ON,
        )
    )
    graph.add_invariant(
        Invariant(
            id="inv.orderable.nonnegative",
            name="Orderable must remain valid",
            facts=("cash.trading", "orderable"),
        )
    )
    return graph


def approval(rule, *, who="product-owner") -> RuleApproval:
    return RuleApproval(
        approval_id=f"approval:{rule.version_id}",
        semantic_id=rule.semantic_id,
        version=rule.version,
        approved_by=who,
        reason="Definition reviewed against product intent and evidence.",
        evidence_ids=("evidence:decision",),
    )


def cash_rule(expression: str, *, applies_when: str | None = None) -> SemanticRuleSpec:
    return SemanticRuleSpec(
        semantic_id="rule.cash.partition",
        kind=ManagedRuleKind.RULE,
        name="Cash partition",
        inputs=("cash.physical", "cash.safety", "cash.trading"),
        outputs=("cash.gap",),
        expression=expression,
        applies_when=applies_when,
    )


def test_candidate_is_not_accepted_without_explicit_approval() -> None:
    graph = build_graph()
    manager = SemanticChangeManager(graph)
    candidate = manager.propose(cash_rule("physical - safety - trading"), proposed_by="discovery")

    proof = manager.review(candidate)
    assert proof.verdict is RuleChangeVerdict.APPROVAL_REQUIRED
    assert proof.previous_accepted_version is None
    assert graph.rules.get("rule.cash.partition") is None


def test_existing_accepted_graph_rule_is_migrated_as_version_baseline() -> None:
    graph = build_graph()
    graph.add_rule(
        Rule(
            id="rule.existing",
            name="Existing rule",
            inputs=("cash.physical",),
            outputs=("cash.trading",),
            expression="physical",
            metadata=Metadata(version="3", commit_sha="abc123"),
        )
    )
    manager = SemanticChangeManager(graph)

    baseline = manager.latest_accepted("rule.existing")
    assert baseline is not None
    assert baseline.version == 3
    assert baseline.commit_sha == "abc123"
    assert manager.approval_for("rule.existing", 3).approved_by == "aegis:migration"

    v4 = manager.propose(
        SemanticRuleSpec(
            semantic_id="rule.existing",
            kind=ManagedRuleKind.RULE,
            name="Existing rule",
            inputs=("cash.physical", "cash.safety"),
            outputs=("cash.trading",),
            expression="physical - safety",
        ),
        proposed_by="product-review",
    )
    assert v4.version == 4
    assert manager.review(v4).previous_accepted_version == 3


def test_accepting_exact_candidate_installs_versioned_rule_and_keeps_history() -> None:
    graph = build_graph()
    manager = SemanticChangeManager(graph)
    v1 = manager.propose(cash_rule("physical - safety - trading"), proposed_by="discovery")
    accepted_v1 = manager.accept(v1, approval(v1))

    assert accepted_v1.verdict is RuleChangeVerdict.ACCEPTED
    assert graph.rules["rule.cash.partition"].metadata.version == "1"

    v2 = manager.propose(
        cash_rule(
            "physical - safety - trading - pending",
            applies_when="capital_state == 'RECONCILED'",
        ),
        proposed_by="product-review",
    )
    pre = manager.review(v2)
    assert pre.verdict is RuleChangeVerdict.APPROVAL_REQUIRED
    assert set(pre.diff.changed_fields) == {"expression", "applies_when"}
    assert "inv.orderable.nonnegative" not in pre.required_verification_ids

    accepted_v2 = manager.accept(v2, approval(v2))
    assert accepted_v2.previous_accepted_version == 1
    assert graph.rules["rule.cash.partition"].metadata.version == "2"
    assert [version.version for version in manager.versions("rule.cash.partition")] == [1, 2]
    assert manager.latest_accepted("rule.cash.partition") == v2
    assert manager.approval_for("rule.cash.partition", 1) is not None
    assert manager.approval_for("rule.cash.partition", 2) is not None


def test_rule_change_impact_uses_existing_graph_and_selects_downstream_invariant() -> None:
    graph = build_graph()
    manager = SemanticChangeManager(graph)
    v1 = manager.propose(
        SemanticRuleSpec(
            semantic_id="rule.trading.cash",
            kind=ManagedRuleKind.RULE,
            name="Trading cash",
            inputs=("cash.physical",),
            outputs=("cash.trading",),
            expression="physical",
        ),
        proposed_by="product",
    )
    manager.accept(v1, approval(v1))

    v2 = manager.propose(
        SemanticRuleSpec(
            semantic_id="rule.trading.cash",
            kind=ManagedRuleKind.RULE,
            name="Trading cash",
            inputs=("cash.physical", "cash.safety"),
            outputs=("cash.trading",),
            expression="physical - safety",
        ),
        proposed_by="discovery",
    )
    proof = manager.review(v2)

    assert proof.verdict is RuleChangeVerdict.APPROVAL_REQUIRED
    assert "cash.trading" in proof.impact.seed_fact_ids
    assert "orderable" in proof.impact.affected_fact_ids
    assert "inv.orderable.nonnegative" in proof.required_verification_ids


def test_accepted_rule_cannot_be_silently_replaced_or_approved_out_of_order() -> None:
    graph = build_graph()
    manager = SemanticChangeManager(graph)
    v1 = manager.propose(cash_rule("physical - safety - trading"), proposed_by="product")
    manager.accept(v1, approval(v1))
    v2 = manager.propose(cash_rule("physical - safety"), proposed_by="developer-ai")
    v3 = manager.propose(cash_rule("physical - trading"), proposed_by="developer-ai")

    with pytest.raises(SemanticChangeError, match="latest candidate"):
        manager.accept(v2, approval(v2))
    assert graph.rules["rule.cash.partition"].metadata.version == "1"

    with pytest.raises(GraphIntegrityError, match="version conflict"):
        graph.replace_rule(
            Rule(
                id="rule.cash.partition",
                name="Cash partition",
                inputs=("cash.physical",),
                outputs=("cash.gap",),
                expression="wrong",
                metadata=Metadata(version="99"),
            ),
            expected_current_version="99",
        )
    assert graph.rules["rule.cash.partition"].metadata.version == "1"
    assert manager.review(v3).verdict is RuleChangeVerdict.APPROVAL_REQUIRED


def test_candidate_requires_traceable_proposer() -> None:
    manager = SemanticChangeManager(build_graph())
    with pytest.raises(SemanticChangeError, match="proposer"):
        manager.propose(cash_rule("physical - safety - trading"), proposed_by="")


def test_approval_must_match_exact_version_and_be_explicit() -> None:
    manager = SemanticChangeManager(build_graph())
    candidate = manager.propose(cash_rule("physical - safety - trading"), proposed_by="discovery")

    with pytest.raises(SemanticChangeError, match="exact candidate"):
        manager.accept(
            candidate,
            RuleApproval("a", candidate.semantic_id, 99, "owner", "reason"),
        )
    with pytest.raises(SemanticChangeError, match="requires id, approver, and reason"):
        manager.accept(
            candidate,
            RuleApproval("", candidate.semantic_id, candidate.version, "owner", "reason"),
        )


def test_no_change_candidate_does_not_need_or_allow_approval() -> None:
    manager = SemanticChangeManager(build_graph())
    v1 = manager.propose(cash_rule("physical - safety - trading"), proposed_by="product")
    manager.accept(v1, approval(v1))
    v2 = manager.propose(cash_rule("physical - safety - trading"), proposed_by="discovery")

    assert manager.review(v2).verdict is RuleChangeVerdict.NO_CHANGE
    with pytest.raises(SemanticChangeError, match="no semantic change"):
        manager.accept(v2, approval(v2))


def test_invariant_change_is_versioned_and_self_selected_for_reverification() -> None:
    graph = build_graph()
    manager = SemanticChangeManager(graph)
    candidate = manager.propose(
        SemanticRuleSpec(
            semantic_id="inv.cash.partition",
            kind=ManagedRuleKind.INVARIANT,
            name="Cash partition conservation",
            facts=("cash.physical", "cash.safety", "cash.trading", "cash.gap"),
            expression="gap == 0",
            applies_when="capital_state == 'RECONCILED'",
        ),
        proposed_by="discovery",
    )
    proof = manager.review(candidate)
    assert proof.verdict is RuleChangeVerdict.APPROVAL_REQUIRED
    assert proof.required_verification_ids == ("inv.cash.partition",)

    manager.accept(candidate, approval(candidate))
    assert graph.invariants["inv.cash.partition"].metadata.version == "1"
