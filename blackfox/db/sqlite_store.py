"""SQLite research store with FTS5 full-text search.

Schema
  records  one row per experiment / facility / finding / concept / incident
  facts    numeric facts attached to a record (e.g. drop time 5.18 s)
  records_fts  full-text index over title, summary, details, tags

`status` is "curated" for the seed data shipped in the repo (seed/*.json, re-applied on
every start so edits in git reach the live DB) and "community" for anything an AI or
user added at runtime - the website shows the difference.
"""

import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .base import KINDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT '',
    agency TEXT NOT NULL DEFAULT '',
    years TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    sources TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'community',
    created_by TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY,
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    value REAL,
    unit TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'community',
    created_by TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    UNIQUE(record_id, name)
);
CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
    title, summary, details, tags, platform, content='records', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS records_ai AFTER INSERT ON records BEGIN
  INSERT INTO records_fts(rowid, title, summary, details, tags, platform)
  VALUES (new.id, new.title, new.summary, new.details, new.tags, new.platform);
END;
CREATE TRIGGER IF NOT EXISTS records_ad AFTER DELETE ON records BEGIN
  INSERT INTO records_fts(records_fts, rowid, title, summary, details, tags, platform)
  VALUES ('delete', old.id, old.title, old.summary, old.details, old.tags, old.platform);
END;
CREATE TRIGGER IF NOT EXISTS records_au AFTER UPDATE ON records BEGIN
  INSERT INTO records_fts(records_fts, rowid, title, summary, details, tags, platform)
  VALUES ('delete', old.id, old.title, old.summary, old.details, old.tags, old.platform);
  INSERT INTO records_fts(rowid, title, summary, details, tags, platform)
  VALUES (new.id, new.title, new.summary, new.details, new.tags, new.platform);
END;
"""

LIMITS = {"title": 200, "summary": 1200, "details": 6000, "platform": 200, "agency": 120,
          "years": 60, "tags": 300}


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:80] or "record"


class SQLiteResearchStore:
    def __init__(self, path: Path, seed_dir: Path | None = None):
        self.path = Path(path)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(SCHEMA)
        if seed_dir and seed_dir.is_dir():
            self.apply_seed(seed_dir)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    # ---- seed ---------------------------------------------------------------
    def apply_seed(self, seed_dir: Path) -> int:
        n = 0
        for f in sorted(seed_dir.glob("*.json")):
            for rec in json.loads(f.read_text(encoding="utf-8"))["records"]:
                self._upsert(rec, status="curated", created_by="seed")
                n += 1
        return n

    def _upsert(self, rec: dict, status: str, created_by: str) -> int:
        now = time.time()
        row = self._clean(rec)
        with self._lock, self._conn() as c:
            cur = c.execute("SELECT id, status FROM records WHERE slug=?", (row["slug"],)).fetchone()
            if cur:
                c.execute("""UPDATE records SET title=?, kind=?, summary=?, details=?, platform=?, agency=?,
                             years=?, tags=?, sources=?, status=?, updated_at=? WHERE id=?""",
                          (row["title"], row["kind"], row["summary"], row["details"], row["platform"],
                           row["agency"], row["years"], row["tags"], row["sources"], status, now, cur["id"]))
                rid = cur["id"]
            else:
                rid = c.execute("""INSERT INTO records (slug, title, kind, summary, details, platform, agency,
                                   years, tags, sources, status, created_by, created_at, updated_at)
                                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                (row["slug"], row["title"], row["kind"], row["summary"], row["details"],
                                 row["platform"], row["agency"], row["years"], row["tags"], row["sources"],
                                 status, created_by, now, now)).lastrowid
            for fact in rec.get("facts", []):
                c.execute("""INSERT INTO facts (record_id, name, value, unit, note, status, created_by, created_at)
                             VALUES (?,?,?,?,?,?,?,?)
                             ON CONFLICT(record_id, name) DO UPDATE SET value=excluded.value,
                               unit=excluded.unit, note=excluded.note, status=excluded.status""",
                          (rid, fact["name"][:120], fact.get("value"), fact.get("unit", "")[:40],
                           fact.get("note", "")[:500], status, created_by, now))
        return rid

    @staticmethod
    def _clean(rec: dict) -> dict:
        title = str(rec.get("title", "")).strip()
        summary = str(rec.get("summary", "")).strip()
        if not title or not summary:
            raise ValueError("title and summary are required")
        kind = str(rec.get("kind", "other")).strip().lower()
        if kind not in KINDS:
            kind = "other"
        tags = rec.get("tags", "")
        if isinstance(tags, (list, tuple)):
            tags = ", ".join(str(t).strip() for t in tags if str(t).strip())
        sources = rec.get("sources", [])
        if isinstance(sources, str):
            sources = [{"title": sources}] if sources.strip() else []
        sources = [s if isinstance(s, dict) else {"title": str(s)} for s in sources][:10]
        out = {"slug": slugify(rec.get("slug") or title), "title": title, "kind": kind, "summary": summary,
               "details": str(rec.get("details", "")).strip(), "platform": str(rec.get("platform", "")).strip(),
               "agency": str(rec.get("agency", "")).strip(), "years": str(rec.get("years", "")).strip(),
               "tags": str(tags).strip(), "sources": json.dumps(sources, ensure_ascii=False)}
        for k, n in LIMITS.items():
            out[k] = out[k][:n]
        return out

    # ---- reads --------------------------------------------------------------
    @staticmethod
    def _row(r: sqlite3.Row, full: bool = False) -> dict[str, Any]:
        d = {k: r[k] for k in ("slug", "title", "kind", "summary", "platform", "agency", "years", "tags", "status")}
        if full:
            d["details"] = r["details"]
            d["sources"] = json.loads(r["sources"] or "[]")
        return d

    def search(self, query: str, kind: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 25))
        terms = re.findall(r"\w+", query or "", flags=re.UNICODE)
        if not terms:
            return self.list(kind=kind, limit=limit)
        fts = " OR ".join(f'"{t}"*' for t in terms[:12])
        sql = ("SELECT r.* FROM records_fts f JOIN records r ON r.id=f.rowid WHERE records_fts MATCH ?"
               + (" AND r.kind=?" if kind else "") + " ORDER BY bm25(records_fts, 8, 4, 1, 3, 2) LIMIT ?")
        args = [fts] + ([kind] if kind else []) + [limit]
        with self._conn() as c:
            return [self._row(r) for r in c.execute(sql, args)]

    def get(self, slug: str) -> dict[str, Any] | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM records WHERE slug=?", (slugify(slug),)).fetchone()
            if not r:
                return None
            d = self._row(r, full=True)
            d["facts"] = [dict(f) for f in c.execute(
                "SELECT name, value, unit, note, status FROM facts WHERE record_id=? ORDER BY id", (r["id"],))]
            return d

    def list(self, kind: str | None = None, tag: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM records WHERE 1=1", []
        if kind:
            sql += " AND kind=?"; args.append(kind)
        if tag:
            sql += " AND (',' || lower(replace(tags,' ','')) || ',') LIKE ?"
            args.append(f"%,{tag.lower().replace(' ', '')},%")
        sql += " ORDER BY status='curated' DESC, kind, title LIMIT ?"
        args.append(max(1, min(int(limit), 500)))
        with self._conn() as c:
            return [self._row(r) for r in c.execute(sql, args)]

    def stats(self) -> dict[str, Any]:
        with self._conn() as c:
            kinds = {r[0]: r[1] for r in c.execute("SELECT kind, count(*) FROM records GROUP BY kind")}
            status = {r[0]: r[1] for r in c.execute("SELECT status, count(*) FROM records GROUP BY status")}
            facts = c.execute("SELECT count(*) FROM facts").fetchone()[0]
        return {"records": sum(kinds.values()), "by_kind": kinds, "by_status": status, "facts": facts}

    # ---- writes -------------------------------------------------------------
    def add(self, record: dict[str, Any], created_by: str = "ai") -> dict[str, Any]:
        row = self._clean(record)
        with self._conn() as c:
            existing = c.execute("SELECT status FROM records WHERE slug=?", (row["slug"],)).fetchone()
        if existing and existing["status"] == "curated":
            raise ValueError(f"'{row['slug']}' is a curated record and cannot be overwritten; "
                             "use add_fact or pick a different title")
        self._upsert({**record, "slug": row["slug"]}, status="community", created_by=created_by[:60])
        return self.get(row["slug"])

    def add_fact(self, slug: str, name: str, value: float | None, unit: str, note: str,
                 created_by: str = "ai") -> dict[str, Any]:
        if not name.strip():
            raise ValueError("fact name is required")
        with self._lock, self._conn() as c:
            r = c.execute("SELECT id FROM records WHERE slug=?", (slugify(slug),)).fetchone()
            if not r:
                raise ValueError(f"no record '{slug}'")
            cur = c.execute("SELECT status FROM facts WHERE record_id=? AND name=?", (r["id"], name.strip())).fetchone()
            if cur and cur["status"] == "curated":
                raise ValueError("that fact is curated and cannot be overwritten; use a different name")
            c.execute("""INSERT INTO facts (record_id, name, value, unit, note, status, created_by, created_at)
                         VALUES (?,?,?,?,?, 'community', ?, ?)
                         ON CONFLICT(record_id, name) DO UPDATE SET value=excluded.value, unit=excluded.unit,
                           note=excluded.note""",
                      (r["id"], name.strip()[:120], value, (unit or "")[:40], (note or "")[:500],
                       created_by[:60], time.time()))
        return self.get(slug)
