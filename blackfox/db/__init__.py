"""Research database factory. Add a backend: implement base.ResearchStore and
register it in BACKENDS; select it with BLACKFOX_DB_BACKEND."""

from ..settings import get_settings
from .base import GRAVITIES, KINDS, ResearchStore


def _json():
    from .json_store import JsonResearchStore
    s = get_settings()
    return JsonResearchStore(s.knowledge_dir, s.data_dir, s.fulltext_dir)


BACKENDS = {"json": _json, "sqlite": _json}     # "sqlite" was the old default; an old env value must not break the tools
_store: ResearchStore | None = None


def get_store() -> ResearchStore:
    global _store
    if _store is None:
        _store = BACKENDS[get_settings().db_backend]()
    return _store


__all__ = ["get_store", "ResearchStore", "KINDS", "GRAVITIES", "BACKENDS"]
