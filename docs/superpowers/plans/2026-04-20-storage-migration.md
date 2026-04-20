# Storage Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate PlotPilot from SQLite+FAISS to SQLite+LanceDB+FalkorDBLite with Protocol-based abstraction for future PostgreSQL/LanceDB Cloud/FalkorDB Server upgrade path.

**Architecture:** Three-phase progressive migration: (1) extract Protocol interfaces from existing concrete classes, (2) implement FalkorDBLite graph store behind the new Protocol, (3) implement LanceDB vector store behind the existing VectorStore ABC. A storage factory + DI wiring selects implementations based on `STORAGE_VERSION` env var. A manual migration script converts existing data.

**Tech Stack:** Python 3.9+, FalkorDBLite (embedded graph via Cypher), LanceDB (embedded vector+FTS), existing FastAPI+SQLite+FAISS stack.

**Spec:** `docs/superpowers/specs/2026-04-20-storage-migration-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `domain/ports/__init__.py` | Ports package init |
| `domain/ports/graph_store.py` | `GraphStore` Protocol — Cypher query/execute interface |
| `domain/ports/triple_repository.py` | `TripleRepositoryProtocol` — triple CRUD + graph traversal |
| `domain/ports/vector_store.py` | `VectorStoreProtocol` — revised vector ops with filter + update_metadata |
| `infrastructure/persistence/graph/__init__.py` | Graph package init |
| `infrastructure/persistence/graph/falkordb_lite_store.py` | `FalkorDBLiteGraphStore` — GraphStore impl using falkordblite |
| `infrastructure/persistence/graph/falkordb_triple_repository.py` | `FalkorDBTripleRepository` — TripleRepositoryProtocol impl using Cypher |
| `infrastructure/persistence/lance/__init__.py` | Lance package init |
| `infrastructure/persistence/lance/lance_vector_store.py` | `LanceVectorStore` — VectorStore impl using lancedb |
| `infrastructure/config/__init__.py` | Config package init |
| `infrastructure/config/storage_factory.py` | `StorageFactory` — creates storage layer based on STORAGE_VERSION |
| `scripts/migrate_to_v2_storage.py` | CLI migration script: SQLite triples → FalkorDB, FAISS → LanceDB |
| `tests/unit/test_graph_store.py` | Unit tests for FalkorDBLiteGraphStore |
| `tests/unit/test_falkordb_triple_repository.py` | Unit tests for FalkorDBTripleRepository |
| `tests/unit/test_lance_vector_store.py` | Unit tests for LanceVectorStore |
| `tests/unit/test_storage_factory.py` | Unit tests for StorageFactory |
| `tests/integration/test_migration.py` | Integration test for full migration flow |

### Modified Files

| File | Change |
|------|--------|
| `requirements.txt` | Add `falkordblite>=0.1.0`, `lancedb>=0.6.0` |
| `domain/ai/services/vector_store.py` | Add `update_metadata`, `update_metadata_batch`, `filter` param to `search` |
| `interfaces/api/dependencies.py` | Use `StorageFactory` to create triple_repository and vector_store |
| `application/world/services/knowledge_graph_service.py` | Type hint `TripleRepository` → `TripleRepositoryProtocol` |
| `application/world/services/bible_location_triple_sync.py` | Type hint `TripleRepository` → `TripleRepositoryProtocol` |
| `application/engine/services/context_builder.py` | Type hint `triple_repository` → `TripleRepositoryProtocol` |
| `application/engine/services/background_task_service.py` | Type hint → `TripleRepositoryProtocol` |
| `application/engine/services/chapter_aftermath_pipeline.py` | Type hint → `TripleRepositoryProtocol` |
| `application/world/services/auto_bible_generator.py` | Type hint → `TripleRepositoryProtocol` |
| `.env.example` | Add `STORAGE_VERSION`, `GRAPH_DB_PATH`, `LANCE_DB_PATH` |

---

## Task 1: Add New Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add falkordblite and lancedb to requirements.txt**

Add these lines to `requirements.txt`:

```
falkordblite>=0.1.0
lancedb>=0.6.0
pyarrow>=14.0.0
```

- [ ] **Step 2: Install and verify**

Run: `pip install falkordblite lancedb pyarrow`
Expected: Successful installation, no conflicts

- [ ] **Step 3: Verify imports work**

Run: `python -c "import lancedb; from redislite.falkordb_client import FalkorDB; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add falkordblite and lancedb"
```

---

## Task 2: Create Port Interfaces (domain/ports/)

**Files:**
- Create: `domain/ports/__init__.py`
- Create: `domain/ports/graph_store.py`
- Create: `domain/ports/triple_repository.py`
- Create: `domain/ports/vector_store.py`
- Test: `tests/unit/test_ports_protocols.py`

- [ ] **Step 1: Write protocol conformance tests**

```python
# tests/unit/test_ports_protocols.py
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
    # Structural check — Protocol uses duck typing
    repo = TripleRepository.__new__(TripleRepository)
    for method_name in [
        "persist_triple_sync", "delete_triple_sync", "get_by_novel_sync",
        "get_by_entity_ids_sync", "search_by_predicate_sync", "get_recent_triples_sync",
    ]:
        assert hasattr(repo, method_name), f"Missing {method_name}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_ports_protocols.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'domain.ports'`

- [ ] **Step 3: Create domain/ports/__init__.py**

```python
# domain/ports/__init__.py
"""Domain port interfaces (Protocol classes) for storage abstraction."""
```

- [ ] **Step 4: Create domain/ports/graph_store.py**

```python
# domain/ports/graph_store.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class GraphStore(Protocol):
    """Port interface for graph database operations (Cypher-based)."""

    def query(
        self, graph_name: str, cypher: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        ...

    def execute(
        self, graph_name: str, cypher: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        ...

    def delete_graph(self, graph_name: str) -> None:
        ...
```

- [ ] **Step 5: Create domain/ports/triple_repository.py**

```python
# domain/ports/triple_repository.py
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from domain.bible.triple import Triple


@runtime_checkable
class TripleRepositoryProtocol(Protocol):
    """Port interface for knowledge-graph triple persistence."""

    def persist_triple_sync(self, novel_id: str, triple: Triple) -> None:
        ...

    def delete_triple_sync(self, triple_id: str) -> bool:
        ...

    def get_by_novel_sync(self, novel_id: str) -> List[Triple]:
        ...

    def get_by_entity_ids_sync(
        self, novel_id: str, entity_ids: List[str]
    ) -> List[Triple]:
        ...

    def search_by_predicate_sync(
        self,
        novel_id: str,
        predicates: List[str],
        subject_ids: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Triple]:
        ...

    def get_recent_triples_sync(
        self,
        novel_id: str,
        chapter_number: int,
        chapter_range: int = 5,
        limit: int = 20,
    ) -> List[Triple]:
        ...

    def traverse_relations(
        self, novel_id: str, entity_id: str, max_hops: int = 3
    ) -> List[Triple]:
        ...
```

- [ ] **Step 6: Create domain/ports/vector_store.py**

```python
# domain/ports/vector_store.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """Port interface for vector storage with metadata filtering."""

    async def insert(
        self, collection: str, id: str, vector: List[float], payload: Dict[str, Any]
    ) -> None:
        ...

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        limit: int,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ...

    async def delete(self, collection: str, id: str) -> None:
        ...

    async def update_metadata(
        self, collection: str, id: str, metadata: Dict[str, Any]
    ) -> None:
        ...

    async def update_metadata_batch(
        self, collection: str, filter: Dict[str, Any], metadata: Dict[str, Any]
    ) -> int:
        ...

    async def create_collection(self, collection: str, dimension: int) -> None:
        ...

    async def delete_collection(self, collection: str) -> None:
        ...
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/unit/test_ports_protocols.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add domain/ports/ tests/unit/test_ports_protocols.py
git commit -m "feat(ports): add Protocol interfaces for graph, triple, and vector stores"
```

---

## Task 3: Add traverse_relations to Existing TripleRepository

**Files:**
- Modify: `infrastructure/persistence/database/triple_repository.py`
- Test: `tests/unit/test_ports_protocols.py` (already covers this)

- [ ] **Step 1: Write a test for traverse_relations on SQLite impl**

Add to `tests/unit/test_ports_protocols.py`:

```python
def test_sqlite_triple_repository_has_traverse_relations():
    from infrastructure.persistence.database.triple_repository import TripleRepository
    repo = TripleRepository.__new__(TripleRepository)
    assert hasattr(repo, "traverse_relations")
    assert callable(repo.traverse_relations)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_ports_protocols.py::test_sqlite_triple_repository_has_traverse_relations -v`
Expected: FAIL — `AssertionError`

- [ ] **Step 3: Add traverse_relations stub to TripleRepository**

Add this method to the `TripleRepository` class in `infrastructure/persistence/database/triple_repository.py`:

```python
def traverse_relations(
    self, novel_id: str, entity_id: str, max_hops: int = 3
) -> List["Triple"]:
    """Single-hop traversal for SQLite (multi-hop requires graph DB)."""
    return self.get_by_entity_ids_sync(novel_id, [entity_id])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_ports_protocols.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add infrastructure/persistence/database/triple_repository.py tests/unit/test_ports_protocols.py
git commit -m "feat(triple-repo): add traverse_relations method for Protocol conformance"
```

---

## Task 4: Implement FalkorDBLiteGraphStore

**Files:**
- Create: `infrastructure/persistence/graph/__init__.py`
- Create: `infrastructure/persistence/graph/falkordb_lite_store.py`
- Test: `tests/unit/test_graph_store.py`

- [ ] **Step 1: Write failing tests for FalkorDBLiteGraphStore**

```python
# tests/unit/test_graph_store.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_graph_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create infrastructure/persistence/graph/__init__.py**

```python
# infrastructure/persistence/graph/__init__.py
```

- [ ] **Step 4: Implement FalkorDBLiteGraphStore**

```python
# infrastructure/persistence/graph/falkordb_lite_store.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from redislite.falkordb_client import FalkorDB


class FalkorDBLiteGraphStore:
    """GraphStore implementation using FalkorDBLite (embedded)."""

    def __init__(self, db_path: str):
        self._db = FalkorDB(db_path)
        self._graphs: Dict[str, Any] = {}

    def _get_graph(self, graph_name: str):
        if graph_name not in self._graphs:
            self._graphs[graph_name] = self._db.select_graph(graph_name)
        return self._graphs[graph_name]

    def query(
        self, graph_name: str, cypher: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        g = self._get_graph(graph_name)
        result = g.ro_query(cypher, params=params) if params else g.ro_query(cypher)
        if not result.result_set:
            return []
        headers = result.header
        return [
            {headers[i]: row[i] for i in range(len(headers))}
            for row in result.result_set
        ]

    def execute(
        self, graph_name: str, cypher: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        g = self._get_graph(graph_name)
        if params:
            g.query(cypher, params=params)
        else:
            g.query(cypher)

    def delete_graph(self, graph_name: str) -> None:
        g = self._get_graph(graph_name)
        g.delete()
        self._graphs.pop(graph_name, None)

    def close(self) -> None:
        self._db.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_graph_store.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add infrastructure/persistence/graph/ tests/unit/test_graph_store.py
git commit -m "feat(graph): implement FalkorDBLiteGraphStore with Cypher query/execute"
```

---

## Task 5: Implement FalkorDBTripleRepository

**Files:**
- Create: `infrastructure/persistence/graph/falkordb_triple_repository.py`
- Test: `tests/unit/test_falkordb_triple_repository.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_falkordb_triple_repository.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_falkordb_triple_repository.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement FalkorDBTripleRepository**

```python
# infrastructure/persistence/graph/falkordb_triple_repository.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.bible.triple import SourceType, Triple
from domain.ports.graph_store import GraphStore


class FalkorDBTripleRepository:
    """TripleRepositoryProtocol implementation backed by FalkorDB graph."""

    def __init__(self, graph_store: GraphStore):
        self._gs = graph_store

    def _graph_name(self, novel_id: str) -> str:
        return f"novel_{novel_id}"

    def _ensure_entity(self, novel_id: str, entity_id: str, entity_type: str, name: str = "") -> None:
        self._gs.execute(
            self._graph_name(novel_id),
            "MERGE (:Entity {id: $id, entity_type: $et, name: $name, novel_id: $nid})",
            {"id": entity_id, "et": entity_type, "name": name or entity_id, "nid": novel_id},
        )

    def _triple_to_edge_params(self, triple: Triple) -> Dict[str, Any]:
        chapter_number = 0
        if triple.attributes.get("chapter_number"):
            chapter_number = int(triple.attributes["chapter_number"])
        elif triple.source_chapter_id:
            try:
                chapter_number = int(triple.source_chapter_id)
            except (ValueError, TypeError):
                pass
        return {
            "tid": triple.id,
            "pred": triple.predicate,
            "conf": triple.confidence,
            "src": triple.source_type.value if isinstance(triple.source_type, SourceType) else str(triple.source_type),
            "imp": triple.attributes.get("importance", ""),
            "desc": triple.description or "",
            "first": triple.first_appearance or "",
            "note": triple.attributes.get("note", ""),
            "ch": chapter_number,
            "created": triple.created_at.isoformat() if triple.created_at else "",
        }

    def _row_to_triple(self, row: Dict[str, Any], novel_id: str) -> Triple:
        r = row.get("r", row)
        a = row.get("a", {})
        b = row.get("b", {})
        props = r if isinstance(r, dict) else {}
        a_props = a if isinstance(a, dict) else {}
        b_props = b if isinstance(b, dict) else {}
        chapter_number = props.get("ch", 0) or props.get("chapter_number", 0)
        attrs = {"chapter_number": str(chapter_number)} if chapter_number else {}
        if props.get("note"):
            attrs["note"] = props["note"]
        if props.get("imp") or props.get("importance"):
            attrs["importance"] = props.get("imp") or props.get("importance", "")
        source_str = props.get("src", props.get("source_type", "manual"))
        try:
            source_type = SourceType(source_str)
        except (ValueError, KeyError):
            source_type = SourceType.MANUAL
        return Triple(
            id=props.get("tid", props.get("triple_id", "")),
            novel_id=novel_id,
            subject_type=a_props.get("entity_type", ""),
            subject_id=a_props.get("id", ""),
            predicate=props.get("pred", props.get("predicate", "")),
            object_type=b_props.get("entity_type", ""),
            object_id=b_props.get("id", ""),
            confidence=float(props.get("conf", props.get("confidence", 1.0))),
            source_type=source_type,
            source_chapter_id=str(chapter_number) if chapter_number else None,
            first_appearance=props.get("first", props.get("first_appearance")),
            description=props.get("desc", props.get("description")),
            attributes=attrs,
        )

    def persist_triple_sync(self, novel_id: str, triple: Triple) -> None:
        self._ensure_entity(novel_id, triple.subject_id, triple.subject_type)
        self._ensure_entity(novel_id, triple.object_id, triple.object_type)
        params = self._triple_to_edge_params(triple)
        params["sid"] = triple.subject_id
        params["oid"] = triple.object_id
        self._gs.execute(
            self._graph_name(novel_id),
            """MATCH (a:Entity {id: $sid}), (b:Entity {id: $oid})
               CREATE (a)-[:RELATION {
                   triple_id: $tid, predicate: $pred, confidence: $conf,
                   source_type: $src, importance: $imp, description: $desc,
                   first_appearance: $first, note: $note, chapter_number: $ch,
                   created_at: $created
               }]->(b)""",
            params,
        )

    def delete_triple_sync(self, triple_id: str) -> bool:
        for graph_name in self._gs.query("__meta__", "RETURN 1"):
            pass
        # Delete across all graphs — scan known graphs
        # For simplicity, we delete from all cached graphs
        deleted = False
        for gn in list(self._gs._graphs.keys()) if hasattr(self._gs, "_graphs") else []:
            try:
                self._gs.execute(
                    gn,
                    "MATCH ()-[r:RELATION {triple_id: $tid}]->() DELETE r",
                    {"tid": triple_id},
                )
                deleted = True
            except Exception:
                pass
        return deleted

    def get_by_novel_sync(self, novel_id: str) -> List[Triple]:
        rows = self._gs.query(
            self._graph_name(novel_id),
            "MATCH (a:Entity)-[r:RELATION]->(b:Entity) RETURN a, r, b",
        )
        return [self._row_to_triple(row, novel_id) for row in rows]

    def get_by_entity_ids_sync(self, novel_id: str, entity_ids: List[str]) -> List[Triple]:
        rows = self._gs.query(
            self._graph_name(novel_id),
            "MATCH (e:Entity)-[r:RELATION]-(other:Entity) WHERE e.id IN $ids RETURN e AS a, r, other AS b",
            {"ids": entity_ids},
        )
        return [self._row_to_triple(row, novel_id) for row in rows]

    def search_by_predicate_sync(
        self,
        novel_id: str,
        predicates: List[str],
        subject_ids: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Triple]:
        if subject_ids:
            rows = self._gs.query(
                self._graph_name(novel_id),
                "MATCH (a:Entity)-[r:RELATION]->(b:Entity) WHERE r.predicate IN $preds AND a.id IN $sids RETURN a, r, b LIMIT $lim",
                {"preds": predicates, "sids": subject_ids, "lim": limit},
            )
        else:
            rows = self._gs.query(
                self._graph_name(novel_id),
                "MATCH (a:Entity)-[r:RELATION]->(b:Entity) WHERE r.predicate IN $preds RETURN a, r, b LIMIT $lim",
                {"preds": predicates, "lim": limit},
            )
        return [self._row_to_triple(row, novel_id) for row in rows]

    def get_recent_triples_sync(
        self,
        novel_id: str,
        chapter_number: int,
        chapter_range: int = 5,
        limit: int = 20,
    ) -> List[Triple]:
        min_ch = chapter_number - chapter_range
        rows = self._gs.query(
            self._graph_name(novel_id),
            "MATCH (a:Entity)-[r:RELATION]->(b:Entity) WHERE r.chapter_number >= $min AND r.chapter_number <= $max RETURN a, r, b ORDER BY r.chapter_number DESC LIMIT $lim",
            {"min": min_ch, "max": chapter_number, "lim": limit},
        )
        return [self._row_to_triple(row, novel_id) for row in rows]

    def traverse_relations(
        self, novel_id: str, entity_id: str, max_hops: int = 3
    ) -> List[Triple]:
        rows = self._gs.query(
            self._graph_name(novel_id),
            "MATCH (start:Entity {id: $eid})-[r:RELATION*1.." + str(max_hops) + "]-(target:Entity) "
            "WITH start, r, target UNWIND r AS rel "
            "MATCH (a:Entity)-[rel]->(b:Entity) RETURN a, rel AS r, b",
            {"eid": entity_id},
        )
        return [self._row_to_triple(row, novel_id) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_falkordb_triple_repository.py -v`
Expected: ALL PASS (adjust `_row_to_triple` parsing if FalkorDB returns Node/Edge objects instead of dicts — see Step 5)

- [ ] **Step 5: Fix FalkorDB result parsing if needed**

FalkorDB may return `Node` and `Edge` objects instead of plain dicts. If tests fail with attribute errors, update `_row_to_triple` and `query()` in `FalkorDBLiteGraphStore` to extract `.properties` from Node/Edge objects:

```python
# In FalkorDBLiteGraphStore.query(), after getting result_set:
def _extract_value(self, val):
    if hasattr(val, "properties"):
        return val.properties
    return val
```

Then wrap each row value through `_extract_value`.

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `pytest tests/unit/test_falkordb_triple_repository.py tests/unit/test_graph_store.py tests/unit/test_ports_protocols.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add infrastructure/persistence/graph/falkordb_triple_repository.py tests/unit/test_falkordb_triple_repository.py
git commit -m "feat(graph): implement FalkorDBTripleRepository with Cypher-based triple CRUD"
```

---

## Task 6: Implement LanceVectorStore

**Files:**
- Create: `infrastructure/persistence/lance/__init__.py`
- Create: `infrastructure/persistence/lance/lance_vector_store.py`
- Test: `tests/unit/test_lance_vector_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_lance_vector_store.py
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
        _run(lance_store.insert(f"batch_coll", f"v{i}", [float(i), 0.0, 0.0, 0.0], {
            "novel_id": "n1", "chapter_number": 5, "kind": "test", "text": f"t{i}",
        }))
    count = _run(lance_store.update_metadata_batch(
        "batch_coll", {"chapter_number": 5}, {"chapter_number": 10}
    ))
    assert count == 3


def test_delete_collection(lance_store):
    _run(lance_store.create_collection("to_delete", dimension=4))
    _run(lance_store.delete_collection("to_delete"))
    # Recreating should work without error
    _run(lance_store.create_collection("to_delete", dimension=4))


def test_satisfies_protocol(lance_store):
    from domain.ports.vector_store import VectorStoreProtocol
    assert isinstance(lance_store, VectorStoreProtocol)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_lance_vector_store.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create infrastructure/persistence/lance/__init__.py**

```python
# infrastructure/persistence/lance/__init__.py
```

- [ ] **Step 4: Implement LanceVectorStore**

```python
# infrastructure/persistence/lance/lance_vector_store.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import lancedb
import pyarrow as pa


class LanceVectorStore:
    """VectorStoreProtocol implementation using LanceDB (embedded)."""

    def __init__(self, db_path: str):
        self._db = lancedb.connect(db_path)

    def _schema_for_dim(self, dimension: int) -> pa.Schema:
        return pa.schema([
            pa.field("id", pa.string()),
            pa.field("novel_id", pa.string()),
            pa.field("chapter_number", pa.int32()),
            pa.field("kind", pa.string()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), dimension)),
        ])

    def _get_or_create_table(self, collection: str, dimension: int):
        if collection in self._db.table_names():
            return self._db.open_table(collection)
        return self._db.create_table(collection, schema=self._schema_for_dim(dimension))

    def _build_filter(self, filter_dict: Dict[str, Any]) -> str:
        clauses = []
        for key, value in filter_dict.items():
            if isinstance(value, str):
                clauses.append(f"{key} = '{value}'")
            else:
                clauses.append(f"{key} = {value}")
        return " AND ".join(clauses)

    async def insert(
        self, collection: str, id: str, vector: List[float], payload: Dict[str, Any]
    ) -> None:
        table = self._get_or_create_table(collection, len(vector))
        record = {"id": id, "vector": vector}
        record["novel_id"] = payload.get("novel_id", "")
        record["chapter_number"] = payload.get("chapter_number", -1)
        record["kind"] = payload.get("kind", "")
        record["text"] = payload.get("text", "")
        table.add([record])

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        limit: int,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if collection not in self._db.table_names():
            return []
        table = self._db.open_table(collection)
        query = table.search(query_vector).limit(limit)
        if filter:
            query = query.where(self._build_filter(filter))
        results = query.to_list()
        return results

    async def delete(self, collection: str, id: str) -> None:
        if collection not in self._db.table_names():
            return
        table = self._db.open_table(collection)
        table.delete(f"id = '{id}'")

    async def update_metadata(
        self, collection: str, id: str, metadata: Dict[str, Any]
    ) -> None:
        if collection not in self._db.table_names():
            return
        table = self._db.open_table(collection)
        table.update(where=f"id = '{id}'", values=metadata)

    async def update_metadata_batch(
        self, collection: str, filter: Dict[str, Any], metadata: Dict[str, Any]
    ) -> int:
        if collection not in self._db.table_names():
            return 0
        table = self._db.open_table(collection)
        where_clause = self._build_filter(filter)
        # Count matching rows before update
        df = table.search().where(where_clause).to_pandas()
        count = len(df)
        if count > 0:
            table.update(where=where_clause, values=metadata)
        return count

    async def create_collection(self, collection: str, dimension: int) -> None:
        if collection not in self._db.table_names():
            self._db.create_table(collection, schema=self._schema_for_dim(dimension))

    async def delete_collection(self, collection: str) -> None:
        if collection in self._db.table_names():
            self._db.drop_table(collection)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_lance_vector_store.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add infrastructure/persistence/lance/ tests/unit/test_lance_vector_store.py
git commit -m "feat(lance): implement LanceVectorStore with filter, update, and batch ops"
```

---

## Task 7: Implement StorageFactory and DI Wiring

**Files:**
- Create: `infrastructure/config/__init__.py`
- Create: `infrastructure/config/storage_factory.py`
- Modify: `interfaces/api/dependencies.py`
- Modify: `.env.example`
- Test: `tests/unit/test_storage_factory.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_storage_factory.py
import os
import tempfile
import pytest


def test_factory_creates_v1_stores(monkeypatch):
    monkeypatch.setenv("STORAGE_VERSION", "v1")
    from infrastructure.config.storage_factory import StorageFactory
    factory = StorageFactory()
    triple_repo = factory.get_triple_repository()
    vector_store = factory.get_vector_store()
    from infrastructure.persistence.database.triple_repository import TripleRepository
    assert isinstance(triple_repo, TripleRepository)


def test_factory_creates_v2_stores(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_VERSION", "v2")
    monkeypatch.setenv("GRAPH_DB_PATH", str(tmp_path / "graph.db"))
    monkeypatch.setenv("LANCE_DB_PATH", str(tmp_path / "lance"))
    from infrastructure.config.storage_factory import StorageFactory
    factory = StorageFactory()
    triple_repo = factory.get_triple_repository()
    from infrastructure.persistence.graph.falkordb_triple_repository import FalkorDBTripleRepository
    assert isinstance(triple_repo, FalkorDBTripleRepository)


def test_factory_defaults_to_v1(monkeypatch):
    monkeypatch.delenv("STORAGE_VERSION", raising=False)
    from infrastructure.config.storage_factory import StorageFactory
    factory = StorageFactory()
    assert factory.version == "v1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_storage_factory.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create infrastructure/config/__init__.py**

```python
# infrastructure/config/__init__.py
```

- [ ] **Step 4: Implement StorageFactory**

```python
# infrastructure/config/storage_factory.py
from __future__ import annotations

import os
from typing import Optional

from domain.ai.services.vector_store import VectorStore


class StorageFactory:
    """Creates storage layer instances based on STORAGE_VERSION env var."""

    def __init__(self):
        self.version = os.getenv("STORAGE_VERSION", "v1")

    def get_triple_repository(self):
        if self.version == "v2":
            return self._create_v2_triple_repository()
        return self._create_v1_triple_repository()

    def get_vector_store(self) -> Optional[VectorStore]:
        if self.version == "v2":
            return self._create_v2_vector_store()
        return self._create_v1_vector_store()

    def get_graph_store(self):
        if self.version == "v2":
            return self._create_v2_graph_store()
        return None

    def _create_v1_triple_repository(self):
        from infrastructure.persistence.database.triple_repository import TripleRepository
        return TripleRepository()

    def _create_v1_vector_store(self) -> Optional[VectorStore]:
        try:
            from infrastructure.ai.chromadb_vector_store import ChromaDBVectorStore
            path = os.getenv("VECTOR_STORE_PATH", "./data/chromadb")
            return ChromaDBVectorStore(persist_directory=path)
        except ImportError:
            return None

    def _create_v2_graph_store(self):
        from infrastructure.persistence.graph.falkordb_lite_store import FalkorDBLiteGraphStore
        db_path = os.getenv("GRAPH_DB_PATH", "./data/novel_graph.db")
        return FalkorDBLiteGraphStore(db_path)

    def _create_v2_triple_repository(self):
        from infrastructure.persistence.graph.falkordb_triple_repository import FalkorDBTripleRepository
        graph_store = self._create_v2_graph_store()
        return FalkorDBTripleRepository(graph_store)

    def _create_v2_vector_store(self) -> Optional[VectorStore]:
        from infrastructure.persistence.lance.lance_vector_store import LanceVectorStore
        db_path = os.getenv("LANCE_DB_PATH", "./data/lance")
        return LanceVectorStore(db_path)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_storage_factory.py -v`
Expected: ALL PASS

- [ ] **Step 6: Update .env.example**

Add these lines to `.env.example`:

```env
# Storage Engine (v1=SQLite+FAISS, v2=SQLite+LanceDB+FalkorDBLite)
STORAGE_VERSION=v1
GRAPH_DB_PATH=./data/novel_graph.db
LANCE_DB_PATH=./data/lance
```

- [ ] **Step 7: Update dependencies.py to use StorageFactory**

In `interfaces/api/dependencies.py`, find where `TripleRepository()` is instantiated directly and replace with factory calls. Add near the top:

```python
from infrastructure.config.storage_factory import StorageFactory

_storage_factory = StorageFactory()
```

Then replace direct `TripleRepository()` instantiations with `_storage_factory.get_triple_repository()`. Replace `get_vector_store()` body to delegate to `_storage_factory.get_vector_store()` when appropriate.

- [ ] **Step 8: Run existing tests to verify no regressions**

Run: `pytest tests/ -v --timeout=60`
Expected: ALL existing tests still PASS (v1 is default)

- [ ] **Step 9: Commit**

```bash
git add infrastructure/config/ tests/unit/test_storage_factory.py interfaces/api/dependencies.py .env.example
git commit -m "feat(factory): add StorageFactory for v1/v2 storage switching via STORAGE_VERSION"
```

---

## Task 8: Update Consumer Type Hints

**Files:**
- Modify: `application/world/services/knowledge_graph_service.py`
- Modify: `application/world/services/bible_location_triple_sync.py`
- Modify: `application/engine/services/context_builder.py`
- Modify: `application/engine/services/background_task_service.py`
- Modify: `application/engine/services/chapter_aftermath_pipeline.py`
- Modify: `application/world/services/auto_bible_generator.py`

- [ ] **Step 1: Update knowledge_graph_service.py**

Change the import and type hint:

```python
# Before:
from infrastructure.persistence.database.triple_repository import TripleRepository

# After:
from domain.ports.triple_repository import TripleRepositoryProtocol
```

And in `__init__`:
```python
def __init__(self, triple_repo: TripleRepositoryProtocol, ...):
```

- [ ] **Step 2: Update bible_location_triple_sync.py**

Same pattern — replace `TripleRepository` import with `TripleRepositoryProtocol` in type hints.

- [ ] **Step 3: Update context_builder.py**

Change `triple_repository` parameter type hint to `Optional[TripleRepositoryProtocol]`.

- [ ] **Step 4: Update background_task_service.py**

Same pattern.

- [ ] **Step 5: Update chapter_aftermath_pipeline.py**

Same pattern.

- [ ] **Step 6: Update auto_bible_generator.py**

Same pattern.

- [ ] **Step 7: Run full test suite**

Run: `pytest tests/ -v --timeout=60`
Expected: ALL PASS — type hints are runtime-transparent for Protocol

- [ ] **Step 8: Commit**

```bash
git add application/world/services/knowledge_graph_service.py \
        application/world/services/bible_location_triple_sync.py \
        application/engine/services/context_builder.py \
        application/engine/services/background_task_service.py \
        application/engine/services/chapter_aftermath_pipeline.py \
        application/world/services/auto_bible_generator.py
git commit -m "refactor: update consumer type hints to TripleRepositoryProtocol"
```

---

## Task 9: Implement Migration Script

**Files:**
- Create: `scripts/migrate_to_v2_storage.py`
- Test: `tests/integration/test_migration.py`

- [ ] **Step 1: Write integration test for migration**

```python
# tests/integration/test_migration.py
import os
import shutil
import tempfile
import asyncio
import pytest


@pytest.fixture
def migration_env(tmp_path):
    """Set up a minimal v1 environment with test data."""
    # Create SQLite DB with a triple
    db_path = str(tmp_path / "novels.db")
    import sqlite3
    conn = sqlite3.connect(db_path)
    # Create schema
    conn.executescript("""
        CREATE TABLE novels (id TEXT PRIMARY KEY, title TEXT);
        CREATE TABLE triples (
            id TEXT PRIMARY KEY, novel_id TEXT, subject TEXT, predicate TEXT,
            object TEXT, chapter_number INTEGER, note TEXT, entity_type TEXT,
            importance TEXT, location_type TEXT, description TEXT,
            first_appearance INTEGER, confidence REAL, source_type TEXT,
            subject_entity_id TEXT, object_entity_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE triple_more_chapters (
            triple_id TEXT, novel_id TEXT, chapter_number INTEGER,
            PRIMARY KEY (triple_id, chapter_number)
        );
        CREATE TABLE triple_tags (
            triple_id TEXT, tag TEXT, PRIMARY KEY (triple_id, tag)
        );
        CREATE TABLE triple_attr (
            triple_id TEXT, attr_key TEXT, attr_value TEXT,
            PRIMARY KEY (triple_id, attr_key)
        );
        CREATE TABLE triple_provenance (
            id TEXT PRIMARY KEY, triple_id TEXT, novel_id TEXT,
            story_node_id TEXT, chapter_element_id TEXT,
            rule_id TEXT, role TEXT DEFAULT 'primary',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("INSERT INTO novels VALUES ('n1', 'Test Novel')")
    conn.execute("""INSERT INTO triples VALUES (
        't1', 'n1', 'Alice', 'knows', 'Bob', 3, 'note1', 'character',
        'high', NULL, 'Alice knows Bob', 3, 0.9, 'chapter_inferred',
        'char_alice', 'char_bob', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )""")
    conn.execute("INSERT INTO triple_tags VALUES ('t1', 'friendship')")
    conn.execute("INSERT INTO triple_more_chapters VALUES ('t1', 'n1', 5)")
    conn.commit()
    conn.close()

    graph_path = str(tmp_path / "graph.db")
    lance_path = str(tmp_path / "lance")

    return {
        "db_path": db_path,
        "graph_path": graph_path,
        "lance_path": lance_path,
        "novel_ids": ["n1"],
    }


def test_migrate_knowledge_graph(migration_env):
    from scripts.migrate_to_v2_storage import StorageMigration
    migration = StorageMigration(
        sqlite_db_path=migration_env["db_path"],
        graph_db_path=migration_env["graph_path"],
        lance_db_path=migration_env["lance_path"],
    )
    migration.migrate_knowledge_graph("n1")

    # Verify data in FalkorDB
    from infrastructure.persistence.graph.falkordb_lite_store import FalkorDBLiteGraphStore
    gs = FalkorDBLiteGraphStore(migration_env["graph_path"])
    results = gs.query("novel_n1", "MATCH (a)-[r:RELATION]->(b) RETURN r.triple_id")
    assert len(results) == 1
    assert results[0]["r.triple_id"] == "t1"
    gs.close()


def test_full_migration_run(migration_env):
    from scripts.migrate_to_v2_storage import StorageMigration
    migration = StorageMigration(
        sqlite_db_path=migration_env["db_path"],
        graph_db_path=migration_env["graph_path"],
        lance_db_path=migration_env["lance_path"],
    )
    migration.run(novel_ids=["n1"])
    assert migration.is_complete()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_migration.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement migration script**

```python
# scripts/migrate_to_v2_storage.py
"""
Migration script: SQLite triples + FAISS → FalkorDBLite + LanceDB

Usage:
    python -m scripts.migrate_to_v2_storage [--novel-id NOVEL_ID]
    
Or triggered via API/UI.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))


class StorageMigration:
    def __init__(
        self,
        sqlite_db_path: str = "./data/novels.db",
        graph_db_path: str = "./data/novel_graph.db",
        lance_db_path: str = "./data/lance",
        faiss_path: str = "./data/chromadb",
    ):
        self._sqlite_path = sqlite_db_path
        self._graph_path = graph_db_path
        self._lance_path = lance_db_path
        self._faiss_path = faiss_path
        self._completed = False

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_graph_store(self):
        from infrastructure.persistence.graph.falkordb_lite_store import FalkorDBLiteGraphStore
        return FalkorDBLiteGraphStore(self._graph_path)

    def _get_novel_ids(self) -> List[str]:
        conn = self._get_sqlite_conn()
        rows = conn.execute("SELECT id FROM novels").fetchall()
        conn.close()
        return [r["id"] for r in rows]

    def migrate_knowledge_graph(self, novel_id: str) -> int:
        conn = self._get_sqlite_conn()
        gs = self._get_graph_store()
        graph_name = f"novel_{novel_id}"

        # Load triples
        triples = conn.execute(
            "SELECT * FROM triples WHERE novel_id = ?", (novel_id,)
        ).fetchall()

        # Load side data
        more_chapters = {}
        for row in conn.execute(
            "SELECT triple_id, chapter_number FROM triple_more_chapters WHERE novel_id = ?",
            (novel_id,),
        ):
            more_chapters.setdefault(row["triple_id"], []).append(row["chapter_number"])

        tags = {}
        for row in conn.execute(
            """SELECT tt.triple_id, tt.tag FROM triple_tags tt
               JOIN triples t ON t.id = tt.triple_id WHERE t.novel_id = ?""",
            (novel_id,),
        ):
            tags.setdefault(row["triple_id"], []).append(row["tag"])

        # Create entities and relations
        entities_seen: Set[str] = set()
        count = 0

        for t in triples:
            sid = t["subject_entity_id"] or t["subject"]
            oid = t["object_entity_id"] or t["object"]

            if sid not in entities_seen:
                gs.execute(graph_name,
                    "MERGE (:Entity {id: $id, name: $name, entity_type: $et, novel_id: $nid})",
                    {"id": sid, "name": t["subject"], "et": t["entity_type"] or "unknown", "nid": novel_id})
                entities_seen.add(sid)

            if oid not in entities_seen:
                gs.execute(graph_name,
                    "MERGE (:Entity {id: $id, name: $name, entity_type: $et, novel_id: $nid})",
                    {"id": oid, "name": t["object"], "et": "unknown", "nid": novel_id})
                entities_seen.add(oid)

            gs.execute(graph_name,
                """MATCH (a:Entity {id: $sid}), (b:Entity {id: $oid})
                   CREATE (a)-[:RELATION {
                       triple_id: $tid, predicate: $pred, confidence: $conf,
                       source_type: $src, importance: $imp, description: $desc,
                       first_appearance: $first, note: $note, chapter_number: $ch,
                       created_at: $created
                   }]->(b)""",
                {
                    "sid": sid, "oid": oid, "tid": t["id"],
                    "pred": t["predicate"], "conf": t["confidence"] or 1.0,
                    "src": t["source_type"] or "manual",
                    "imp": t["importance"] or "",
                    "desc": t["description"] or "",
                    "first": t["first_appearance"] or 0,
                    "note": t["note"] or "",
                    "ch": t["chapter_number"] or 0,
                    "created": t["created_at"] or "",
                })
            count += 1

        gs.close()
        conn.close()
        return count

    def migrate_vectors(self, novel_id: str) -> int:
        """Migrate FAISS vectors to LanceDB."""
        import lancedb
        db = lancedb.connect(self._lance_path)
        count = 0

        # Scan FAISS collections for this novel
        if not os.path.isdir(self._faiss_path):
            return 0

        for coll_name in os.listdir(self._faiss_path):
            if novel_id not in coll_name:
                continue
            coll_dir = os.path.join(self._faiss_path, coll_name)
            meta_path = os.path.join(coll_dir, "metadata.json")
            if not os.path.exists(meta_path):
                continue

            with open(meta_path, "r") as f:
                metadata = json.load(f)

            # Extract vectors from FAISS index
            index_path = os.path.join(coll_dir, "index.faiss")
            if not os.path.exists(index_path):
                continue

            try:
                import faiss
                import numpy as np
                index = faiss.read_index(index_path)
                n = index.ntotal
                dim = index.d
                vectors = faiss.rev_swig_ptr(index.get_xb(), n * dim).reshape(n, dim)
            except (ImportError, Exception):
                continue

            records = []
            for vec_id, meta in metadata.items():
                idx = meta.get("idx", 0)
                if idx >= n:
                    continue
                payload = meta.get("payload", {})
                records.append({
                    "id": vec_id,
                    "vector": vectors[idx].tolist(),
                    "novel_id": payload.get("novel_id", novel_id),
                    "chapter_number": payload.get("chapter_number", -1),
                    "kind": payload.get("kind", ""),
                    "text": payload.get("text", ""),
                })

            if records:
                if coll_name in db.table_names():
                    db.drop_table(coll_name)
                db.create_table(coll_name, data=records)
                count += len(records)

        return count

    def run(self, novel_ids: Optional[List[str]] = None) -> Dict[str, int]:
        if novel_ids is None:
            novel_ids = self._get_novel_ids()

        results = {}
        for novel_id in novel_ids:
            graph_count = self.migrate_knowledge_graph(novel_id)
            vec_count = self.migrate_vectors(novel_id)
            results[novel_id] = {"triples": graph_count, "vectors": vec_count}

        self._mark_complete()
        return results

    def _mark_complete(self):
        self._completed = True
        config_path = os.path.join(os.path.dirname(self._sqlite_path), ".migration_complete")
        with open(config_path, "w") as f:
            f.write("v2")

    def is_complete(self) -> bool:
        return self._completed


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate PlotPilot storage to v2")
    parser.add_argument("--novel-id", help="Migrate specific novel only")
    parser.add_argument("--db-path", default="./data/novels.db")
    parser.add_argument("--graph-path", default="./data/novel_graph.db")
    parser.add_argument("--lance-path", default="./data/lance")
    args = parser.parse_args()

    migration = StorageMigration(
        sqlite_db_path=args.db_path,
        graph_db_path=args.graph_path,
        lance_db_path=args.lance_path,
    )
    novel_ids = [args.novel_id] if args.novel_id else None
    results = migration.run(novel_ids)
    for nid, counts in results.items():
        print(f"  {nid}: {counts['triples']} triples, {counts['vectors']} vectors migrated")
    print("Migration complete.")
```

- [ ] **Step 4: Run integration tests**

Run: `pytest tests/integration/test_migration.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_to_v2_storage.py tests/integration/test_migration.py
git commit -m "feat(migration): add v1→v2 storage migration script (SQLite+FAISS → FalkorDB+LanceDB)"
```

---

## Task 10: Add Migration API Endpoint

**Files:**
- Modify: `interfaces/api/v1/` (add migration route)
- Create: `interfaces/api/v1/system/migration_routes.py`

- [ ] **Step 1: Create migration route**

```python
# interfaces/api/v1/system/migration_routes.py
from __future__ import annotations

import os
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/system", tags=["system"])


class MigrationStatus(BaseModel):
    status: str
    message: str
    details: dict = {}


_migration_state = {"running": False, "result": None}


@router.post("/migrate-storage", response_model=MigrationStatus)
async def trigger_migration(background_tasks: BackgroundTasks, novel_id: str = None):
    if _migration_state["running"]:
        raise HTTPException(status_code=409, detail="Migration already in progress")

    _migration_state["running"] = True
    _migration_state["result"] = None

    def run_migration():
        try:
            from scripts.migrate_to_v2_storage import StorageMigration
            migration = StorageMigration()
            novel_ids = [novel_id] if novel_id else None
            result = migration.run(novel_ids)
            _migration_state["result"] = {"success": True, "details": result}
        except Exception as e:
            _migration_state["result"] = {"success": False, "error": str(e)}
        finally:
            _migration_state["running"] = False

    background_tasks.add_task(run_migration)
    return MigrationStatus(status="started", message="Migration started in background")


@router.get("/migrate-storage/status", response_model=MigrationStatus)
async def migration_status():
    if _migration_state["running"]:
        return MigrationStatus(status="running", message="Migration in progress")
    if _migration_state["result"] is None:
        return MigrationStatus(status="idle", message="No migration has been run")
    if _migration_state["result"].get("success"):
        return MigrationStatus(
            status="complete", message="Migration finished",
            details=_migration_state["result"].get("details", {})
        )
    return MigrationStatus(
        status="failed", message=_migration_state["result"].get("error", "Unknown error")
    )
```

- [ ] **Step 2: Register route in main app**

In `interfaces/main.py`, add:

```python
from interfaces.api.v1.system.migration_routes import router as migration_router
app.include_router(migration_router, prefix="/api/v1")
```

- [ ] **Step 3: Run server smoke test**

Run: `python -c "from interfaces.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add interfaces/api/v1/system/ interfaces/main.py
git commit -m "feat(api): add /api/v1/system/migrate-storage endpoint for manual migration trigger"
```

---

## Task 11: Final Integration Test and Verification

**Files:**
- Test: `tests/integration/test_v2_full_stack.py`

- [ ] **Step 1: Write end-to-end integration test**

```python
# tests/integration/test_v2_full_stack.py
"""Verify that the full v2 stack works end-to-end."""
import os
import shutil
import tempfile
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

    # Create chain: A -> B -> C
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
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/integration/test_v2_full_stack.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite to verify no regressions**

Run: `pytest tests/ -v --timeout=120`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_v2_full_stack.py
git commit -m "test: add v2 full-stack integration tests for triple repo + vector store"
```

---

## Summary

| Task | Component | Key Deliverable |
|------|-----------|----------------|
| 1 | Dependencies | `falkordblite`, `lancedb` in requirements.txt |
| 2 | Port Interfaces | `domain/ports/` with 3 Protocol classes |
| 3 | SQLite Conformance | `traverse_relations` on existing TripleRepository |
| 4 | Graph Store | `FalkorDBLiteGraphStore` — Cypher query/execute |
| 5 | Triple Repository | `FalkorDBTripleRepository` — full CRUD via Cypher |
| 6 | Vector Store | `LanceVectorStore` — insert/search/filter/update |
| 7 | Storage Factory | `StorageFactory` — v1/v2 switching via env var |
| 8 | Consumer Refactor | Type hints → `TripleRepositoryProtocol` |
| 9 | Migration Script | `scripts/migrate_to_v2_storage.py` |
| 10 | Migration API | `/api/v1/system/migrate-storage` endpoint |
| 11 | Integration Tests | End-to-end v2 stack verification |
