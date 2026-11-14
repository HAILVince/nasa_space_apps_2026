"""Simulation runs the user started in the main simulator, kept per visitor (the session).

One row per Start: the starting parameters (every setting, defaults filled in), the cabin model's key
results (computed here on the server), the device the run was made on, and - once the browser reports
it - the 2D fire-spread model's outcome. The AI reads them with the get_simulation_runs tool.
Only the newest KEEP runs of a visitor are kept.
"""

import json
import sqlite3
import time
from pathlib import Path

from ..settings import get_settings

KEEP = 20


class RunStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, visitor_id TEXT NOT NULL, started_at REAL NOT NULL,
                settings TEXT NOT NULL, cabin TEXT NOT NULL, device TEXT NOT NULL, spread TEXT,
                spread_at REAL)""")
            c.execute("CREATE INDEX IF NOT EXISTS runs_visitor ON runs (visitor_id, id)")

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def add(self, visitor_id: str, settings: dict, cabin: dict, device: dict) -> int:
        with self._conn() as c:
            rid = c.execute("INSERT INTO runs (visitor_id, started_at, settings, cabin, device) VALUES (?,?,?,?,?)",
                            (visitor_id, time.time(), json.dumps(settings), json.dumps(cabin), json.dumps(device))).lastrowid
            c.execute("DELETE FROM runs WHERE visitor_id=? AND id NOT IN "
                      "(SELECT id FROM runs WHERE visitor_id=? ORDER BY id DESC LIMIT ?)", (visitor_id, visitor_id, KEEP))
        return rid

    def set_spread(self, visitor_id: str, run_id: int, spread: dict) -> bool:
        """Attach the 2D model's outcome to one of THIS visitor's runs; False if it is not theirs."""
        with self._conn() as c:
            cur = c.execute("UPDATE runs SET spread=?, spread_at=? WHERE id=? AND visitor_id=?",
                            (json.dumps(spread), time.time(), run_id, visitor_id))
        return cur.rowcount == 1

    def latest(self, visitor_id: str, limit: int = 5) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id, started_at, settings, cabin, device, spread FROM runs WHERE visitor_id=? "
                             "ORDER BY id DESC LIMIT ?", (visitor_id, max(1, min(int(limit), KEEP)))).fetchall()
        return [{"run_id": r[0], "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r[1])),
                 "settings": json.loads(r[2]), "cabin_3d": json.loads(r[3]), "device": json.loads(r[4]),
                 "spread_2d": json.loads(r[5]) if r[5] else None} for r in rows]

    def delete(self, visitor_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM runs WHERE visitor_id=?", (visitor_id,))


_store: RunStore | None = None


def get_runs() -> RunStore:
    global _store
    if _store is None:
        _store = RunStore(get_settings().data_dir / "sim_runs.db")
    return _store
