"""Turn PSI text and paper abstracts into test envelopes, keeping only what the text backs.

The model is asked for each number together with the sentence it came from. A range is
kept only if such a quote really appears in the text it was given; otherwise the range
becomes null. Rows always come out verified=false: a person checks them afterwards.
"""

import re

from pydantic import ValidationError

from ..models import Envelope, Investigation

RANGES = ("o2Pct", "pressureKPa", "flowMps")
COPIED = ("label", "fuel", "geometry", *RANGES, "gravity", "diluent", "measured", "sensors", "keyFinding")
MIN_QUOTE = 12            # shorter than this and a "quote" like "21" would match anywhere
_FOLD = str.maketrans({"−": "-", "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"'})


def _squash(s: str) -> str:
    """Whitespace, case and dash style do not count when checking a quote."""
    return re.sub(r"\s+", " ", s.translate(_FOLD)).strip().lower()


def build_context(inv: Investigation, papers: list[dict], max_tokens: int = 3500) -> str:
    """The text the model reads, each part under a [source] tag it can cite. ~4 chars per token."""
    parts = [(f"{inv.accession} Title", f"{inv.acronym}: {inv.title}"), (f"{inv.accession} Objectives", inv.objectives),
             (f"{inv.accession} Approach", inv.approach), (f"{inv.accession} Hypothesis", inv.hypothesis)]
    parts += [(f"NTRS {p['ntrsId']}", p["abstract"]) for p in papers]
    budget, each = max_tokens * 4, max_tokens * 4 // len(parts)
    # no part may crowd out the others: PSI's own text and every abstract get an equal share
    return "\n".join(f"[{tag}] {text[:each - len(tag) - 4]}" for tag, text in parts if text)[:budget]


def validate_extraction(raw: dict, context: str, accession: str) -> tuple[str, list[Envelope]]:
    ctx, rows = _squash(context), []
    for item in raw.get("envelopes") or []:
        if not isinstance(item, dict):
            continue
        quotes = [p for p in item.get("provenance") or []
                  if isinstance(p, dict) and len(q := _squash(str(p.get("quote", "")))) >= MIN_QUOTE and q in ctx]
        backed = {p.get("field") for p in quotes}
        row = {k: item.get(k) for k in COPIED if item.get(k) is not None}
        row |= {name: row.get(name) if name in backed else None for name in RANGES}
        row |= {"accession": accession, "verified": False,
                "provenance": [{"source": str(p.get("source", "")), "quote": str(p["quote"])} for p in quotes]}
        try:
            rows.append(Envelope.model_validate(row))
        except ValidationError:
            continue          # a row the model got wrong is skipped; the others still count
    return str(raw.get("summary") or "").strip(), rows


def merge(existing: list[Envelope], new: list[Envelope]) -> list[Envelope]:
    """New rows replace an investigation's unchecked rows. A verified row is never touched."""
    fresh = {e.accession for e in new}
    keep = [e for e in existing if e.verified or e.accession not in fresh]
    taken = {(e.accession, e.label) for e in keep}
    return keep + [e for e in new if (e.accession, e.label) not in taken]
