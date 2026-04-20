"""Verify that the full v2 stack works end-to-end."""
import os
import asyncio
import pytest


@pytest.fixture
def v2_env(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_VERSION", "v2")
    monkeypatch.setenv("GRAPH_DB_PATH", str(tmp_path / "graph.db"))
    monkeypatch.setenv("LANCE_DB_PATH", str(tmp_path / "lance"))
    return tmp_path


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_v2_triple_repository_crud(v2_env):
    from infrastructure.config.storage_factory import StorageFactory
    from domain.bible.triple import Triple, SourceType

    factory = StorageFactory()
    repo = factory.get_triple_repository()

    t = Triple(
        id="test_triple_1",
        novel_id="novel_test",
        subject_type="character",
        subject_id="char_a",
        predicate="loves",
        object_type="character",
        object_id="char_b",
        confidence=0.95,
        source_type=SourceType.CHAPTER_INFERRED,
        attributes={"chapter_number": "5"},
    )

    repo.persist_triple_sync("novel_test", t)
    results = repo.get_by_novel_sync("novel_test")
    assert len(results) >= 1
    assert any(r.id == "test_triple_1" for r in results)

    repo.delete_triple_sync("test_triple_1")
    results = repo.get_by_novel_sync("novel_test")
    assert all(r.id != "test_triple_1" for r in results)


def test_v2_vector_store_crud(v2_env):
    from infrastructure.config.storage_factory import StorageFactory

    factory = StorageFactory()
    vs = factory.get_vector_store()

    _run(vs.create_collection("test_vectors", dimension=4))
    _run(vs.insert("test_vectors", "vec_1", [1.0, 0.0, 0.0, 0.0], {
        "novel_id": "n1", "chapter_number": 1, "kind": "test", "text": "hello",
    }))

    results = _run(vs.search("test_vectors", [1.0, 0.0, 0.0, 0.0], limit=5))
    assert len(results) >= 1

    _run(vs.delete("test_vectors", "vec_1"))
    results = _run(vs.search("test_vectors", [1.0, 0.0, 0.0, 0.0], limit=5))
    assert all(r.get("id") != "vec_1" for r in results)


def test_v2_traverse_relations(v2_env):
    from infrastructure.config.storage_factory import StorageFactory
    from domain.bible.triple import Triple, SourceType

    factory = StorageFactory()
    repo = factory.get_triple_repository()

    repo.persist_triple_sync("novel_test", Triple(
        id="t_ab", novel_id="novel_test",
        subject_type="character", subject_id="a",
        predicate="knows", object_type="character", object_id="b",
        attributes={"chapter_number": "1"},
    ))
    repo.persist_triple_sync("novel_test", Triple(
        id="t_bc", novel_id="novel_test",
        subject_type="character", subject_id="b",
        predicate="knows", object_type="character", object_id="c",
        attributes={"chapter_number": "2"},
    ))

    results = repo.traverse_relations("novel_test", "a", max_hops=2)
    ids = {r.subject_id for r in results} | {r.object_id for r in results}
    assert "b" in ids
