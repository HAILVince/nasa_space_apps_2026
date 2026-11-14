import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    visitor_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    trace TEXT NOT NULL DEFAULT '[]',
    model TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_conv ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    visitor_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS notes_visitor ON notes(visitor_id, id);
"""

MAX_NOTES_PER_VISITOR = 50
RETENTION_DAYS = 60


class SQLiteMemory:
    def __init__(self, path: Path):
        self.path = Path(path)
        with self._conn() as c:
            c.executescript(SCHEMA)
            cutoff = time.time() - RETENTION_DAYS * 86400
            c.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    # ---- conversation -------------------------------------------------------
    def history(self, conversation_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT role, content, trace, model, created_at FROM messages "
                             "WHERE conversation_id=? ORDER BY id DESC LIMIT ?", (conversation_id, limit)).fetchall()
        return [{"role": r["role"], "content": r["content"], "trace": json.loads(r["trace"]),
                 "model": r["model"], "created_at": r["created_at"]} for r in reversed(rows)]

    def append(self, conversation_id: str, visitor_id: str, role: str, content: str,
               trace: list | None = None, model: str = "") -> None:
        with self._conn() as c:
            c.execute("INSERT INTO messages (conversation_id, visitor_id, role, content, trace, model, created_at) "
                      "VALUES (?,?,?,?,?,?,?)",
                      (conversation_id, visitor_id, role, content,
                       json.dumps(trace or [], ensure_ascii=False), model, time.time()))

    def clear_conversation(self, conversation_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))

    # ---- notes --------------------------------------------------------------
    def remember(self, visitor_id: str, text: str) -> dict[str, Any]:
        text = " ".join(text.split())[:500]
        if not text:
            raise ValueError("empty note")
        with self._conn() as c:
            dup = c.execute("SELECT id FROM notes WHERE visitor_id=? AND lower(text)=lower(?)",
                            (visitor_id, text)).fetchone()
            if dup:
                return {"id": dup["id"], "text": text, "duplicate": True}
            nid = c.execute("INSERT INTO notes (visitor_id, text, created_at) VALUES (?,?,?)",
                            (visitor_id, text, time.time())).lastrowid
            c.execute("DELETE FROM notes WHERE visitor_id=? AND id NOT IN "
                      "(SELECT id FROM notes WHERE visitor_id=? ORDER BY id DESC LIMIT ?)",
                      (visitor_id, visitor_id, MAX_NOTES_PER_VISITOR))
        return {"id": nid, "text": text}

    def recall(self, visitor_id: str, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = [dict(r) for r in c.execute("SELECT id, text, created_at FROM notes WHERE visitor_id=? "
                                               "ORDER BY id DESC", (visitor_id,))]
        terms = set(re.findall(r"\w+", query.lower()))
        if terms:
            rows.sort(key=lambda r: -len(terms & set(re.findall(r"\w+", r["text"].lower()))))
        return rows[:max(1, min(limit, MAX_NOTES_PER_VISITOR))]

    def forget(self, visitor_id: str, note_id: int | None = None) -> int:
        with self._conn() as c:
            if note_id is None:
                return c.execute("DELETE FROM notes WHERE visitor_id=?", (visitor_id,)).rowcount
            return c.execute("DELETE FROM notes WHERE visitor_id=? AND id=?", (visitor_id, note_id)).rowcount
