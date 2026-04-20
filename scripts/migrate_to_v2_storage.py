"""
Migration script: SQLite triples + FAISS -> FalkorDBLite + LanceDB

Usage:
    python -m scripts.migrate_to_v2_storage [--novel-id NOVEL_ID]
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

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

        triples = conn.execute(
            "SELECT * FROM triples WHERE novel_id = ?", (novel_id,)
        ).fetchall()

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

        entities_seen: Set[str] = set()
        count = 0

        for t in triples:
            sid = t["subject_entity_id"] or t["subject"]
            oid = t["object_entity_id"] or t["object"]

            if sid not in entities_seen:
                gs.execute(
                    graph_name,
                    "MERGE (:Entity {id: $id, name: $name, entity_type: $et, novel_id: $nid})",
                    {"id": sid, "name": t["subject"], "et": t["entity_type"] or "unknown", "nid": novel_id},
                )
                entities_seen.add(sid)

            if oid not in entities_seen:
                gs.execute(
                    graph_name,
                    "MERGE (:Entity {id: $id, name: $name, entity_type: $et, novel_id: $nid})",
                    {"id": oid, "name": t["object"], "et": "unknown", "nid": novel_id},
                )
                entities_seen.add(oid)

            gs.execute(
                graph_name,
                """MATCH (a:Entity {id: $sid}), (b:Entity {id: $oid})
                   CREATE (a)-[:RELATION {
                       triple_id: $tid, predicate: $pred, confidence: $conf,
                       source_type: $src, importance: $imp, description: $desc,
                       first_appearance: $first, note: $note, chapter_number: $ch,
                       created_at: $created
                   }]->(b)""",
                {
                    "sid": sid,
                    "oid": oid,
                    "tid": t["id"],
                    "pred": t["predicate"],
                    "conf": t["confidence"] or 1.0,
                    "src": t["source_type"] or "manual",
                    "imp": t["importance"] or "",
                    "desc": t["description"] or "",
                    "first": t["first_appearance"] or 0,
                    "note": t["note"] or "",
                    "ch": t["chapter_number"] or 0,
                    "created": t["created_at"] or "",
                },
            )
            count += 1

        gs.close()
        conn.close()
        return count

    def migrate_vectors(self, novel_id: str) -> int:
        """Migrate FAISS vectors to LanceDB."""
        if not os.path.isdir(self._faiss_path):
            return 0

        import lancedb
        db = lancedb.connect(self._lance_path)
        count = 0

        for coll_name in os.listdir(self._faiss_path):
            if novel_id not in coll_name:
                continue
            coll_dir = os.path.join(self._faiss_path, coll_name)
            meta_path = os.path.join(coll_dir, "metadata.json")
            if not os.path.exists(meta_path):
                continue

            with open(meta_path, "r") as f:
                metadata = json.load(f)

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
                table_names = (
                    [t.name for t in db.list_tables().tables]
                    if hasattr(db.list_tables(), "tables")
                    else db.table_names()
                )
                if coll_name in table_names:
                    db.drop_table(coll_name)
                db.create_table(coll_name, data=records)
                count += len(records)

        return count

    def run(self, novel_ids: Optional[List[str]] = None) -> Dict[str, dict]:
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
