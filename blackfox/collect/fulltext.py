"""Optional second stage: download the full text of the records in the database.

The summaries in the database are a few hundred MB; the full texts are what can fill tens
of GB, so they are not kept in git. Run this on the server:

    python -m blackfox.collect --max-gb 30 fulltext

It stops when database + full texts reach --max-gb, can be interrupted and continued, and
writes text only:

  <fulltext dir>/<gravity>/text-0001.json       {"format": ..., "records": [ one document per line ]}
  <fulltext dir>/<gravity>/text-0001.idx.json   {"<record id>": [byte offset, length]}  (lookup table)
"""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from itertools import zip_longest
from pathlib import Path

from ..db.json_store import iter_knowledge_file
from .sources import Http, clean

FORMAT = "blackfox-fulltext/1"
SHARD_BYTES = 100_000_000
DOC_CHARS = 400_000        # one document never takes more than this
FOOTER = b"\n]}\n"
_BREAK = re.compile(r"</(?:p|div|h\d|li|tr|title|sec)>|<br\s*/?>", re.I)
_DROP = re.compile(r"<(head|ref-list|front|back|table-wrap|fig|script|style)\b.*?</\1>", re.I | re.S)


def to_text(url: str, body: bytes) -> str:
    """Whatever the source returns (Tika HTML, JATS XML, MediaWiki JSON) -> plain text paragraphs."""
    if "wikipedia.org" in url:
        pages = (json.loads(body).get("query") or {}).get("pages") or {}
        raw = next(iter(pages.values()), {}).get("extract", "")
        paragraphs = raw.split("\n")
    else:
        raw = _DROP.sub(" ", body.decode("utf-8", "replace"))
        paragraphs = _BREAK.sub("\n", raw).split("\n")
    text = "\n".join(p for p in (clean(p) for p in paragraphs) if p)
    return text[:DOC_CHARS]


def _dir_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else 0


def _scan(shard: Path) -> dict[str, list[int]]:
    """Rebuild a shard's lookup table from the shard itself."""
    return {rec["id"]: [offset, length] for offset, length, rec in iter_knowledge_file(shard) if offset >= 0}


class _Shards:
    """Appends documents to <gravity>/text-NNNN.json, keeping every file valid JSON at all times."""

    def __init__(self, root: Path):
        self.root, self.open_shard, self.index = root, {}, {}
        for shard in sorted(root.rglob("text-*.json")):
            if shard.name.endswith(".idx.json"):
                continue
            side = shard.with_name(shard.stem + ".idx.json")
            idx = _scan(shard)     # trust the data file, not a possibly stale lookup table
            side.write_text(json.dumps(idx), encoding="utf-8")
            self.index[shard] = idx
            self.open_shard[shard.parent.name] = shard

    def known(self) -> set[str]:
        return {slug for idx in self.index.values() for slug in idx}

    def add(self, gravity: str, doc: dict) -> int:
        line = json.dumps(doc, ensure_ascii=False).encode()
        shard = self.open_shard.get(gravity)
        if shard is None or shard.stat().st_size + len(line) > SHARD_BYTES:
            n = int(shard.stem.split("-")[1]) + 1 if shard else 1
            shard = self.root / gravity / f"text-{n:04d}.json"
            shard.parent.mkdir(parents=True, exist_ok=True)
            shard.write_bytes(json.dumps({"format": FORMAT, "gravity": gravity})[:-1].encode() + b', "records": [' + FOOTER)
            self.open_shard[gravity], self.index[shard] = shard, {}
        idx = self.index[shard]
        with open(shard, "r+b") as f:
            f.seek(-len(FOOTER), 2)
            f.write(b",\n" if idx else b"\n")
            offset = f.tell()
            f.write(line + FOOTER)
        idx[doc["id"]] = [offset, len(line)]
        if len(idx) % 25 == 0:
            self.flush(shard)
        return len(line)

    def flush(self, shard: Path | None = None):
        for s in [shard] if shard else list(self.index):
            s.with_name(s.stem + ".idx.json").write_text(json.dumps(self.index[s]), encoding="utf-8")


def collect_fulltext(knowledge: Path, out: Path, max_bytes: int = 30_000_000_000, workers: int = 6, limit: int = 0) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    shards = _Shards(out)
    have = shards.known()
    budget = max_bytes - _dir_bytes(knowledge) - _dir_bytes(out)

    # newest records of every gravity/topic file first, taking turns between the files
    per_file = []
    for path in sorted(knowledge.rglob("*-[0-9][0-9][0-9].json")):
        rows = [(r["id"], r["gravity"][0], r["title"], r.get("url", ""), r["fulltext_url"])
                for _, _, r in iter_knowledge_file(path) if r.get("fulltext_url") and r["id"] not in have]
        if rows:
            per_file.append(rows)
    todo = [row for group in zip_longest(*per_file) for row in group if row]
    if limit:
        todo = todo[:limit]

    http = Http()
    stats = {"wanted": len(todo), "stored": 0, "empty_or_failed": 0, "bytes_added": 0, "stopped_at_size_cap": False}

    full = threading.Event()

    def fetch(row):
        slug, gravity, title, url, ft_url = row
        if full.is_set():       # size cap reached: skip the rest of the queue without downloading
            return gravity, None
        try:
            r = http.request("GET", ft_url, delay=1.0 if "wikipedia.org" in ft_url else 0.0, tries=3)
            text = to_text(ft_url, r.content) if r.status_code == 200 else ""
        except Exception:
            text = ""
        return gravity, {"id": slug, "title": title, "url": url, "chars": len(text), "text": text}

    with ThreadPoolExecutor(workers) as pool:
        for gravity, doc in pool.map(fetch, todo):
            if doc is None or full.is_set():
                continue
            if doc["chars"] < 500:          # scanned PDFs without a text layer, withdrawn files, errors
                stats["empty_or_failed"] += 1
                continue
            if len(json.dumps(doc, ensure_ascii=False).encode()) + 200 > budget:     # would pass --max-gb: stop here
                stats["stopped_at_size_cap"] = True
                full.set()
                continue
            added = shards.add(gravity, doc)
            stats["stored"] += 1
            stats["bytes_added"] += added
            budget -= added + 60      # 60: the document's entry in the lookup table
    shards.flush()
    stats["total_full_texts"] = len(shards.known())
    return stats
