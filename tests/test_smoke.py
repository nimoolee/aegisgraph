from aegis_graph import __version__
from aegis_graph.core import ChangeType, FactNode


def test_package_version() -> None:
    assert __version__ == "1.0.0"


def test_fact_node_has_semantic_identity() -> None:
    node = FactNode(id="cash.available", name="Available Cash")
    assert node.id == "cash.available"


def test_temporal_change_is_first_class_change_type() -> None:
    assert ChangeType.TEMPORAL_CHANGE.value == "temporal_change"
