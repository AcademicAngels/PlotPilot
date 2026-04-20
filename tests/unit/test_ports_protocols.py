"""Verify that Protocol definitions are importable and structurally sound."""
import pytest
from typing import runtime_checkable, Protocol


def test_graph_store_protocol_importable():
    from domain.ports.graph_store import GraphStore
    assert hasattr(GraphStore, "query")
    assert hasattr(GraphStore, "execute")
    assert hasattr(GraphStore, "delete_graph")


def test_triple_repository_protocol_importable():
    from domain.ports.triple_repository import TripleRepositoryProtocol
    assert hasattr(TripleRepositoryProtocol, "persist_triple_sync")
    assert hasattr(TripleRepositoryProtocol, "delete_triple_sync")
    assert hasattr(TripleRepositoryProtocol, "get_by_novel_sync")
    assert hasattr(TripleRepositoryProtocol, "get_by_entity_ids_sync")
    assert hasattr(TripleRepositoryProtocol, "search_by_predicate_sync")
    assert hasattr(TripleRepositoryProtocol, "get_recent_triples_sync")
    assert hasattr(TripleRepositoryProtocol, "traverse_relations")


def test_vector_store_protocol_importable():
    from domain.ports.vector_store import VectorStoreProtocol
    assert hasattr(VectorStoreProtocol, "insert")
    assert hasattr(VectorStoreProtocol, "search")
    assert hasattr(VectorStoreProtocol, "delete")
    assert hasattr(VectorStoreProtocol, "update_metadata")
    assert hasattr(VectorStoreProtocol, "update_metadata_batch")
    assert hasattr(VectorStoreProtocol, "create_collection")
    assert hasattr(VectorStoreProtocol, "delete_collection")


def test_existing_triple_repository_satisfies_protocol():
    """The existing TripleRepository must satisfy the new Protocol."""
    from domain.ports.triple_repository import TripleRepositoryProtocol
    from infrastructure.persistence.database.triple_repository import TripleRepository
    repo = TripleRepository.__new__(TripleRepository)
    for method_name in [
        "persist_triple_sync", "delete_triple_sync", "get_by_novel_sync",
        "get_by_entity_ids_sync", "search_by_predicate_sync", "get_recent_triples_sync",
    ]:
        assert hasattr(repo, method_name), f"Missing {method_name}"


def test_sqlite_triple_repository_has_traverse_relations():
    from infrastructure.persistence.database.triple_repository import TripleRepository
    repo = TripleRepository.__new__(TripleRepository)
    assert hasattr(repo, "traverse_relations")
    assert callable(repo.traverse_relations)
