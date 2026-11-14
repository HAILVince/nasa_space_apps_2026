"""Per-visitor design memory: each visitor has one current design (JSON) that both the
agent tools and the typed commands edit. Stored in SQLite next to the chat memory, so a
design survives reloads and new conversations.

Typed commands (handled instantly, no LLM):
  show                         full simulation snapshot
  select <part>                show that part's properties
  set <target>.<prop> = <val>  e.g. set hab.radius_m = 3   /   set environment.crew = 6
  add <type> <name>            e.g. add solar_array solar2
  remove <part>
  new [habitat|spacecraft]     start over from a default design
"""

import json
import re
import sqlite3
import time
from pathlib import Path

from ..physics import spacecraft as sc
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


_SET = re.compile(r"^set\s+([\w-]+)\.(\w+)\s*(?:=|to|\s)\s*(.+)$", re.I)


def run_command(visitor_id: str, text: str) -> str | None:
    """A typed command -> snapshot text; None if the text is not a command (send it to the agent)."""
    t = text.strip()
    low = t.lower()
    word = low.split(maxsplit=1)[0] if low else ""
    if word not in ("show", "select", "set", "add", "remove", "new", "help"):
        return None
    if word == "help" and low == "help":
        return __doc__.split("Typed commands", 1)[1].split(":", 1)[1].strip("\n")
    store = get_store()
    try:
        if word == "new" and low in ("new", "new habitat", "new spacecraft"):
            d = sc.new_design(kind=low.split()[-1] if " " in low else "habitat")
        else:
            d = load_or_new(visitor_id)
            parts = t.split()
            if word == "show" and low == "show":
                pass
            elif word == "select" and len(parts) == 2:
                if parts[1] not in d["parts"]:
                    raise ValueError(f"no part named '{parts[1]}'; parts: {', '.join(d['parts'])}")
                d["selected"] = parts[1]
            elif word == "set" and (m := _SET.match(t)):
                sc.set_value(d, m.group(1), m.group(2), m.group(3).strip())
                if m.group(1) in d["parts"]:
                    d["selected"] = m.group(1)
            elif word == "add" and len(parts) == 3:
                sc.add_part(d, parts[2], parts[1])
            elif word == "remove" and len(parts) == 2:
                if parts[1] not in d["parts"]:
                    raise ValueError(f"no part named '{parts[1]}'")
                del d["parts"][parts[1]]
                if d["selected"] == parts[1]:
                    d["selected"] = next(iter(d["parts"]), "")
            else:
                return None      # looks like a sentence, not a command: let the agent handle it
    except ValueError as e:
        return f"error: {e}"
    store.put(visitor_id, d)
    return sc.report(d)
