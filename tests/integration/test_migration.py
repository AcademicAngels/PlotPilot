import os
import shutil
import tempfile
import pytest


@pytest.fixture
def migration_env(tmp_path):
    """Set up a minimal v1 environment with test data."""
    db_path = str(tmp_path / "novels.db")
    import sqlite3
    conn = sqlite3.connect(db_path)
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
