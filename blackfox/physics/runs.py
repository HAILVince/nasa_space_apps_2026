"""Simulation runs the user started in the main simulator, kept per visitor (the session).

One row per Start: the starting parameters (every setting, defaults filled in), the cabin model's key
results (computed here on the server), the device the run was made on, and - once the browser reports
it - the 2D fire-spread model's outcome. The SI reads them with the get_simulation_runs tool.
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
            if "outcomes" not in [r[1] for r in c.execute("PRAGMA table_info(runs)")]:
                c.execute("ALTER TABLE runs ADD COLUMN outcomes TEXT")     # CFD results, one per model

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

    def set_outcome(self, visitor_id: str, run_id: int, model: str, outcome: dict) -> bool:
        """Attach one CFD model's result (cfd_habitat, cfd_spacecraft...) to one of THIS visitor's runs."""
        with self._conn() as c:
            row = c.execute("SELECT outcomes FROM runs WHERE id=? AND visitor_id=?", (run_id, visitor_id)).fetchone()
            if row is None:
                return False
            data = json.loads(row[0]) if row[0] else {}
            data[model] = outcome
            c.execute("UPDATE runs SET outcomes=? WHERE id=?", (json.dumps(data), run_id))
        return True

    def latest(self, visitor_id: str, limit: int = 5) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id, started_at, settings, cabin, device, spread, outcomes FROM runs WHERE visitor_id=? "
                             "ORDER BY id DESC LIMIT ?", (visitor_id, max(1, min(int(limit), KEEP)))).fetchall()
        return [{"run_id": r[0], "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r[1])),
                 "settings": json.loads(r[2]), "cabin_3d": json.loads(r[3]), "device": json.loads(r[4]),
                 "spread_2d": json.loads(r[5]) if r[5] else None, "cfd": json.loads(r[6]) if r[6] else {}} for r in rows]

    def delete(self, visitor_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM runs WHERE visitor_id=?", (visitor_id,))


_store: RunStore | None = None


def get_runs() -> RunStore:
    global _store
    if _store is None:
        _store = RunStore(get_settings().data_dir / "sim_runs.db")
    return _store
