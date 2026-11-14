"""Research database factory. Add a backend: implement base.ResearchStore and
register it in BACKENDS; select it with BLACKFOX_DB_BACKEND."""

from pathlib import Path

from ..settings import get_settings
from .base import KINDS, ResearchStore

SEED_DIR = Path(__file__).parent / "seed"


def _sqlite():
    from .sqlite_store import SQLiteResearchStore
    return SQLiteResearchStore(get_settings().data_dir / "research.db", seed_dir=SEED_DIR)


BACKENDS = {"sqlite": _sqlite}
_store: ResearchStore | None = None


def get_store() -> ResearchStore:
    global _store
    if _store is None:
        _store = BACKENDS[get_settings().db_backend]()
    return _store


__all__ = ["get_store", "ResearchStore", "KINDS", "BACKENDS"]
