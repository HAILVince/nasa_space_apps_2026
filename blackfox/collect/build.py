"""Turns the harvested raw records into the sorted JSON database.

Layout written to the output folder (see blackfox/db/README.md):

  index.json                         the table of contents (counts, files, field descriptions)
  moon/<topic>-001.json ...          one folder per gravity environment, one file series per topic,
  mars/<topic>-001.json ...          records sorted newest first, then by title
  zero_g/<topic>-001.json ...

Every file is plain JSON with exactly one record per line, so a program can jump straight to
a record by byte offset and a person (or an LLM) can still read the file top to bottom.
"""

import hashlib
import json
import re
import time
from pathlib import Path

from .classify import GRAVITY, TOPICS, classify, is_pop_culture

FORMAT = "blackfox-knowledge/1"
SHARD_BYTES = 10_000_000          # keeps every file small enough for GitHub and quick to open
FIELD_ORDER = ("id", "title", "kind", "year", "gravity", "topic", "summary", "keywords", "authors", "org",
               "doc_type", "source", "url", "doi", "license", "trl", "fulltext_url")
FIELDS = {
    "id": "unique record id (also the slug the tools use), prefixed by its source: ntrs-, pmc-, epmc-, arxiv-, techport-, osdr-, wiki-",
    "title": "title of the report, paper, project, study or article",
    "kind": "report | paper | project | dataset | article (curated records also use experiment, facility, finding, concept, incident)",
    "year": "publication or start year",
    "gravity": "the gravity environments the record is about, most relevant first: moon, mars, zero_g",
    "topic": "the one topic the record is filed under (see index.json -> topics)",
    "summary": "abstract / description as plain text",
    "keywords": "subject keywords from the source",
    "authors": "up to 8 authors",
    "org": "NASA center, lead organisation or journal",
    "doc_type": "document type as named by the source",
    "source": "where the record was collected from",
    "url": "page of the original record",
    "doi": "DOI when known",
    "license": "licence of the text when the source states one",
    "trl": "technology readiness level at begin / current / end (TechPort projects)",
    "fulltext_url": "where the full text can be downloaded (used by `python -m blackfox.collect fulltext`)",
}


_INLINE = re.compile(r"</?(?:sub|sup|i|b|em|strong|u|tt|span|p|br|h\d)\b[^<>]{0,40}>", re.I)    # markup that arrived escaped


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:80] or "record"


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def build(staging: Path, out: Path, max_bytes: int = 30_000_000_000) -> dict:
    # pass 1: classify every raw record, keep only small metadata in memory, drop duplicates
    files = sorted(staging.glob("*.jsonl"))
    metas: list[list] = []        # [gravity0, topic, -year, title_lower, file_no, offset, length, quality, relevance, alive, gravity]
    seen: dict[str, int] = {}
    raw = dropped = dupes = 0
    for file_no, path in enumerate(files):
        with open(path, "rb") as f:
            offset = 0
            for line in f:
                length = len(line)
                try:
                    r = json.loads(line)
                except ValueError:      # a half-written last line after an interrupted harvest
                    offset += length
                    continue
                raw += 1
                gravity, topic, relevance = classify(r.get("title"), r.get("keywords"), r.get("summary"))
                if not gravity or not r.get("id") or (r.get("source") == "Wikipedia"
                                                      and is_pop_culture(r.get("title"), r.get("summary"))):
                    dropped += 1
                    offset += length
                    continue
                year = r.get("year") or 0
                quality = (bool(r.get("fulltext_url")), len(r.get("summary") or ""))
                keys = [slugify(r["id"])]
                if r.get("doi"):
                    keys.append("doi:" + r["doi"].lower())
                nt = _norm_title(r["title"])
                if len(nt) > 25:
                    keys.append(f"t:{nt}:{year}")
                me = len(metas)
                metas.append([gravity[0], topic, -year, r["title"].lower(), file_no, offset, length, quality, relevance, True, gravity])
                old = {seen[k] for k in keys if k in seen}
                if old:
                    dupes += 1
                    best = max(old | {me}, key=lambda i: metas[i][7])
                    for i in old | {me}:
                        metas[i][9] = i == best
                    me = best
                for k in keys:
                    seen[k] = me
                offset += length
    alive = [m for m in metas if m[9]]
    seen.clear()

    # size cap: if the database would be too big, the least relevant records go first
    total = sum(m[6] for m in alive)
    if total > max_bytes:
        alive.sort(key=lambda m: -m[8])
        kept, size = [], 0
        for m in alive:
            if size + m[6] > max_bytes:
                break
            kept.append(m)
            size += m[6]
        alive = kept

    # pass 2: sort (gravity, topic, newest first, title) and write the files
    alive.sort(key=lambda m: (m[0], m[1], m[2], m[3]))
    handles = [open(p, "rb") for p in files]
    out.mkdir(parents=True, exist_ok=True)
    for g in GRAVITY:
        (out / g).mkdir(exist_ok=True)
        for old_file in (out / g).glob("*-[0-9][0-9][0-9].json"):
            old_file.unlink()

    index_files, gravity_stats, sources, kinds = [], {}, {}, {}
    i = 0
    while i < len(alive):
        g, topic = alive[i][0], alive[i][1]
        j = i
        while j < len(alive) and alive[j][0] == g and alive[j][1] == topic:
            j += 1
        lines, years = [], []
        for m in alive[i:j]:
            handles[m[4]].seek(m[5])
            r = json.loads(handles[m[4]].read(m[6]))
            r["id"], r["gravity"], r["topic"] = slugify(r["id"]), m[10], topic
            r["title"], r["summary"] = _INLINE.sub("", r["title"]), _INLINE.sub("", r["summary"])
            rec = {k: r[k] for k in FIELD_ORDER if r.get(k) not in (None, "", [], {})}
            lines.append(json.dumps(rec, ensure_ascii=False))
            sources[rec["source"]] = sources.get(rec["source"], 0) + 1
            kinds[rec["kind"]] = kinds.get(rec["kind"], 0) + 1
            if rec.get("year"):
                years.append(rec["year"])
        parts, cur, size = [], [], 0
        for line in lines:
            if cur and size + len(line.encode()) > SHARD_BYTES:
                parts.append(cur)
                cur, size = [], 0
            cur.append(line)
            size += len(line.encode()) + 2
        parts.append(cur)
        names = []
        for n, part in enumerate(parts, 1):
            rel = f"{g}/{topic}-{n:03d}.json"
            header = {"format": FORMAT, "gravity": g, "topic": topic, "topic_label": TOPICS[topic], "part": n,
                      "parts": len(parts), "count": len(part), "sorted_by": "year (newest first), then title"}
            text = json.dumps(header, ensure_ascii=False)[:-1] + ', "records": [\n' + ",\n".join(part) + "\n]}\n"
            (out / rel).write_text(text, encoding="utf-8")
            index_files.append({"path": rel, "gravity": g, "topic": topic, "records": len(part), "bytes": len(text.encode())})
            names.append(rel)
        gs = gravity_stats.setdefault(g, {**GRAVITY[g], "records": 0, "topics": {}})
        gs["records"] += len(lines)
        gs["topics"][topic] = {"label": TOPICS[topic], "records": len(lines), "files": names,
                               "years": [min(years), max(years)] if years else None}
        i = j
    for h in handles:
        h.close()

    build_id = hashlib.sha1(json.dumps(index_files).encode()).hexdigest()[:16]
    index = {
        "format": FORMAT,
        "about": "Black Fox research knowledge base: text records about three gravity environments - the Moon (lunar "
                 "gravity), Mars (Martian gravity) and 0 g (microgravity / weightlessness). No images. Summaries come "
                 "from the named sources; open the record's url before citing a number.",
        "how_to_read": "Pick a gravity folder, then a topic file. Each file is JSON: a small header and a 'records' list "
                       "with one record per line, sorted newest first. curated/ holds hand-written records and facts.",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "build_id": build_id,
        "totals": {"records": len(alive), "bytes": sum(f["bytes"] for f in index_files), "files": len(index_files)},
        "gravity": gravity_stats,
        "topics": TOPICS,
        "sources": dict(sorted(sources.items(), key=lambda kv: -kv[1])),
        "kinds": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
        "fields": FIELDS,
        "files": index_files,
    }
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"raw_records": raw, "not_about_moon_mars_0g": dropped, "duplicates": dupes, **index["totals"],
            "by_gravity": {g: s["records"] for g, s in gravity_stats.items()}, "sources": index["sources"]}
