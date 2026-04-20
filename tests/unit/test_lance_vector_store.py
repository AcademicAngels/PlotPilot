import os
import shutil
import tempfile
import pytest
import asyncio


@pytest.fixture
def lance_store():
    tmp_dir = tempfile.mkdtemp(prefix="lance_test_")
    from infrastructure.persistence.lance.lance_vector_store import LanceVectorStore
    store = LanceVectorStore(tmp_dir)
    yield store
    shutil.rmtree(tmp_dir, ignore_errors=True)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_create_collection_and_insert(lance_store):
    _run(lance_store.create_collection("test_coll", dimension=4))
    _run(lance_store.insert("test_coll", "v1", [1.0, 0.0, 0.0, 0.0], {
        "novel_id": "n1", "chapter_number": 1, "kind": "chapter_summary",
        "text": "Hello world",
    }))
    results = _run(lance_store.search("test_coll", [1.0, 0.0, 0.0, 0.0], limit=5))
    assert len(results) >= 1
    assert results[0]["id"] == "v1"


def test_search_with_filter(lance_store):
    _run(lance_store.create_collection("filtered", dimension=4))
    _run(lance_store.insert("filtered", "v1", [1.0, 0.0, 0.0, 0.0], {
        "novel_id": "n1", "chapter_number": 1, "kind": "chapter_summary", "text": "a",
    }))
    _run(lance_store.insert("filtered", "v2", [0.9, 0.1, 0.0, 0.0], {
        "novel_id": "n2", "chapter_number": 2, "kind": "chapter_summary", "text": "b",
    }))
    results = _run(lance_store.search(
        "filtered", [1.0, 0.0, 0.0, 0.0], limit=5, filter={"novel_id": "n1"}
    ))
    assert all(r.get("novel_id") == "n1" for r in results)


def test_delete(lance_store):
    _run(lance_store.create_collection("del_coll", dimension=4))
    _run(lance_store.insert("del_coll", "v1", [1.0, 0.0, 0.0, 0.0], {
        "novel_id": "n1", "chapter_number": 1, "kind": "test", "text": "x",
    }))
    _run(lance_store.delete("del_coll", "v1"))
    results = _run(lance_store.search("del_coll", [1.0, 0.0, 0.0, 0.0], limit=5))
    assert all(r.get("id") != "v1" for r in results)


def test_update_metadata(lance_store):
    _run(lance_store.create_collection("upd_coll", dimension=4))
    _run(lance_store.insert("upd_coll", "v1", [1.0, 0.0, 0.0, 0.0], {
        "novel_id": "n1", "chapter_number": 1, "kind": "test", "text": "x",
    }))
    _run(lance_store.update_metadata("upd_coll", "v1", {"chapter_number": 99}))
    results = _run(lance_store.search("upd_coll", [1.0, 0.0, 0.0, 0.0], limit=1))
    assert results[0]["chapter_number"] == 99


def test_update_metadata_batch(lance_store):
    _run(lance_store.create_collection("batch_coll", dimension=4))
    for i in range(3):
        _run(lance_store.insert("batch_coll", f"v{i}", [float(i), 0.0, 0.0, 0.0], {
            "novel_id": "n1", "chapter_number": 5, "kind": "test", "text": f"t{i}",
        }))
    count = _run(lance_store.update_metadata_batch(
        "batch_coll", {"chapter_number": 5}, {"chapter_number": 10}
    ))
    assert count == 3


def test_delete_collection(lance_store):
    _run(lance_store.create_collection("to_delete", dimension=4))
    _run(lance_store.delete_collection("to_delete"))
    _run(lance_store.create_collection("to_delete", dimension=4))


def test_satisfies_protocol(lance_store):
    from domain.ports.vector_store import VectorStoreProtocol
    assert isinstance(lance_store, VectorStoreProtocol)
