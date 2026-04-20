from __future__ import annotations
import os
from typing import Optional


class StorageFactory:
    """Creates storage layer instances based on STORAGE_VERSION env var."""

    def __init__(self):
        self.version = os.getenv("STORAGE_VERSION", "v1")

    def get_triple_repository(self):
        if self.version == "v2":
            return self._create_v2_triple_repository()
        return self._create_v1_triple_repository()

    def get_vector_store(self):
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

    def _create_v1_vector_store(self):
        try:
            from infrastructure.ai.chromadb_vector_store import ChromaDBVectorStore
            path = os.getenv("VECTOR_STORE_PATH", "./data/chromadb")
            return ChromaDBVectorStore(persist_directory=path)
        except (ImportError, Exception):
            return None

    def _create_v2_graph_store(self):
        from infrastructure.persistence.graph.falkordb_lite_store import FalkorDBLiteGraphStore
        db_path = os.getenv("GRAPH_DB_PATH", "./data/novel_graph.db")
        return FalkorDBLiteGraphStore(db_path)

    def _create_v2_triple_repository(self):
        from infrastructure.persistence.graph.falkordb_triple_repository import FalkorDBTripleRepository
        graph_store = self._create_v2_graph_store()
        return FalkorDBTripleRepository(graph_store)

    def _create_v2_vector_store(self):
        from infrastructure.persistence.lance.lance_vector_store import LanceVectorStore
        db_path = os.getenv("LANCE_DB_PATH", "./data/lance")
        return LanceVectorStore(db_path)
