"""Versioned semantic-rule lifecycle and approval gate.

This module manages AegisGraph's own semantic truth.  It never writes a target
system.  Rule content is append-only/versioned; accepted semantics can change
only through explicit approval of one exact candidate version.
"""

from __future__ import annotations

from dataclasses import replace

from aegis_graph.core.models import (
    Change,
    ChangeType,
    ConfidenceSource,
    Invariant,
    Metadata,
    Rule,
)
from aegis_graph.graph.store import SoftwareGraph
from aegis_graph.impact.analyzer import ImpactAnalyzer, ImpactResult
from aegis_graph.semantics.models import (
    ManagedRuleKind,
    RuleApproval,
    RuleChangeProof,
    RuleChangeVerdict,
    SemanticRuleDiff,
    SemanticRuleSpec,
    SemanticRuleVersion,
)

_SEMANTIC_FIELDS = (
    "kind",
    "name",
    "inputs",
    "outputs",
    "facts",
    "expression",
    "applies_when",
    "context_ids",
)


class SemanticChangeError(ValueError):
    """Raised when semantic lifecycle rules are violated."""


class SemanticChangeManager:
    """Append-only rule versions + explicit acceptance + impact proof gate."""

    def __init__(self, graph: SoftwareGraph) -> None:
        self.graph = graph
        self.impact = ImpactAnalyzer(graph)
        self._versions: dict[str, list[SemanticRuleVersion]] = {}
        self._approvals: dict[tuple[str, int], RuleApproval] = {}
        self._bootstrap_existing_graph()

    def propose(
        self,
        spec: SemanticRuleSpec,
        *,
        proposed_by: str,
        evidence_ids: tuple[str, ...] = (),
        commit_sha: str | None = None,
    ) -> SemanticRuleVersion:
        self._validate_spec(spec)
        proposer = self._require_text(proposed_by, "candidate proposer")
        evidence = self._validate_trace_ids(evidence_ids, "candidate evidence ids")
        if commit_sha is not None:
            commit_sha = self._require_text(commit_sha, "candidate commit sha")
        versions = self._versions.setdefault(spec.semantic_id, [])
        version = SemanticRuleVersion(
            semantic_id=spec.semantic_id,
            version=(versions[-1].version + 1) if versions else 1,
            spec=spec,
            proposed_by=proposer,
            evidence_ids=evidence,
            commit_sha=commit_sha,
        )
        versions.append(version)
        return version

    def versions(self, semantic_id: str) -> tuple[SemanticRuleVersion, ...]:
        return tuple(self._versions.get(semantic_id, ()))

    def approval_for(self, semantic_id: str, version: int) -> RuleApproval | None:
        return self._approvals.get((semantic_id, version))

    def latest_accepted(self, semantic_id: str) -> SemanticRuleVersion | None:
        accepted_versions = [
            version
            for version in self._versions.get(semantic_id, ())
            if (semantic_id, version.version) in self._approvals
        ]
        return accepted_versions[-1] if accepted_versions else None

    def diff(self, candidate: SemanticRuleVersion) -> SemanticRuleDiff:
        previous = self.latest_accepted(candidate.semantic_id)
        changed: list[str] = []
        if previous is None:
            changed.extend(_SEMANTIC_FIELDS)
        else:
            before = previous.spec
            after = candidate.spec
            changed.extend(
                name for name in _SEMANTIC_FIELDS if getattr(before, name) != getattr(after, name)
            )
        return SemanticRuleDiff(
            semantic_id=candidate.semantic_id,
            from_version=previous.version if previous else None,
            to_version=candidate.version,
            changed_fields=tuple(changed),
        )

    def review(self, candidate: SemanticRuleVersion) -> RuleChangeProof:
        self._require_registered(candidate)
        diff = self.diff(candidate)
        impact = self._impact_for(candidate)
        approval = self.approval_for(candidate.semantic_id, candidate.version)
        reasons: tuple[str, ...]

        if not diff.has_semantic_change:
            verdict = RuleChangeVerdict.NO_CHANGE
            reasons = ("candidate is semantically identical to the latest accepted version",)
        elif approval is None:
            verdict = RuleChangeVerdict.APPROVAL_REQUIRED
            reasons = (
                "accepted semantics may not be replaced without explicit approval",
                "review semantic diff and impact before changing target implementation",
            )
        else:
            verdict = RuleChangeVerdict.ACCEPTED
            reasons = ("exact candidate version has explicit approval",)

        required = set(impact.affected_invariant_ids)
        if candidate.spec.kind is ManagedRuleKind.INVARIANT:
            required.add(candidate.semantic_id)
        return RuleChangeProof(
            semantic_id=candidate.semantic_id,
            candidate_version=candidate.version,
            previous_accepted_version=diff.from_version,
            diff=diff,
            impact=impact,
            required_verification_ids=tuple(sorted(required)),
            verdict=verdict,
            reasons=reasons,
            approval=approval,
        )

    def accept(self, candidate: SemanticRuleVersion, approval: RuleApproval) -> RuleChangeProof:
        self._require_registered(candidate)
        versions = self._versions[candidate.semantic_id]
        if versions[-1] != candidate:
            raise SemanticChangeError("only the latest candidate version may be accepted")
        if (
            not isinstance(approval.version, int)
            or isinstance(approval.version, bool)
            or approval.version < 1
        ):
            raise SemanticChangeError("approval version must be a positive integer")
        approval_id = self._require_text(approval.approval_id, "approval id")
        approved_by = self._require_text(approval.approved_by, "approval approver")
        reason = self._require_text(approval.reason, "approval reason")
        approval_evidence = self._validate_trace_ids(
            approval.evidence_ids, "approval evidence ids"
        )
        if approval.semantic_id != candidate.semantic_id or approval.version != candidate.version:
            raise SemanticChangeError("approval does not match the exact candidate version")
        if (
            approval_id != approval.approval_id
            or approved_by != approval.approved_by
            or reason != approval.reason
            or approval_evidence != approval.evidence_ids
        ):
            raise SemanticChangeError(
                "approval identifiers, approver, reason, and evidence ids may not have surrounding whitespace"
            )
        if not self.diff(candidate).has_semantic_change:
            raise SemanticChangeError("candidate has no semantic change to approve")
        key = (candidate.semantic_id, candidate.version)
        if key in self._approvals:
            raise SemanticChangeError("candidate version is already accepted")

        # Compute impact against the previous accepted graph before installing the new truth.
        pre_accept_proof = self.review(candidate)
        self._install(candidate)
        self._approvals[key] = approval
        return replace(
            pre_accept_proof,
            verdict=RuleChangeVerdict.ACCEPTED,
            reasons=("semantic change explicitly approved and installed",),
            approval=approval,
        )

    def _bootstrap_existing_graph(self) -> None:
        """Migrate already-accepted graph truth into version history without redefining it."""

        for rule in sorted(self.graph.rules.values(), key=lambda item: item.id):
            version_number = self._parse_existing_version(
                rule.metadata.version, semantic_id=rule.id
            )
            spec = SemanticRuleSpec(
                semantic_id=rule.id,
                kind=ManagedRuleKind.RULE,
                name=rule.name,
                inputs=rule.inputs,
                outputs=rule.outputs,
                expression=rule.expression,
                applies_when=rule.applies_when,
                context_ids=rule.context_ids,
            )
            version = SemanticRuleVersion(
                semantic_id=rule.id,
                version=version_number,
                spec=spec,
                proposed_by="aegis:migration",
                evidence_ids=("existing-accepted-graph",),
                commit_sha=rule.metadata.commit_sha,
            )
            self._versions[rule.id] = [version]
            self._approvals[(rule.id, version_number)] = RuleApproval(
                approval_id=f"migration:{version.version_id}",
                semantic_id=rule.id,
                version=version_number,
                approved_by="aegis:migration",
                reason="Pre-existing accepted semantic truth migrated into version history.",
                evidence_ids=("existing-accepted-graph",),
            )

        for invariant in sorted(self.graph.invariants.values(), key=lambda item: item.id):
            version_number = self._parse_existing_version(
                invariant.metadata.version, semantic_id=invariant.id
            )
            spec = SemanticRuleSpec(
                semantic_id=invariant.id,
                kind=ManagedRuleKind.INVARIANT,
                name=invariant.name,
                facts=invariant.facts,
                expression=invariant.expression,
                applies_when=invariant.applies_when,
                context_ids=invariant.context_ids,
            )
            version = SemanticRuleVersion(
                semantic_id=invariant.id,
                version=version_number,
                spec=spec,
                proposed_by="aegis:migration",
                evidence_ids=("existing-accepted-graph",),
                commit_sha=invariant.metadata.commit_sha,
            )
            self._versions[invariant.id] = [version]
            self._approvals[(invariant.id, version_number)] = RuleApproval(
                approval_id=f"migration:{version.version_id}",
                semantic_id=invariant.id,
                version=version_number,
                approved_by="aegis:migration",
                reason="Pre-existing accepted semantic truth migrated into version history.",
                evidence_ids=("existing-accepted-graph",),
            )

    @staticmethod
    def _require_text(value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise SemanticChangeError(f"{label} is required")
        return value.strip()

    @classmethod
    def _validate_trace_ids(cls, values: object, label: str) -> tuple[str, ...]:
        if not isinstance(values, tuple):
            raise SemanticChangeError(f"{label} must be a tuple of non-empty strings")
        cleaned: list[str] = []
        for value in values:
            text = cls._require_text(value, label)
            if text != value:
                raise SemanticChangeError(f"{label} may not contain surrounding whitespace")
            cleaned.append(text)
        if len(set(cleaned)) != len(cleaned):
            raise SemanticChangeError(f"{label} may not contain duplicates")
        return tuple(cleaned)

    @staticmethod
    def _parse_existing_version(value: object, *, semantic_id: str) -> int:
        if not isinstance(value, str) or not value.isdigit():
            raise SemanticChangeError(
                f"accepted semantic {semantic_id} has invalid version: {value!r}"
            )
        version = int(value)
        if version < 1 or str(version) != value:
            raise SemanticChangeError(
                f"accepted semantic {semantic_id} has invalid version: {value!r}"
            )
        return version

    def _impact_for(self, candidate: SemanticRuleVersion) -> ImpactResult:
        spec = candidate.spec
        if spec.kind is ManagedRuleKind.RULE:
            if spec.semantic_id in self.graph.rules:
                change = Change(
                    id=f"semantic-change:{candidate.version_id}",
                    type=ChangeType.RULE_CHANGE,
                    summary=f"Semantic rule change {candidate.version_id}",
                    changed_rule_ids=(spec.semantic_id,),
                    commit_sha=candidate.commit_sha,
                )
            else:
                change = Change(
                    id=f"semantic-change:{candidate.version_id}",
                    type=ChangeType.RULE_CHANGE,
                    summary=f"New semantic rule {candidate.version_id}",
                    changed_fact_ids=spec.outputs,
                    commit_sha=candidate.commit_sha,
                )
        elif spec.semantic_id in self.graph.invariants:
            change = Change(
                id=f"semantic-change:{candidate.version_id}",
                type=ChangeType.INVARIANT_CHANGE,
                summary=f"Semantic invariant change {candidate.version_id}",
                changed_invariant_ids=(spec.semantic_id,),
                commit_sha=candidate.commit_sha,
            )
        else:
            # Adding a new invariant does not mutate any existing fact. It has no
            # accepted-graph blast radius yet; review() explicitly requires the new
            # invariant itself to be verified before acceptance.
            change = Change(
                id=f"semantic-change:{candidate.version_id}",
                type=ChangeType.INVARIANT_CHANGE,
                summary=f"New semantic invariant {candidate.version_id}",
                commit_sha=candidate.commit_sha,
            )
        return self.impact.analyze(change)

    def _install(self, candidate: SemanticRuleVersion) -> None:
        spec = candidate.spec
        metadata = Metadata(
            version=str(candidate.version),
            provenance=ConfidenceSource.EXPLICIT,
            confidence=1.0,
            valid_from=candidate.commit_sha,
            commit_sha=candidate.commit_sha,
        )
        previous = self.latest_accepted(candidate.semantic_id)
        expected_version = str(previous.version) if previous else None

        if spec.kind is ManagedRuleKind.RULE:
            rule_value = Rule(
                id=spec.semantic_id,
                name=spec.name,
                inputs=spec.inputs,
                outputs=spec.outputs,
                expression=spec.expression,
                applies_when=spec.applies_when,
                context_ids=spec.context_ids,
                metadata=metadata,
            )
            if spec.semantic_id in self.graph.rules:
                if expected_version is None:
                    raise SemanticChangeError("graph has an unmanaged accepted rule with the same id")
                self.graph.replace_rule(rule_value, expected_current_version=expected_version)
            else:
                self.graph.add_rule(rule_value)
        else:
            invariant_value = Invariant(
                id=spec.semantic_id,
                name=spec.name,
                facts=spec.facts,
                expression=spec.expression,
                applies_when=spec.applies_when,
                context_ids=spec.context_ids,
                metadata=metadata,
            )
            if spec.semantic_id in self.graph.invariants:
                if expected_version is None:
                    raise SemanticChangeError("graph has an unmanaged accepted invariant with the same id")
                self.graph.replace_invariant(
                    invariant_value, expected_current_version=expected_version
                )
            else:
                self.graph.add_invariant(invariant_value)

    def _require_registered(self, candidate: SemanticRuleVersion) -> None:
        versions = self._versions.get(candidate.semantic_id, ())
        if candidate not in versions:
            raise SemanticChangeError("candidate version is not registered in this manager")

    def _validate_spec(self, spec: SemanticRuleSpec) -> None:
        semantic_id = self._require_text(spec.semantic_id, "semantic id")
        name = self._require_text(spec.name, "semantic name")
        if semantic_id != spec.semantic_id or name != spec.name:
            raise SemanticChangeError("semantic id and name may not have surrounding whitespace")
        if not isinstance(spec.kind, ManagedRuleKind):
            raise SemanticChangeError("semantic kind must be ManagedRuleKind")
        if spec.kind is ManagedRuleKind.RULE and spec.semantic_id in self.graph.invariants:
            raise SemanticChangeError(
                f"semantic id {spec.semantic_id} is already an invariant and cannot become a rule"
            )
        if spec.kind is ManagedRuleKind.INVARIANT and spec.semantic_id in self.graph.rules:
            raise SemanticChangeError(
                f"semantic id {spec.semantic_id} is already a rule and cannot become an invariant"
            )
        if spec.kind is ManagedRuleKind.RULE:
            if not spec.outputs:
                raise SemanticChangeError("a rule requires at least one output fact")
            if spec.facts:
                raise SemanticChangeError("rule specs use inputs/outputs, not facts")
            fact_ids = (*spec.inputs, *spec.outputs)
        else:
            if not spec.facts:
                raise SemanticChangeError("an invariant requires at least one fact")
            if spec.inputs or spec.outputs:
                raise SemanticChangeError("invariant specs use facts, not inputs/outputs")
            fact_ids = spec.facts
        for fact_id in fact_ids:
            text = self._require_text(fact_id, "semantic fact reference")
            if text != fact_id:
                raise SemanticChangeError(
                    "semantic fact references may not have surrounding whitespace"
                )
        for context_id in spec.context_ids:
            text = self._require_text(context_id, "semantic context reference")
            if text != context_id:
                raise SemanticChangeError(
                    "semantic context references may not have surrounding whitespace"
                )
        if spec.expression is not None and not isinstance(spec.expression, str):
            raise SemanticChangeError("semantic expression must be a string or None")
        if spec.applies_when is not None and not isinstance(spec.applies_when, str):
            raise SemanticChangeError("semantic applies_when must be a string or None")
        missing_facts = sorted({fact_id for fact_id in fact_ids if fact_id not in self.graph.facts})
        if missing_facts:
            raise SemanticChangeError(f"unknown fact ids: {', '.join(missing_facts)}")
        missing_contexts = sorted(
            {context_id for context_id in spec.context_ids if context_id not in self.graph.contexts}
        )
        if missing_contexts:
            raise SemanticChangeError(f"unknown context ids: {', '.join(missing_contexts)}")
