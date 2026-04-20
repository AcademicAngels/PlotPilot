import os
import tempfile

import pytest


@pytest.fixture
def graph_store():
    tmp = tempfile.mktemp(suffix=".db")
    from infrastructure.persistence.graph.falkordb_lite_store import FalkorDBLiteGraphStore
    store = FalkorDBLiteGraphStore(tmp)
    yield store
    store.close()
    if os.path.exists(tmp):
        os.unlink(tmp)


def test_execute_and_query_create_node(graph_store):
    graph_store.execute("test_graph", "CREATE (:Person {name: $name})", {"name": "Alice"})
    results = graph_store.query("test_graph", "MATCH (p:Person) RETURN p.name")
    assert len(results) == 1
    assert results[0]["p.name"] == "Alice"


def test_execute_create_relationship(graph_store):
    graph_store.execute("test_graph", "CREATE (:Person {name: 'A'})")
    graph_store.execute("test_graph", "CREATE (:Person {name: 'B'})")
    graph_store.execute(
        "test_graph",
        "MATCH (a:Person {name: 'A'}), (b:Person {name: 'B'}) CREATE (a)-[:KNOWS]->(b)",
    )
    results = graph_store.query(
        "test_graph", "MATCH (a)-[:KNOWS]->(b) RETURN a.name, b.name"
    )
    assert len(results) == 1
    assert results[0]["a.name"] == "A"
    assert results[0]["b.name"] == "B"


def test_delete_graph(graph_store):
    graph_store.execute("test_graph", "CREATE (:Node {id: 1})")
    graph_store.delete_graph("test_graph")
    results = graph_store.query("test_graph", "MATCH (n) RETURN n")
    assert len(results) == 0


def test_query_with_params(graph_store):
    graph_store.execute("test_graph", "CREATE (:Item {val: $v})", {"v": 42})
    results = graph_store.query("test_graph", "MATCH (i:Item {val: $v}) RETURN i.val", {"v": 42})
    assert results[0]["i.val"] == 42


def test_satisfies_protocol(graph_store):
    from domain.ports.graph_store import GraphStore
    assert isinstance(graph_store, GraphStore)
