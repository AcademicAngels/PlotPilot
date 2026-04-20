import os
import tempfile
from datetime import datetime
import pytest
from domain.bible.triple import Triple, SourceType


@pytest.fixture
def triple_repo():
    tmp = tempfile.mktemp(suffix=".db")
    from infrastructure.persistence.graph.falkordb_lite_store import FalkorDBLiteGraphStore
    from infrastructure.persistence.graph.falkordb_triple_repository import FalkorDBTripleRepository
    graph_store = FalkorDBLiteGraphStore(tmp)
    repo = FalkorDBTripleRepository(graph_store)
    yield repo
    graph_store.close()
    if os.path.exists(tmp):
        os.unlink(tmp)


def _make_triple(
    novel_id="novel_1",
    subject_id="char_alice",
    subject_type="character",
    predicate="knows",
    object_id="char_bob",
    object_type="character",
    chapter_number=1,
    triple_id=None,
) -> Triple:
    return Triple(
        id=triple_id or f"t_{subject_id}_{predicate}_{object_id}",
        novel_id=novel_id,
        subject_type=subject_type,
        subject_id=subject_id,
        predicate=predicate,
        object_type=object_type,
        object_id=object_id,
        confidence=0.9,
        source_type=SourceType.CHAPTER_INFERRED,
        source_chapter_id=str(chapter_number),
        first_appearance=str(chapter_number),
        related_chapters=[str(chapter_number)],
        description=f"{subject_id} {predicate} {object_id}",
        tags=["test"],
        attributes={"chapter_number": str(chapter_number)},
    )


def test_persist_and_get_by_novel(triple_repo):
    t = _make_triple()
    triple_repo.persist_triple_sync("novel_1", t)
    results = triple_repo.get_by_novel_sync("novel_1")
    assert len(results) >= 1
    found = [r for r in results if r.id == t.id]
    assert len(found) == 1
    assert found[0].predicate == "knows"


def test_delete_triple(triple_repo):
    t = _make_triple(triple_id="t_del")
    triple_repo.persist_triple_sync("novel_1", t)
    assert triple_repo.delete_triple_sync("t_del") is True
    results = triple_repo.get_by_novel_sync("novel_1")
    assert all(r.id != "t_del" for r in results)


def test_search_by_predicate(triple_repo):
    triple_repo.persist_triple_sync("novel_1", _make_triple(predicate="loves"))
    triple_repo.persist_triple_sync("novel_1", _make_triple(
        predicate="hates", subject_id="char_carol", object_id="char_dave",
        triple_id="t_carol_hates_dave"
    ))
    results = triple_repo.search_by_predicate_sync("novel_1", ["loves"])
    assert all(r.predicate == "loves" for r in results)


def test_get_by_entity_ids(triple_repo):
    triple_repo.persist_triple_sync("novel_1", _make_triple())
    results = triple_repo.get_by_entity_ids_sync("novel_1", ["char_alice"])
    assert len(results) >= 1


def test_get_recent_triples(triple_repo):
    for ch in [1, 5, 10]:
        triple_repo.persist_triple_sync("novel_1", _make_triple(
            chapter_number=ch,
            triple_id=f"t_ch{ch}",
            subject_id=f"s{ch}",
            object_id=f"o{ch}",
        ))
    results = triple_repo.get_recent_triples_sync("novel_1", chapter_number=10, chapter_range=5)
    chapters = [int(r.attributes.get("chapter_number", 0)) for r in results]
    assert all(ch >= 5 for ch in chapters)


def test_traverse_relations(triple_repo):
    triple_repo.persist_triple_sync("novel_1", _make_triple(
        subject_id="a", object_id="b", triple_id="t_ab"
    ))
    triple_repo.persist_triple_sync("novel_1", _make_triple(
        subject_id="b", object_id="c", triple_id="t_bc"
    ))
    results = triple_repo.traverse_relations("novel_1", "a", max_hops=2)
    entity_ids = set()
    for r in results:
        entity_ids.add(r.subject_id)
        entity_ids.add(r.object_id)
    assert "b" in entity_ids


def test_satisfies_protocol(triple_repo):
    from domain.ports.triple_repository import TripleRepositoryProtocol
    assert isinstance(triple_repo, TripleRepositoryProtocol)
