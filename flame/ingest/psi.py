"""Fetch NASA PSI's combustion investigations and write flame/data/investigations.json.

Run: python -m flame.ingest psi            (add --dry-run to print without writing)

PSI packs lists into one string: items are separated by 3 or more spaces, and the authors
inside one publication by 2. Fuel phase and topics are guessed from keywords; anything
the guess gets wrong is corrected in overrides.json, which always wins.
"""

import json
import re
from pathlib import Path

from blackfox.collect.sources import Http

from ..models import Investigation

SEARCH = "https://psi.nasa.gov/geode-py/ws/repo/search"
OUT = Path(__file__).parents[1] / "data" / "investigations.json"
OVERRIDES = Path(__file__).with_name("overrides.json")

# substring of the PSI hardware name (lowercase) -> short name
HARDWARE_ALIASES = {
    "combustion integrated rack": "CIR", "droplet combustion app": "MDCA",
    "microgravity science glovebox": "MSG", "acme": "ACME",
    "advanced combustion via microgravity": "ACME", "spice": "SPICE duct", "saffire": "Saffire",
}
# first match wins, so "Smoke Point In Co-flow" is a gas flame, not an aerosol study
FUEL_WORDS = (("liquid", ("droplet",)), ("solid", ("solid", "flame spread", "pmma", "cotton")),
              ("gas", ("gaseous", "gas jet", "coflow", "co-flow")), ("aerosol", ("smoke", "aerosol")))
TOPIC_WORDS = {"prevention": ("flammab", "ignition", "material"), "detection": ("smoke", "detect"),
               "suppression": ("suppress", "extinguish")}


def fetch_raw(http=None) -> list[dict]:
    params = {"term": "combustion", "source": "psi", "type": "investigation", "size": 200}
    body = (http or Http()).json("GET", SEARCH, params=params)
    return [hit["_source"] for hit in body["hits"]["hits"]]


def split_list(s: str | None) -> list[str]:
    return [x for x in re.split(r"\s{3,}", (s or "").strip()) if x]


def is_combustion(raw: dict) -> bool:
    return raw.get("Research Area") == "Combustion Science"


def _text(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _hardware(field) -> list[str]:
    items = field if isinstance(field, list) else [field] if isinstance(field, dict) else []
    out: list[str] = []
    for item in items:
        for name in re.split(r"\s{2,}", (item.get("Name") or "").strip()):
            short = next((v for k, v in HARDWARE_ALIASES.items() if k in name.lower()), name)
            if short and short not in out:
                out.append(short)
    return out


def normalize(raw: dict) -> Investigation:
    acc = raw["Accession"]
    hay = " ".join(raw.get(k) or "" for k in ("Title", "Acronym", "Keywords", "SubResearch Area", "Proposal Title")).lower()
    titles = split_list(raw.get("Publication Title"))
    groups = split_list(raw.get("Publication Author List"))
    # authors are matched to titles by position, so only trust them when the counts agree
    authors = [", ".join(re.split(r"\s{2,}", g)) for g in groups] if len(groups) == len(titles) else [None] * len(titles)
    return Investigation(
        accession=acc, acronym=_text(raw.get("Acronym")) or acc, title=_text(raw.get("Title")),
        kind="flight" if "Microgravity" in (raw.get("Project Type") or "") else "ground",
        sub_area=_text(raw.get("SubResearch Area")),
        fuel_phase=next((phase for phase, words in FUEL_WORDS if any(w in hay for w in words)), "none"),
        hardware=_hardware(raw.get("Experiment Hardware")),
        topics=[t for t, words in TOPIC_WORDS.items() if any(w in hay for w in words)] or ["fundamental"],
        objectives=_text(raw.get("Objectives")), approach=_text(raw.get("Approach")),
        hypothesis=_text(raw.get("Hypothesis")), earth_benefits=_text(raw.get("Research Impacts/Earth Benefits")),
        related=split_list(raw.get("Related Investigations")),
        publications=[{"title": t, "authors": a} for t, a in zip(titles, authors)],
        psi_url=f"https://psi.nasa.gov/physci/repo/search?q={acc}&data_source=psi&data_type=investigation",
        summary="",
    )


def apply_overrides(inv: Investigation, overrides: dict) -> Investigation:
    patch = overrides.get(inv.accession)
    return Investigation.model_validate({**inv.model_dump(by_alias=True), **patch}) if patch else inv


def main(dry_run: bool = False) -> int:
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    # summaries are written later by the extract step; a re-run must not wipe them
    kept = {row["accession"]: row.get("summary", "") for row in json.loads(OUT.read_text(encoding="utf-8"))}
    rows = [apply_overrides(normalize(raw), overrides) for raw in fetch_raw() if is_combustion(raw)]
    rows.sort(key=lambda inv: int(inv.accession[4:]))
    for inv in rows:
        inv.summary = inv.summary or kept.get(inv.accession, "")
        print(f"{inv.accession:8} {inv.acronym:20} {inv.kind:6} {inv.fuel_phase:7} {','.join(inv.topics):34} {inv.hardware}")
    if not dry_run:
        dump = [inv.model_dump(by_alias=True, exclude_none=True) for inv in rows]
        OUT.write_text(json.dumps(dump, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} investigations" + ("" if dry_run else f" -> {OUT}"))
    return 0
