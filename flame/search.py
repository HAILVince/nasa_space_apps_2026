"""Keyword search over the PSI investigations.

24 records need no search library. A query word scores once per field it appears in:
acronym 3, title 2, objectives / approach / summary 1 each. A word that only starts a
field word ("extinguish" in "extinguishment") counts for 0.6 of that. Typing an exact
acronym or accession puts that record first.

PSI gives ground studies no acronym; their names in our data were written from the title
(flame/ingest/overrides.json). Those names are skipped when scoring words, otherwise a made-up
name like "FLEX cool-flame CFD" would outrank FLEX itself for the word "flame".
"""

import re
from typing import NamedTuple

from . import data
from .models import Investigation

FIELDS = (("acronym", 3.0), ("title", 2.0), ("objectives", 1.0), ("approach", 1.0), ("summary", 1.0))
PREFIX = 0.6
EXACT_NAME = 10.0
NOISE = {"the", "of", "and", "in", "a", "an", "to", "for", "on", "with", "at", "by", "is", "are"}


class SearchHit(NamedTuple):
    accession: str
    acronym: str
    title: str
    summary: str
    score: float


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _score(inv: Investigation, query: list[str]) -> float:
    total = 0.0
    for name, weight in FIELDS:
        if name == "acronym" and inv.kind == "ground":
            continue
        field = set(_words(getattr(inv, name)))
        for q in query:
            if q in field:
                total += weight
            elif len(q) >= 3 and any(w.startswith(q) for w in field):
                total += weight * PREFIX
    return total


def search_investigations(query: str = "", *, fuel_phase: str | None = None, kind: str | None = None,
                          topic: str | None = None, hardware: str | None = None,
                          k: int | None = 5) -> list[SearchHit]:
    """Best matches first. An empty query lists everything that passes the filters, by accession."""
    rows = [i for i in data.get_investigations()
            if (not fuel_phase or i.fuel_phase == fuel_phase) and (not kind or i.kind == kind)
            and (not topic or topic in i.topics)
            and (not hardware or hardware.lower() in (h.lower() for h in i.hardware))]
    words = [w for w in _words(query) if w not in NOISE]
    name = " ".join(_words(query))
    hits = []
    for inv in rows:
        score = _score(inv, words)
        if name and name in (" ".join(_words(inv.acronym)), " ".join(_words(inv.accession))):
            score += EXACT_NAME
        if score > 0 or not query.strip():
            hits.append(SearchHit(inv.accession, inv.acronym, inv.title, inv.summary, round(score, 2)))
    hits.sort(key=lambda h: (-h.score, int(h.accession[4:])))
    return hits[:k]
