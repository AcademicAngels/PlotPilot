import os
import tempfile
import pytest


def _has_redislite():
    try:
        import redislite  # noqa: F401
        return True
    except ImportError:
        return False


def test_factory_creates_v1_stores(monkeypatch):
    monkeypatch.setenv("STORAGE_VERSION", "v1")
    from infrastructure.config.storage_factory import StorageFactory
    factory = StorageFactory()
    triple_repo = factory.get_triple_repository()
    from infrastructure.persistence.database.triple_repository import TripleRepository
    assert isinstance(triple_repo, TripleRepository)


@pytest.mark.skipif(
    not _has_redislite(),
    reason="redislite/falkordblite not installed"
)
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
