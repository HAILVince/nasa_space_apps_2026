"""Turn PSI text and paper abstracts into test envelopes, keeping only what the text backs.

The model is asked for each number together with the sentence it came from. A range is
kept only if such a quote really appears in the text it was given; otherwise the range
becomes null. Rows always come out verified=false: a person checks them afterwards.

Run: python -m flame.ingest extract [--only PSI-25,PSI-69]
Needs BLACKFOX_AI_BASE and BLACKFOX_AI_KEY. Investigations that already have a verified
envelope are left alone.
"""

import asyncio
import json
import re
from pathlib import Path

from pydantic import ValidationError

from blackfox.llm import LLMError, get_llm

from .. import data
from ..models import Envelope, Investigation

PAPERS = Path(__file__).with_name("cache") / "papers.json"
PROMPT = """You read NASA combustion experiment descriptions and list the test conditions they state.
Reply with one JSON object and nothing else:
{"summary": "2-3 plain sentences: what was burned, how, and what it was for",
 "envelopes": [{"label": "short name of this family of tests", "fuel": "...", "geometry": "...",
   "o2Pct": [min, max] or null, "pressureKPa": [min, max] or null, "flowMps": [min, max] or null,
   "gravity": "micro" | "earth" | "partial-proxy", "diluent": "N2" | "CO2" | "He" | ... or null,
   "measured": ["..."], "sensors": ["..."], "keyFinding": "one sentence",
   "provenance": [{"field": "o2Pct" | "pressureKPa" | "flowMps" | "other", "source": "the [tag] the quote is under",
                   "quote": "copied word for word from the text"}]}]}
Rules:
- One envelope per distinct fuel or test family; usually 1 to 3.
- Oxygen in percent by volume. Pressure in kPa (1 atm = 101.325 kPa, 1 psi = 6.895 kPa). Flow in m/s.
- A range needs a provenance entry naming its field, with a quote that contains the numbers. No quote, no range: use null.
- Never fill in a typical or assumed value. If the text gives no number, the range is null.
- gravity is "micro" for space, drop-tower and aircraft tests, "earth" for normal-gravity tests,
  "partial-proxy" only for tests that imitate lunar or Martian gravity."""

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


def parse_json(text: str) -> dict:
    """The endpoint has no JSON mode, so take the outermost {...} out of whatever came back."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the model's answer")
    return json.loads(text[start:end + 1])


async def extract_one(inv: Investigation, papers: list[dict], llm) -> tuple[str, list[Envelope]]:
    context = build_context(inv, papers)
    messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": context}]
    answer = await llm.chat(messages, None, max_tokens=1500)
    return validate_extraction(parse_json(answer.message.get("content") or ""), context, inv.accession)


async def _run(only, llm, pause: float) -> int:
    papers = json.loads(PAPERS.read_text(encoding="utf-8")) if PAPERS.exists() else []
    existing = list(data.get_envelopes())
    checked = {e.accession for e in existing if e.verified}
    new, summaries = [], {}
    for inv in data.get_investigations():
        if inv.accession in checked or (only and inv.accession not in only):
            continue
        try:
            summary, rows = await extract_one(inv, [p for p in papers if p["accession"] == inv.accession], llm)
        except (LLMError, ValueError) as e:        # one bad answer must not lose the rest of the run
            print(f"{inv.accession:8} failed: {e}")
            continue
        new += rows
        summaries[inv.accession] = summary
        placed = sum(1 for e in rows if e.o2_pct and e.pressure_kpa)
        print(f"{inv.accession:8} {len(rows)} envelopes, {placed} with both oxygen and pressure")
        await asyncio.sleep(pause)
    if not summaries:
        print("nothing extracted; data files left as they were")
        return 1
    merged = sorted(merge(existing, new), key=lambda e: (int(e.accession[4:]), e.label))
    _write("envelopes", [e.model_dump(by_alias=True) for e in merged])
    invs = json.loads((data.DATA / "investigations.json").read_text(encoding="utf-8"))
    for row in invs:                               # a summary someone already wrote or fixed stays
        row["summary"] = row["summary"] or summaries.get(row["accession"], "")
    _write("investigations", invs)
    print(f"{len(new)} new envelopes; {len(merged)} in total")
    return 0


def _write(name: str, rows: list[dict]) -> None:
    (data.DATA / f"{name}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(only: list[str] | None = None, llm=None, pause: float = 3.0) -> int:
    return asyncio.run(_run(only, llm or get_llm(), pause))
