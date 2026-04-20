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

    @staticmethod
    def _extract_value(val: Any) -> Any:
        """Convert FalkorDB Node/Edge objects to dicts."""
        if hasattr(val, "properties"):
            return val.properties
        return val

    def query(
        self, graph_name: str, cypher: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        g = self._get_graph(graph_name)
        try:
            result = g.ro_query(cypher, params=params) if params else g.ro_query(cypher)
        except Exception as e:
            if "empty key" in str(e):
                return []
            raise
        if not result.result_set:
            return []
        # Headers are [[type_int, column_name], ...]
        headers = [h[1] for h in result.header]
        return [
            {headers[i]: self._extract_value(row[i]) for i in range(len(headers))}
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
