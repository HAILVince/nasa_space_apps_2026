"""Source-backed challenge metadata; relevance scores are not fire risk predictions."""
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/research")
SOURCE = "https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/"


class Scenario(str, Enum):
    spacecraft = "spacecraft"
    station = "station"
    lunar_base = "lunar_base"
    mars_habitat = "mars_habitat"
    rover = "rover"


class Focus(str, Enum):
    all = "all"
    prevention = "prevention"
    detection = "detection"
    suppression = "suppression"


# Legacy family IDs resolve to a representative investigation in compare URLs.
ALIASES = {"bass": "PSI-26", "saffire": "PSI-98", "same": "PSI-102",
           "flex": "PSI-69", "bre": "PSI-20", "cfi_g": "PSI-159"}
MODEL_STUDIES = {"PSI-60", "PSI-62", "PSI-115", "PSI-117", "PSI-142"}


def _range(envelopes, attribute):
    ranges = [getattr(e, attribute) for e in envelopes if getattr(e, attribute) is not None]
    return [min(r[0] for r in ranges), max(r[1] for r in ranges)] if ranges else None


def _catalog():
    from flame.data import get_envelopes, get_investigations
    by_accession = {}
    for envelope in get_envelopes():
        by_accession.setdefault(envelope.accession, []).append(envelope)
    rows = []
    for inv in get_investigations():
        envs = by_accession.get(inv.accession, [])
        focuses = [x for x in ("prevention", "detection", "suppression") if x in inv.topics]
        if not focuses:
            # Fundamental combustion studies inform prevention, but are not direct safety tests.
            focuses = ["detection" if inv.fuel_phase == "aerosol" else "prevention"]
        fuels = list(dict.fromkeys(e.fuel for e in envs if e.fuel))
        rows.append(dict(id=inv.accession, accession=inv.accession, acronym=inv.acronym,
                         title=inv.title, focus=focuses[0], focuses=focuses, topics=inv.topics,
                         fuel=inv.fuel_phase + (": " + "; ".join(fuels) if fuels else ""),
                         fuel_phase=inv.fuel_phase, hardware=", ".join(inv.hardware) or "not reported",
                         summary=inv.summary, gravity="microgravity", source_url=inv.psi_url,
                         evidence_type="psi_investigation", kind=inv.kind,
                         measurements_available=bool(envs),
                         oxygen_percent=_range(envs, "o2_pct"), pressure_kpa=_range(envs, "pressure_kpa"),
                         airflow_m_s=_range(envs, "flow_mps"),
                         conditions_note=("Modeling study; no experimental envelope reported." if inv.accession in MODEL_STUDIES
                                          else "No experimental envelope reported." if not envs
                                          else "Envelope ranges aggregate reported conditions; missing fields are unknown.")))
    return rows


CATALOG = _catalog()
LIMITATIONS = [
    "PSI investigation summaries and reported experimental envelope ranges; ranges spanning multiple envelopes do not imply every combination was tested.",
    "An available envelope does not mean every condition was reported or that raw measurements are available; check the source and verification status.",
    "Relevance scores express topic matching, not ignition probability, safety certification or validated predictive modeling.",
    "PSI microgravity findings do not establish lunar or Martian fire behavior.",
    "Missing oxygen, pressure and airflow values are unknown, never zero. Consult original datasets before comparing test conditions.",
]


def ranked(scenario: Scenario, focus: Focus, q: str):
    rows = []
    for item in CATALOG:
        if focus != Focus.all and focus.value not in item["focuses"]:
            continue
        if q.casefold() not in " ".join(str(v) for v in item.values()).casefold():
            continue
        score = 50
        reasons = [f"PSI topics: {', '.join(item['topics'])}; dashboard categories: {', '.join(item['focuses'])} (+50 baseline)."]
        if "fundamental" in item["topics"] and not any(t in item["topics"] for t in ("prevention", "detection", "suppression")):
            reasons.append("Fundamental research is grouped by fuel phase as indirect safety evidence.")
        if focus != Focus.all:
            score += 30
            reasons.append(f"Matches selected {focus.value} focus (+30).")
        if scenario in (Scenario.lunar_base, Scenario.mars_habitat, Scenario.rover) and item["fuel_phase"] == "solid":
            score += 20
            reasons.append("Solid-material research is relevant to habitat or rover materials (+20); this is not a partial-gravity result.")
        elif scenario in (Scenario.spacecraft, Scenario.station) and item["kind"] == "flight":
            score += 20
            reasons.append("Flight investigation is relevant to a microgravity mission context (+20).")
        else:
            reasons.append("No scenario-specific topic bonus (+0).")
        rows.append(dict(item, relevance_score=score, ranking_reasons=reasons))
    return sorted(rows, key=lambda row: (-row["relevance_score"], row["id"]))


@router.get("/scenarios")
def scenarios():
    return {"scenarios": [{"id": s.value, "label": s.value.replace("_", " ").title()}
                          for s in Scenario], "focuses": [f.value for f in Focus]}


@router.get("/dashboard")
def dashboard(scenario: Scenario = Scenario.spacecraft, focus: Focus = Focus.all,
              q: str = Query("", max_length=200)):
    rows = ranked(scenario, focus, q.strip())
    return {"scenario": scenario.value, "focus": focus.value, "investigations": rows,
            "total": len(rows), "counts": {f.value: sum(r["focus"] == f.value for r in rows)
                                           for f in Focus if f != Focus.all},
            "method": "topic-relevance-v2", "limitations": LIMITATIONS,
            "source_url": SOURCE}


@router.get("/compare")
def compare(ids: str = Query(..., max_length=200)):
    selected = list(dict.fromkeys(i.strip() for i in ids.split(",") if i.strip()))
    if not 2 <= len(selected) <= 4:
        raise HTTPException(422, "Choose two to four distinct investigation IDs.")
    by_id = {r["id"]: r for r in CATALOG}
    if any(ALIASES.get(i, i) not in by_id for i in selected):
        raise HTTPException(404, "Unknown investigation ID.")
    return {"investigations": [dict(by_id[ALIASES.get(i, i)], id=i) for i in selected], "limitations": LIMITATIONS}


@router.get("/vector/status")
def vector_status():
    from blackfox.db.vector_store import get_vector_store
    store = get_vector_store()
    return store.status() if store else {"enabled": False, "ready": False}


@router.get("/vector/search")
def vector_search(q: str = Query(..., min_length=1, max_length=2000),
                  limit: int = Query(6, ge=1, le=25)):
    from blackfox.tools.research import search_research_semantic
    result = search_research_semantic(q, limit)
    if "error" in result:
        return JSONResponse(result, status_code=503)
    return result
