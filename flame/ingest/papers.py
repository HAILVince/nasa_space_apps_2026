"""Look up abstracts on NTRS for the publications PSI lists, for the extract step to read.

Run: python -m flame.ingest papers

NTRS holds NASA reports and conference papers, not most journal articles, so many titles
find nothing. A hit only counts when its title is close to the one PSI gave (token Jaccard
of 0.6 or more) and it comes with an abstract. Output: flame/ingest/cache/papers.json.
"""

import json
import re
from pathlib import Path

from blackfox.collect.sources import NTRS, Http, clean

from .. import data

OUT = Path(__file__).with_name("cache") / "papers.json"
THRESHOLD = 0.6
PER_INVESTIGATION = 3     # abstracts kept per investigation; the extract prompt has a small budget
MAX_TRIES = 12            # titles tried per investigation before giving up
ABSTRACT_MAX = 3000


def title_similarity(a: str, b: str) -> float:
    ta, tb = (set(re.findall(r"[a-z0-9]+", s.lower())) for s in (a, b))
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def search_ntrs(title: str, http=None) -> dict | None:
    # NTRS returns nothing when the query carries a long subtitle, so search on the main title
    body = {"q": title.split(":")[0].strip(), "page": {"size": 5, "from": 0}}
    results = (http or Http()).json("POST", f"{NTRS}/api/citations/search", json=body, delay=0.5).get("results") or []
    best = max(results, key=lambda r: title_similarity(title, r.get("title") or ""), default=None)
    if best is None or title_similarity(title, best.get("title") or "") < THRESHOLD:
        return None
    abstract = clean(best.get("abstract"), ABSTRACT_MAX)
    if len(abstract) < 100:
        return None
    return {"ntrsId": str(best["id"]), "title": clean(best["title"]), "abstract": abstract,
            "url": f"{NTRS}/citations/{best['id']}"}


def collect(investigations, http=None) -> list[dict]:
    http = http or Http()
    rows: list[dict] = []
    for inv in investigations:
        seen: set[str] = set()     # PSI often lists one paper under two slightly different titles
        for pub in inv.publications[:MAX_TRIES]:
            if len(seen) == PER_INVESTIGATION:
                break
            hit = search_ntrs(pub.title, http)
            if hit and hit["ntrsId"] not in seen:
                seen.add(hit["ntrsId"])
                rows.append({"accession": inv.accession, "pubTitle": pub.title, "ntrsId": hit["ntrsId"],
                             "abstract": hit["abstract"], "url": hit["url"]})
        print(f"{inv.accession:8} {len(seen)} of {min(len(inv.publications), MAX_TRIES)} titles tried")
    return rows


def main() -> int:
    rows = collect(data.get_investigations())
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} abstracts for {len({r['accession'] for r in rows})} investigations -> {OUT}")
    return 0
