"""Per-visitor design storage (SQLite, one current design per visitor)."""


import json
import sqlite3
import time
from pathlib import Path

from . import simulator as sc
from ..settings import get_settings

SCHEMA = """CREATE TABLE IF NOT EXISTS designs (
    visitor_id TEXT PRIMARY KEY, design TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL)"""


class DesignStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        with self._conn() as c:
            c.execute(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def get(self, visitor_id: str) -> tuple[dict | None, int]:
        with self._conn() as c:
            row = c.execute("SELECT design, version FROM designs WHERE visitor_id=?", (visitor_id,)).fetchone()
        return (json.loads(row[0]), row[1]) if row else (None, 0)

    def put(self, visitor_id: str, design: dict) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO designs (visitor_id, design, version, updated_at) VALUES (?,?,1,?) "
                      "ON CONFLICT(visitor_id) DO UPDATE SET design=excluded.design, "
                      "version=designs.version+1, updated_at=excluded.updated_at",
                      (visitor_id, json.dumps(design), time.time()))

    def delete(self, visitor_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM designs WHERE visitor_id=?", (visitor_id,))


_store: DesignStore | None = None


def get_store() -> DesignStore:
    global _store
    if _store is None:
        _store = DesignStore(get_settings().data_dir / "designs.db")
    return _store


def load_or_new(visitor_id: str) -> dict:
    d, _ = get_store().get(visitor_id)
    if d is None:
        d = sc.new_design()
        get_store().put(visitor_id, d)
    return d


