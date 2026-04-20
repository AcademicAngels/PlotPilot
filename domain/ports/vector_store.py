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
