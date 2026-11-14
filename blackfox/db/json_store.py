"""The research database as plain JSON files.

The database IS the folder of JSON files (blackfox/db/knowledge, see README.md there):
text records sorted by gravity environment (moon / mars / zero_g) and topic, one record
per line. Nothing else holds data:

  knowledge/**.json                 the shipped records (collected + curated), read-only
  <data dir>/community.json         records and facts the AI or users added at runtime
  <fulltext dir>/**.json            optional full texts (python -m blackfox.collect fulltext)

To find records fast, the store keeps a search index next to the data
(<data dir>/knowledge_index.sqlite). It stores words and where each record sits in its JSON
file (file + byte offset) - never the record itself - and is rebuilt automatically in the
background whenever the JSON files change. Delete it any time; it comes back.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .base import GRAVITIES, KINDS

try:
    import fcntl
except ImportError:      # Windows dev machines: no cross-process lock, the build is still atomic
    fcntl = None

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT);
CREATE TABLE recs (
    id INTEGER PRIMARY KEY, slug TEXT UNIQUE, file_id INTEGER, offset INTEGER, length INTEGER, inline TEXT,
    title TEXT, kind TEXT, year INTEGER, gravity TEXT, topic TEXT, status TEXT, source TEXT);
CREATE VIRTUAL TABLE fts USING fts5(title, keywords, summary, content='', tokenize='unicode61 remove_diacritics 2');
"""
INDEXES = """
CREATE INDEX recs_browse ON recs (topic, year);
CREATE INDEX recs_kind ON recs (kind);
"""
STOP = set("a an and are as at be by for from how in is it its of on or that the this to was what when where which "
           "who why will with about into than then there their these those can does do".split())
LIMITS = {"title": 200, "summary": 3000, "details": 6000, "source": 300}
PAGE_CHARS = 4500     # one page of full text; fits the agent's tool-result budget
INTAKE_DIRS = ("pdf-s", "raw_data")   # folders in knowledge/ that hold source material, not records
FIRST_BUILD_WAIT = 40   # seconds a query waits for the very first index build before giving up


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:80] or "record"


def iter_knowledge_file(path: Path, bad_lines: list | None = None):
    """Yields (offset, length, record) for every record of a knowledge file, one at a time
    (the service runs with little memory). Files written one record per line give real byte
    offsets; any other valid JSON file with a "records" list also works (offset -1).
    Unreadable lines are skipped and counted in bad_lines."""
    with open(path, "rb") as f:
        first = f.readline()
        if first.rstrip().endswith(b'"records": ['):
            offset = len(first)
            for line in f:
                body = line.strip()
                if body in (b"]}", b"]", b"}"):
                    break
                if body:
                    body = body.rstrip(b",")
                    try:
                        yield offset + line.index(b"{"), len(body), json.loads(body)
                    except ValueError:
                        if bad_lines is not None:
                            bad_lines.append(offset)
                offset += len(line)
            return
    for rec in json.loads(path.read_text(encoding="utf-8")).get("records", []):     # small hand-written files
        yield -1, 0, rec


def read_knowledge_file(path: Path) -> list[tuple[int, int, dict]]:
    return list(iter_knowledge_file(path))


class JsonResearchStore:
    def __init__(self, root: Path, data_dir: Path, fulltext_dir: Path | None = None, background: bool = True):
        self.root, self.data_dir = Path(root), Path(data_dir)
        self.fulltext_dir = Path(fulltext_dir) if fulltext_dir else self.data_dir / "fulltext"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.data_dir / "knowledge_index.sqlite"
        self.community_path = self.data_dir / "community.json"
        self._lock = threading.Lock()
        self._build_error = ""
        self._fulltext: dict[str, tuple[Path, int, int]] | None = None
        self._fulltext_at = 0.0
        self._stats: dict | None = None
        self._community = self._load_community()
        self._signature = self._compute_signature()
        self._ready = threading.Event()
        self._building = self._indexed_signature() != self._signature
        if not self._building:
            self._ready.set()
        else:
            if background:
                threading.Thread(target=self._build, name="knowledge-index", daemon=True).start()
            else:
                self._build()

    # ---- search index (derived from the JSON files) -----------------------------------
    def _json_files(self) -> list[Path]:
        """The record files. Intake folders (source PDFs, unprocessed raw data) are not part of the database."""
        if not self.root.is_dir():
            return []
        return sorted(p for p in self.root.rglob("*.json")
                      if p.name != "index.json" and p.relative_to(self.root).parts[0] not in INTAKE_DIRS)

    def _compute_signature(self) -> str:
        h = hashlib.sha1(b"v1")
        for p in self._json_files():
            size = p.stat().st_size
            h.update(f"{p.relative_to(self.root)}:{size}".encode())
            if size < 2_000_000:      # small (hand-edited) files: notice edits that keep the size
                h.update(hashlib.sha1(p.read_bytes()).digest())
        return h.hexdigest()

    def _indexed_signature(self) -> str:
        if not self.index_path.exists():
            return ""
        try:
            with sqlite3.connect(self.index_path) as c:
                row = c.execute("SELECT value FROM meta WHERE key='signature'").fetchone()
            return row[0] if row else ""
        except sqlite3.Error:
            return ""

    def _build(self):
        lock_file = open(self.index_path.with_suffix(".lock"), "w")
        tmp = self.index_path.with_suffix(f".tmp{os.getpid()}")
        try:
            if fcntl:
                fcntl.flock(lock_file, fcntl.LOCK_EX)     # web app and MCP server share the data dir
            if self._indexed_signature() == self._signature:
                return
            tmp.unlink(missing_ok=True)
            c = sqlite3.connect(tmp)
            c.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
            n, skipped = 0, []
            for file_id, path in enumerate(self._json_files(), 1):
                rel = str(path.relative_to(self.root))
                c.execute("INSERT INTO files VALUES (?,?)", (file_id, rel))
                curated = rel.startswith("curated")
                bad: list[int] = []
                rows = iter_knowledge_file(path, bad)
                while True:
                    try:
                        offset, length, r = next(rows)
                    except StopIteration:
                        break
                    except (ValueError, OSError) as e:     # one broken file must not take the whole database down
                        skipped.append(f"{rel}: {e}"[:200])
                        break
                    title, summary = str(r.get("title") or "").strip(), str(r.get("summary") or "").strip()
                    if not title or not summary:
                        continue
                    n += 1
                    gravity = [g for g in r.get("gravity") or [] if g in GRAVITIES]
                    keywords = r.get("keywords") or r.get("tags") or ""
                    if isinstance(keywords, list):
                        keywords = "; ".join(map(str, keywords))
                    cur = c.execute(
                        "INSERT OR IGNORE INTO recs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (n, slugify(r.get("id") or r.get("slug") or title), file_id, offset, length,
                         json.dumps(r, ensure_ascii=False) if offset < 0 else None, title[:300],
                         str(r.get("kind") or "other"), r.get("year") or None, "," + ",".join(gravity) + ",",
                         str(r.get("topic") or "general"), "curated" if curated else "collected",
                         str(r.get("source") or ("Black Fox curated" if curated else ""))))
                    if cur.rowcount:
                        c.execute("INSERT INTO fts (rowid, title, keywords, summary) VALUES (?,?,?,?)",
                                  (n, title, keywords, summary + " " + str(r.get("details") or "")))
                if bad:
                    skipped.append(f"{rel}: {len(bad)} unreadable line(s)")
                c.commit()
            c.executescript(INDEXES)
            c.execute("INSERT INTO meta VALUES ('signature', ?)", (self._signature,))
            c.execute("INSERT INTO meta VALUES ('built_at', ?)", (str(time.time()),))
            c.execute("INSERT INTO meta VALUES ('skipped_files', ?)", (json.dumps(skipped),))
            c.commit()
            c.close()
            os.replace(tmp, self.index_path)
        except Exception as e:       # keep serving the previous index (if any) and report why
            self._build_error = f"{type(e).__name__}: {e}"
            tmp.unlink(missing_ok=True)
        finally:
            self._building = False
            self._stats = None
            self._ready.set()
            lock_file.close()

    def _conn(self) -> sqlite3.Connection | None:
        if not self.index_path.exists():
            self._ready.wait(FIRST_BUILD_WAIT)      # first start: indexing takes some seconds
            if not self.index_path.exists():
                return None
        c = sqlite3.connect(self.index_path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def _not_ready(self) -> dict[str, Any]:
        if self._build_error:
            return {"error": "the research index could not be built: " + self._build_error}
        return {"error": "the research database is still being indexed (first start after an update); "
                         "try again in a minute"}

    # ---- reading records out of the JSON files ----------------------------------------
    def _record(self, c: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        if row["inline"]:
            rec = json.loads(row["inline"])
        else:
            path = c.execute("SELECT path FROM files WHERE id=?", (row["file_id"],)).fetchone()[0]
            with open(self.root / path, "rb") as f:
                f.seek(row["offset"])
                rec = json.loads(f.read(row["length"]))
        rec["slug"], rec["status"] = row["slug"], row["status"]
        rec.pop("id", None)
        return rec

    @staticmethod
    def _brief(rec: dict, chars: int = 280) -> dict[str, Any]:
        summary = rec.get("summary", "")
        out = {k: rec[k] for k in ("slug", "title", "kind", "year", "gravity", "topic", "source", "status") if rec.get(k)}
        out["summary"] = summary if len(summary) <= chars else summary[:chars].rsplit(" ", 1)[0] + " ..."
        return out

    @staticmethod
    def _filters(gravity, topic, kind, year_from, year_to) -> tuple[str, list]:
        sql, args = "", []
        if gravity:
            sql += " AND r.gravity LIKE ?"
            args.append(f"%,{gravity},%")
        for col, val in (("topic", topic), ("kind", kind)):
            if val:
                sql += f" AND r.{col}=?"
                args.append(val)
        if year_from:
            sql += " AND r.year>=?"
            args.append(int(year_from))
        if year_to:
            sql += " AND r.year<=?"
            args.append(int(year_to))
        return sql, args

    def search(self, query: str, kind: str | None = None, limit: int = 8, gravity: str | None = None,
               topic: str | None = None, year_from: int | None = None, year_to: int | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 25))
        words = [w for w in re.findall(r"\w+", (query or "").lower(), flags=re.UNICODE)]
        terms = [w for w in words if w not in STOP and len(w) > 1][:12] or words[:12]
        if not terms:
            return self.list(kind=kind, gravity=gravity, topic=topic, limit=limit)
        c = self._conn()
        if c is None:
            return [self._not_ready()]
        where, args = self._filters(gravity, topic, kind, year_from, year_to)
        sql = ("SELECT r.*, bm25(fts, 10.0, 5.0, 1.0) * (CASE r.status WHEN 'curated' THEN 2.0 ELSE 1.0 END) AS rank "
               "FROM fts JOIN recs r ON r.id = fts.rowid WHERE fts MATCH ?" + where + " ORDER BY rank LIMIT ?")
        out, seen = [], set()
        with c:
            # first every word must match; if that finds too little, any word may match
            for joiner in (" AND ", " OR "):
                if len(out) >= limit or (joiner == " OR " and len(terms) == 1):
                    break
                match = joiner.join(f'"{t}"*' for t in terms)
                for row in c.execute(sql, [match, *args, limit]):
                    if row["slug"] not in seen and len(out) < limit:
                        seen.add(row["slug"])
                        out.append(self._brief(self._record(c, row)))
        c.close()
        return self._community_hits(terms, gravity, topic, kind) + out

    def get(self, slug: str) -> dict[str, Any] | None:
        slug = slugify(slug)
        rec = None
        for r in self._community["records"]:
            if r["slug"] == slug:
                rec = dict(r)
        if rec is None:
            c = self._conn()
            if c is None:
                return self._not_ready()
            with c:
                row = c.execute("SELECT * FROM recs WHERE slug=?", (slug,)).fetchone()
                rec = self._record(c, row) if row else None
            c.close()
        if rec is None:
            return None
        rec["facts"] = list(rec.get("facts") or []) + list(self._community["facts"].get(slug, []))
        rec.pop("fulltext_url", None)
        rec["full_text"] = slug in self._fulltext_index()
        return rec

    def list(self, kind: str | None = None, gravity: str | None = None, topic: str | None = None,
             limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        c = self._conn()
        if c is None:
            return [self._not_ready()]
        where, args = self._filters(gravity, topic, kind, None, None)
        limit = max(1, min(int(limit), 500))
        with c:
            rows = c.execute("SELECT slug, title, kind, year, gravity, topic, status FROM recs r WHERE 1=1" + where
                             + " ORDER BY r.status='curated' DESC, r.year DESC, r.title LIMIT ? OFFSET ?",
                             [*args, limit, max(0, int(offset))]).fetchall()
        c.close()
        out = [{**dict(r), "gravity": [g for g in r["gravity"].split(",") if g]} for r in rows]
        mine = [{k: r.get(k) for k in ("slug", "title", "kind", "year", "gravity", "topic", "status")}
                for r in self._community["records"]
                if (not kind or r["kind"] == kind) and (not topic or r.get("topic") == topic)
                and (not gravity or gravity in r.get("gravity", []))] if not offset else []
        return (mine + out)[:limit]

    def stats(self) -> dict[str, Any]:
        if self._stats is None:
            c = self._conn()
            if c is None:
                return self._not_ready()
            with c:
                by_gravity = {}
                for g in GRAVITIES:
                    topics = {r[0]: r[1] for r in c.execute(
                        "SELECT topic, count(*) FROM recs WHERE gravity LIKE ? GROUP BY topic ORDER BY 2 DESC", (f"%,{g},%",))}
                    by_gravity[g] = {"records": sum(topics.values()), "topics": topics}
                self._stats = {
                    "records": c.execute("SELECT count(*) FROM recs").fetchone()[0],
                    "by_gravity": by_gravity,
                    "by_kind": {r[0]: r[1] for r in c.execute("SELECT kind, count(*) FROM recs GROUP BY kind ORDER BY 2 DESC")},
                    "by_source": {r[0]: r[1] for r in c.execute("SELECT source, count(*) FROM recs GROUP BY source ORDER BY 2 DESC")},
                    "curated": c.execute("SELECT count(*) FROM recs WHERE status='curated'").fetchone()[0],
                }
                skipped = json.loads(c.execute("SELECT value FROM meta WHERE key='skipped_files'").fetchone()[0])
                if skipped:
                    self._stats["unreadable_files"] = skipped
            c.close()
        return {**self._stats, "community": len(self._community["records"]),
                "full_texts": len(self._fulltext_index()), "index_updating": self._building}

    # ---- full texts (optional, collected on the server) -------------------------------
    def _fulltext_index(self) -> dict[str, tuple[Path, int, int]]:
        if self._fulltext is None or time.time() - self._fulltext_at > 600:     # picks up texts collected while running
            idx = {}
            if self.fulltext_dir.is_dir():
                for side in sorted(self.fulltext_dir.rglob("*.idx.json")):
                    shard = side.with_name(side.name[:-len(".idx.json")] + ".json")
                    try:
                        for slug, (offset, length) in json.loads(side.read_text(encoding="utf-8")).items():
                            idx[slug] = (shard, offset, length)
                    except (ValueError, OSError):
                        continue
            self._fulltext, self._fulltext_at = idx, time.time()
        return self._fulltext

    def read_text(self, slug: str, page: int = 1, find: str = "") -> dict[str, Any]:
        slug = slugify(slug)
        where = self._fulltext_index().get(slug)
        if not where:
            return {"error": f"no full text stored for '{slug}'; get_research gives its summary and source url"}
        shard, offset, length = where
        with open(shard, "rb") as f:
            f.seek(offset)
            doc = json.loads(f.read(length))
        text = doc.get("text", "")
        pages = max(1, -(-len(text) // PAGE_CHARS))
        out = {"slug": slug, "title": doc.get("title", ""), "chars": len(text), "pages": pages}
        if find.strip():
            low, needle, hits = text.lower(), find.strip().lower(), []
            pos = low.find(needle)
            while pos >= 0 and len(hits) < 4:
                start = max(0, pos - 500)
                hits.append({"page": pos // PAGE_CHARS + 1, "text": text[start:pos + len(needle) + 500]})
                pos = low.find(needle, pos + len(needle) + 500)
            return {**out, "find": find.strip(), "matches": hits}
        page = max(1, min(int(page), pages))
        return {**out, "page": page, "text": text[(page - 1) * PAGE_CHARS:page * PAGE_CHARS]}

    # ---- community additions (kept in their own JSON file) ----------------------------
    def _load_community(self) -> dict[str, Any]:
        if self.community_path.exists():
            try:
                data = json.loads(self.community_path.read_text(encoding="utf-8"))
                return {"records": data.get("records", []), "facts": data.get("facts", {})}
            except ValueError:
                self.community_path.replace(self.community_path.with_suffix(".broken.json"))
        return self._import_old_sqlite()

    def _import_old_sqlite(self) -> dict[str, Any]:
        """One-time move of community records from the previous SQLite research.db."""
        data: dict[str, Any] = {"records": [], "facts": {}}
        old = self.data_dir / "research.db"
        if not old.exists():
            return data
        try:
            c = sqlite3.connect(old)
            c.row_factory = sqlite3.Row
            for r in c.execute("SELECT * FROM records WHERE status='community'"):
                data["records"].append({
                    "slug": r["slug"], "title": r["title"], "kind": r["kind"], "summary": r["summary"],
                    "details": r["details"], "gravity": ["zero_g"], "topic": "combustion_fire",
                    "keywords": [t.strip() for t in r["tags"].split(",") if t.strip()],
                    "source": "; ".join(s.get("title", "") for s in json.loads(r["sources"] or "[]")),
                    "status": "community", "created_by": r["created_by"], "created_at": r["created_at"]})
            for f in c.execute("SELECT f.*, r.slug FROM facts f JOIN records r ON r.id=f.record_id WHERE f.status='community'"):
                data["facts"].setdefault(f["slug"], []).append(
                    {"name": f["name"], "value": f["value"], "unit": f["unit"], "note": f["note"], "status": "community"})
            c.close()
        except sqlite3.Error:
            return {"records": [], "facts": {}}
        if data["records"] or data["facts"]:
            self._community = data
            self._save_community()
        return data

    def _save_community(self):
        tmp = self.community_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"about": "Records and facts added at runtime by the AI or users (unverified).",
                                   **self._community}, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.community_path)

    def _community_hits(self, terms, gravity, topic, kind) -> list[dict[str, Any]]:
        hits = []
        for r in self._community["records"]:
            if (gravity and gravity not in r.get("gravity", [])) or (topic and r.get("topic") != topic) \
                    or (kind and r.get("kind") != kind):
                continue
            text = " ".join([r["title"], r["summary"], r.get("details", ""), " ".join(r.get("keywords", []))]).lower()
            if all(t in text for t in terms):
                hits.append(self._brief(r))
        return hits[:3]

    def _is_shipped(self, slug: str) -> bool:
        c = self._conn()
        if c is None:
            return False
        with c:
            found = c.execute("SELECT 1 FROM recs WHERE slug=?", (slug,)).fetchone() is not None
        c.close()
        return found

    def add(self, record: dict[str, Any], created_by: str = "ai") -> dict[str, Any]:
        title, summary = str(record.get("title", "")).strip(), str(record.get("summary", "")).strip()
        if not title or not summary:
            raise ValueError("title and summary are required")
        kind = str(record.get("kind", "other")).strip().lower()
        gravity = record.get("gravity") or []
        if isinstance(gravity, str):
            gravity = [g.strip() for g in gravity.split(",") if g.strip()]
        bad = [g for g in gravity if g not in GRAVITIES]
        if bad or not gravity:
            raise ValueError(f"gravity must be one or more of {', '.join(GRAVITIES)}")
        keywords = record.get("keywords") or record.get("tags") or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        slug = slugify(record.get("slug") or title)
        if self._is_shipped(slug):
            raise ValueError(f"'{slug}' already exists in the database and cannot be overwritten; "
                             "use add_fact or pick a different title")
        rec = {"slug": slug, "title": title[:LIMITS["title"]], "kind": kind if kind in KINDS else "other",
               "summary": summary[:LIMITS["summary"]], "details": str(record.get("details", "")).strip()[:LIMITS["details"]],
               "gravity": gravity, "topic": slugify(record.get("topic") or "general").replace("-", "_"),
               "keywords": [str(k)[:60] for k in keywords][:12], "source": str(record.get("source", "")).strip()[:LIMITS["source"]],
               "year": record.get("year") or None, "status": "community", "created_by": created_by[:60], "created_at": time.time()}
        with self._lock:
            self._community["records"] = [r for r in self._community["records"] if r["slug"] != slug] + [rec]
            self._save_community()
        return self.get(slug)

    def add_fact(self, slug: str, name: str, value: float | None, unit: str, note: str,
                 created_by: str = "ai") -> dict[str, Any]:
        name = name.strip()[:120]
        if not name:
            raise ValueError("fact name is required")
        rec = self.get(slug)
        if not rec or rec.get("error"):
            raise ValueError(f"no record '{slug}'")
        slug = rec["slug"]
        if any(f["name"] == name and f.get("status") != "community" for f in rec["facts"]):
            raise ValueError("that fact is curated and cannot be overwritten; use a different name")
        fact = {"name": name, "value": value, "unit": (unit or "")[:40], "note": (note or "")[:500],
                "status": "community", "created_by": created_by[:60]}
        with self._lock:
            facts = [f for f in self._community["facts"].get(slug, []) if f["name"] != name] + [fact]
            self._community["facts"][slug] = facts
            self._save_community()
        return self.get(slug)
