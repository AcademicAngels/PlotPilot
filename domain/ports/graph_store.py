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
