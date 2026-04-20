from __future__ import annotations
from typing import Any, Dict, List, Optional

import lancedb
import pyarrow as pa


class LanceVectorStore:
    """VectorStoreProtocol implementation using LanceDB (embedded)."""

    def __init__(self, db_path: str):
        self._db = lancedb.connect(db_path)

    def _table_names(self) -> List[str]:
        return self._db.list_tables().tables

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
        if collection in self._table_names():
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

    async def create_collection(self, collection: str, dimension: int) -> None:
        if collection not in self._table_names():
            self._db.create_table(collection, schema=self._schema_for_dim(dimension))

    async def delete_collection(self, collection: str) -> None:
        if collection in self._table_names():
            self._db.drop_table(collection)

    async def insert(
        self, collection: str, id: str, vector: List[float], payload: Dict[str, Any]
    ) -> None:
        table = self._get_or_create_table(collection, len(vector))
        record = {
            "id": id,
            "vector": vector,
            "novel_id": payload.get("novel_id", ""),
            "chapter_number": payload.get("chapter_number", -1),
            "kind": payload.get("kind", ""),
            "text": payload.get("text", ""),
        }
        table.add([record])

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        limit: int,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if collection not in self._table_names():
            return []
        table = self._db.open_table(collection)
        query = table.search(query_vector).limit(limit)
        if filter:
            query = query.where(self._build_filter(filter))
        results = query.to_list()
        # Remove internal _distance field from results
        for r in results:
            r.pop("_distance", None)
        return results

    async def delete(self, collection: str, id: str) -> None:
        if collection not in self._table_names():
            return
        table = self._db.open_table(collection)
        table.delete(f"id = '{id}'")

    async def update_metadata(
        self, collection: str, id: str, metadata: Dict[str, Any]
    ) -> None:
        if collection not in self._table_names():
            return
        table = self._db.open_table(collection)
        table.update(where=f"id = '{id}'", values=metadata)

    async def update_metadata_batch(
        self, collection: str, filter: Dict[str, Any], metadata: Dict[str, Any]
    ) -> int:
        if collection not in self._table_names():
            return 0
        table = self._db.open_table(collection)
        where_clause = self._build_filter(filter)
        count = table.count_rows(filter=where_clause)
        if count > 0:
            table.update(where=where_clause, values=metadata)
        return count
