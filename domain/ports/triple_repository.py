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
