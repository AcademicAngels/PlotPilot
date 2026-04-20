"""FalkorDB-backed TripleRepository implementation."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.bible.triple import SourceType, Triple
from infrastructure.persistence.graph.falkordb_lite_store import FalkorDBLiteGraphStore


class FalkorDBTripleRepository:
    """Implements TripleRepositoryProtocol using FalkorDB Cypher queries."""

    def __init__(self, graph_store: FalkorDBLiteGraphStore):
        self._gs = graph_store

    @staticmethod
    def _graph_name(novel_id: str) -> str:
        return f"novel_{novel_id}"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _ensure_entity(
        self, graph: str, entity_id: str, entity_type: str, novel_id: str
    ) -> None:
        cypher = (
            "MERGE (e:Entity {id: $eid}) "
            "ON CREATE SET e.entity_type = $etype, e.novel_id = $nid, e.name = $eid"
        )
        self._gs.execute(graph, cypher, {
            "eid": entity_id,
            "etype": entity_type,
            "nid": novel_id,
        })

    @staticmethod
    def _row_to_triple(row: Dict[str, Any]) -> Triple:
        a = row["a"]  # subject node properties dict
        b = row["b"]  # object node properties dict
        r = row["r"]  # edge properties dict

        # Parse JSON-encoded fields stored as strings on the edge
        related_chapters = r.get("related_chapters", "[]")
        if isinstance(related_chapters, str):
            try:
                related_chapters = json.loads(related_chapters)
            except (json.JSONDecodeError, TypeError):
                related_chapters = []

        tags = r.get("tags", "[]")
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        attributes = r.get("attributes", "{}")
        if isinstance(attributes, str):
            try:
                attributes = json.loads(attributes)
            except (json.JSONDecodeError, TypeError):
                attributes = {}

        created_at = r.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except (ValueError, TypeError):
                created_at = datetime.now()
        elif not isinstance(created_at, datetime):
            created_at = datetime.now()

        updated_at = r.get("updated_at")
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at)
            except (ValueError, TypeError):
                updated_at = datetime.now()
        elif not isinstance(updated_at, datetime):
            updated_at = datetime.now()

        return Triple(
            id=r.get("triple_id", ""),
            novel_id=a.get("novel_id", ""),
            subject_type=a.get("entity_type", ""),
            subject_id=a.get("id", ""),
            predicate=r.get("predicate", ""),
            object_type=b.get("entity_type", ""),
            object_id=b.get("id", ""),
            confidence=float(r.get("confidence", 1.0)),
            source_type=SourceType(r.get("source_type", "manual")),
            source_chapter_id=r.get("source_chapter_id"),
            first_appearance=r.get("first_appearance"),
            related_chapters=related_chapters,
            description=r.get("description"),
            tags=tags,
            attributes=attributes,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ------------------------------------------------------------------
    # persist
    # ------------------------------------------------------------------

    def persist_triple_sync(self, novel_id: str, triple: Triple) -> None:
        g = self._graph_name(novel_id)
        # Ensure subject and object entity nodes exist
        self._ensure_entity(g, triple.subject_id, triple.subject_type, novel_id)
        self._ensure_entity(g, triple.object_id, triple.object_type, novel_id)

        now = datetime.now().isoformat()
        cypher = (
            "MATCH (a:Entity {id: $sid}), (b:Entity {id: $oid}) "
            "MERGE (a)-[r:RELATION {triple_id: $tid}]->(b) "
            "SET r.predicate = $pred, "
            "r.confidence = $conf, "
            "r.source_type = $stype, "
            "r.source_chapter_id = $schap, "
            "r.first_appearance = $fapp, "
            "r.related_chapters = $rchaps, "
            "r.description = $desc, "
            "r.tags = $tags, "
            "r.attributes = $attrs, "
            "r.chapter_number = $chnum, "
            "r.created_at = $cat, "
            "r.updated_at = $uat"
        )
        self._gs.execute(g, cypher, {
            "sid": triple.subject_id,
            "oid": triple.object_id,
            "tid": triple.id,
            "pred": triple.predicate,
            "conf": triple.confidence,
            "stype": triple.source_type.value,
            "schap": triple.source_chapter_id or "",
            "fapp": triple.first_appearance or "",
            "rchaps": json.dumps(triple.related_chapters),
            "desc": triple.description or "",
            "tags": json.dumps(triple.tags),
            "attrs": json.dumps(triple.attributes),
            "chnum": triple.attributes.get("chapter_number", "0"),
            "cat": now,
            "uat": now,
        })

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    def delete_triple_sync(self, triple_id: str) -> bool:
        for gname in list(self._gs._graphs.keys()):
            try:
                self._gs.execute(
                    gname,
                    "MATCH ()-[r:RELATION {triple_id: $tid}]->() DELETE r",
                    {"tid": triple_id},
                )
            except Exception:
                continue
        return True

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def get_by_novel_sync(self, novel_id: str) -> List[Triple]:
        g = self._graph_name(novel_id)
        cypher = (
            "MATCH (a:Entity)-[r:RELATION]->(b:Entity) "
            "RETURN a, r, b"
        )
        rows = self._gs.query(g, cypher)
        return [self._row_to_triple(row) for row in rows]

    def get_by_entity_ids_sync(
        self, novel_id: str, entity_ids: List[str]
    ) -> List[Triple]:
        g = self._graph_name(novel_id)
        # FalkorDB may not support IN with list params well,
        # use ANY() predicate instead
        cypher = (
            "MATCH (a:Entity)-[r:RELATION]->(b:Entity) "
            "WHERE ANY(x IN $eids WHERE a.id = x OR b.id = x) "
            "RETURN a, r, b"
        )
        rows = self._gs.query(g, cypher, {"eids": entity_ids})
        return [self._row_to_triple(row) for row in rows]

    def search_by_predicate_sync(
        self,
        novel_id: str,
        predicates: List[str],
        subject_ids: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Triple]:
        g = self._graph_name(novel_id)
        cypher = (
            "MATCH (a:Entity)-[r:RELATION]->(b:Entity) "
            "WHERE ANY(x IN $preds WHERE r.predicate = x) "
        )
        params: Dict[str, Any] = {"preds": predicates}
        if subject_ids:
            cypher += "AND ANY(x IN $sids WHERE a.id = x) "
            params["sids"] = subject_ids
        # FalkorDB may not support parameterised LIMIT; inline it
        cypher += f"RETURN a, r, b LIMIT {int(limit)}"
        rows = self._gs.query(g, cypher, params)
        return [self._row_to_triple(row) for row in rows]

    def get_recent_triples_sync(
        self,
        novel_id: str,
        chapter_number: int,
        chapter_range: int = 5,
        limit: int = 20,
    ) -> List[Triple]:
        g = self._graph_name(novel_id)
        min_chapter = chapter_number - chapter_range
        # chapter_number is stored as string on the edge
        cypher = (
            "MATCH (a:Entity)-[r:RELATION]->(b:Entity) "
            "WHERE toInteger(r.chapter_number) >= $minch "
            f"RETURN a, r, b LIMIT {int(limit)}"
        )
        rows = self._gs.query(g, cypher, {"minch": min_chapter})
        return [self._row_to_triple(row) for row in rows]

    def traverse_relations(
        self, novel_id: str, entity_id: str, max_hops: int = 3
    ) -> List[Triple]:
        g = self._graph_name(novel_id)
        seen_triple_ids: set = set()
        result: List[Triple] = []
        frontier = {entity_id}

        for _ in range(max_hops):
            if not frontier:
                break
            # Query 1-hop from all frontier entities
            cypher = (
                "MATCH (a:Entity)-[r:RELATION]-(b:Entity) "
                "WHERE ANY(x IN $eids WHERE a.id = x) "
                "RETURN a, r, b"
            )
            rows = self._gs.query(g, cypher, {"eids": list(frontier)})
            next_frontier: set = set()
            for row in rows:
                t = self._row_to_triple(row)
                if t.id not in seen_triple_ids:
                    seen_triple_ids.add(t.id)
                    result.append(t)
                    next_frontier.add(t.subject_id)
                    next_frontier.add(t.object_id)
            # Only expand to truly new entities
            next_frontier -= {eid for t in result for eid in (t.subject_id, t.object_id) if eid in frontier}
            frontier = next_frontier - frontier
        return result
