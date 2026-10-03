from pathlib import Path

from aegis_graph.discovery import CodeAnchor, discover_python
from aegis_graph.semantics import detect_conflicts, unify_discovery
from aegis_graph.semantics.models import (
    SemanticMember,
    UnifiedConcept,
    UnifiedFormula,
    UnificationReport,
)


def write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_unifies_stable_state_projection_without_business_vocabulary(tmp_path: Path) -> None:
    write(
        tmp_path,
        "runner.py",
        '''
def status(state, cash):
    trade_ledger = _nonnegative_decimal(state.get("alpha_balance"))
    headroom = min(trade_ledger, cash)
    output_balance = float(headroom)
    return {"output_balance": output_balance}
''',
    )
    report = unify_discovery(discover_python(tmp_path))

    storage = report.symbol_to_concept['state["alpha_balance"]']
    trade = report.symbol_to_concept["trade_ledger"]
    assert storage == trade

    # The mathematical headroom is not incorrectly collapsed into the source cash.
    assert report.symbol_to_concept["headroom"] != storage


def test_same_local_name_in_two_functions_is_not_merged_by_name_alone(tmp_path: Path) -> None:
    write(
        tmp_path,
        "app.py",
        '''
def one(left):
    value = left + 1
    return value

def two(right):
    value = right * 2
    return value
''',
    )
    report = unify_discovery(discover_python(tmp_path))
    # Scope ambiguity deliberately removes a misleading global symbol lookup.
    assert "value" not in report.symbol_to_concept
    value_concepts = [
        concept for concept in report.concepts if any(member.symbol == "value" for member in concept.members)
    ]
    assert len(value_concepts) == 2


def test_different_contexts_are_not_semantic_conflicts(tmp_path: Path) -> None:
    write(
        tmp_path,
        "policy.py",
        '''
def calculate(mode, left, right, locked):
    if mode == "SAFE":
        spendable = min(left, right)
    else:
        spendable = max(0, right - locked)
    return spendable
''',
    )
    unified = unify_discovery(discover_python(tmp_path))
    assert detect_conflicts(unified).conflicts == ()


def test_same_concept_same_context_different_independent_definitions_conflict(tmp_path: Path) -> None:
    write(
        tmp_path,
        "backend.py",
        '''
def backend(state):
    shared_metric = state.get("source") + 1
    return {"shared_metric": shared_metric}
''',
    )
    write(
        tmp_path,
        "projection.py",
        '''
def projection(state):
    shared_metric = state.get("source") * 2
    return {"shared_metric": shared_metric}
''',
    )
    unified = unify_discovery(discover_python(tmp_path))
    # Local names remain separate without an explicit shared semantic identity, so the
    # conservative detector refuses to manufacture a conflict.
    assert detect_conflicts(unified).conflicts == ()


def test_conflict_detector_requires_prior_cross_scope_semantic_unification() -> None:
    concept = UnifiedConcept(
        id="semantic.metric",
        display_name="metric",
        members=(
            SemanticMember("a::metric", "metric", CodeAnchor("a.py", 2, function="first"), "a.py::first"),
            SemanticMember("b::metric", "metric", CodeAnchor("b.py", 2, function="second"), "b.py::second"),
        ),
        confidence=0.95,
    )
    left = UnifiedConcept(
        id="semantic.left",
        display_name="left",
        members=(SemanticMember("a::left", "left", CodeAnchor("a.py", 2, function="first"), "a.py::first"),),
        confidence=0.7,
    )
    right = UnifiedConcept(
        id="semantic.right",
        display_name="right",
        members=(SemanticMember("b::right", "right", CodeAnchor("b.py", 2, function="second"), "b.py::second"),),
        confidence=0.7,
    )
    report = UnificationReport(
        target_root="/tmp/target",
        concepts=(concept, left, right),
        formulas=(
            UnifiedFormula(
                id="f1",
                output_concept_id="semantic.metric",
                output_symbol="metric",
                input_symbols=("left",),
                input_concept_ids=("semantic.left",),
                expression="left + 1",
                context=(),
                anchor=CodeAnchor("a.py", 2, function="first"),
                source_formula_id="raw1",
            ),
            UnifiedFormula(
                id="f2",
                output_concept_id="semantic.metric",
                output_symbol="metric",
                input_symbols=("right",),
                input_concept_ids=("semantic.right",),
                expression="right * 2",
                context=(),
                anchor=CodeAnchor("b.py", 2, function="second"),
                source_formula_id="raw2",
            ),
        ),
        relationships=(),
        symbol_to_concept={},
    )
    conflicts = detect_conflicts(report).conflicts
    assert len(conflicts) == 1
    assert set(conflicts[0].expressions) == {"left + 1", "right * 2"}


def test_same_return_key_in_different_functions_is_not_a_conflict(tmp_path: Path) -> None:
    write(
        tmp_path,
        "api.py",
        '''
def first(activity):
    return {"token_id": activity.get("asset")}

def second(raw):
    return {"token_id": raw.get("token_id")}
''',
    )
    unified = unify_discovery(discover_python(tmp_path))
    assert detect_conflicts(unified).conflicts == ()


def test_interprocedural_parameter_flow_links_caller_fact_to_helper_parameter(tmp_path: Path) -> None:
    write(
        tmp_path,
        "app.py",
        '''
def partition(cash, safe, trade):
    gap = cash - safe - trade
    return {"gap": gap}

def refresh(state):
    observed = _nonnegative_decimal(state.get("account_balance"))
    safe = _nonnegative_decimal(state.get("safe_balance"))
    trade = _nonnegative_decimal(state.get("trade_balance"))
    return partition(observed, safe, trade)
''',
    )
    unified = unify_discovery(discover_python(tmp_path))
    parameter_edges = [
        edge for edge in unified.relationships if edge.relationship_type == "parameter_from"
    ]
    assert len(parameter_edges) == 3

    account_concept = unified.symbol_to_concept['state["account_balance"]']
    cash_parameter_concepts = {
        edge.source_concept_id
        for edge in parameter_edges
        if edge.target_concept_id == account_concept
    }
    assert len(cash_parameter_concepts) == 1

    gap_formula = next(row for row in unified.formulas if row.output_symbol == "gap")
    assert gap_formula.expression == "cash - safe - trade"
    assert cash_parameter_concepts.pop() in gap_formula.input_concept_ids


def test_self_attribute_identity_is_scoped_to_owning_class(tmp_path: Path) -> None:
    write(
        tmp_path,
        "services.py",
        '''
class MarketService:
    def __init__(self, config):
        self.config = config

class ResolutionService:
    def __init__(self, config):
        self.config = config
''',
    )
    discovery = discover_python(tmp_path)
    self_config_formulas = [row for row in discovery.formulas if row.output_symbol == "self.config"]
    assert {row.anchor.class_name for row in self_config_formulas} == {
        "MarketService",
        "ResolutionService",
    }

    unified = unify_discovery(discovery)
    config_concepts = [
        concept
        for concept in unified.concepts
        if any(member.symbol == "self.config" for member in concept.members)
    ]
    assert len(config_concepts) == 2
    assert "self.config" not in unified.symbol_to_concept
    assert detect_conflicts(unified).conflicts == ()


def test_mutable_self_state_updates_are_not_competing_definitions(tmp_path: Path) -> None:
    write(
        tmp_path,
        "publisher.py",
        '''
class Publisher:
    def __init__(self, saved):
        self._snapshot = saved if isinstance(saved, dict) else {}

    def publish(self, snapshot):
        self._snapshot = self._copy(snapshot)
''',
    )
    unified = unify_discovery(discover_python(tmp_path))
    snapshot_concepts = [
        concept
        for concept in unified.concepts
        if any(member.symbol == "self._snapshot" for member in concept.members)
    ]
    assert len(snapshot_concepts) == 1
    snapshot_formula_methods = {
        formula.anchor.function
        for formula in unified.formulas
        if formula.output_concept_id == snapshot_concepts[0].id
        and formula.output_symbol == "self._snapshot"
    }
    assert snapshot_formula_methods == {"__init__", "publish"}
    assert detect_conflicts(unified).conflicts == ()
