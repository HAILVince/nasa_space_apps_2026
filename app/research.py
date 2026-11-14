"""Source-backed challenge metadata; relevance scores are not fire risk predictions."""
from enum import Enum

from fastapi import APIRouter, HTTPException, Query

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


def investigation(id, title, focus, fuel, hardware, summary):
    return dict(id=id, title=title, focus=focus, fuel=fuel, hardware=hardware,
                summary=summary, gravity="microgravity", source_url=SOURCE,
                evidence_type="challenge_description", measurements_available=False,
                oxygen_percent=None, pressure_kpa=None, airflow_m_s=None)


CATALOG = [
    investigation("bass", "BASS / BASS-II", "prevention", "solid fabrics and plastics",
                  "Microgravity Science Glovebox flow duct",
                  "Studies solid-material flammability and the role of airflow in microgravity."),
    investigation("saffire", "Saffire-I / II / III", "prevention", "solid materials",
                  "Spacecraft Fire Safety Demonstration",
                  "Investigates solid-material burning relevant to spacecraft fire prevention."),
    investigation("same", "SAME / SAME-R", "detection", "smoke and aerosols",
                  "Smoke and Aerosol Measurement Experiment",
                  "Studies smoke and aerosol measurements for microgravity fire detection."),
    investigation("flex", "FLEX", "suppression", "liquid fuel droplets",
                  "Multi-user Droplet Combustion Apparatus, CIR",
                  "Studies flame extinguishment through atmospheric dilution with carbon dioxide and helium."),
    investigation("bre", "BRE (ACME)", "prevention", "gaseous fuels",
                  "ACME modular hardware, CIR",
                  "Uses gaseous flames to study material flammability in still atmospheres as a function of material properties."),
    investigation("cfi_g", "CFI-G (ACME)", "prevention", "gaseous fuels",
                  "ACME modular hardware, CIR",
                  "Studies inside-out cool flames with oxygen-nitrogen burner mixtures up to 85% oxygen; this is not a habitat atmosphere test."),
]
LIMITATIONS = [
    "Curated metadata from the challenge brief, not ingested PSI measurements or experimental results.",
    "Relevance scores express topic matching, not ignition probability, safety certification or validated predictive modeling.",
    "The challenge brief reports no partial-gravity combustion data in PSI. Microgravity findings do not establish lunar or Martian fire behavior.",
    "Missing oxygen, pressure and airflow values are unknown, never zero. Consult original datasets before comparing test conditions.",
]


def ranked(scenario: Scenario, focus: Focus, q: str):
    rows = []
    for item in CATALOG:
        if focus != Focus.all and item["focus"] != focus.value:
            continue
        if q.casefold() not in " ".join(str(v) for v in item.values()).casefold():
            continue
        score = 50
        reasons = ["Direct fire-safety topic in the NASA challenge brief (+50)."]
        if focus != Focus.all:
            score += 30
            reasons.append(f"Matches selected {focus.value} focus (+30).")
        if scenario in (Scenario.lunar_base, Scenario.rover) and item["focus"] == "prevention":
            score += 20
            reasons.append("Material flammability is relevant to proposed oxygen-enriched lunar habitats and rovers (+20).")
        elif scenario in (Scenario.spacecraft, Scenario.station) and item["id"] in ("bass", "saffire", "same", "flex"):
            score += 20
            reasons.append("Microgravity fire prevention, detection or suppression applies to this research context (+20).")
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
            "method": "topic-relevance-v1", "limitations": LIMITATIONS,
            "source_url": SOURCE}


@router.get("/compare")
def compare(ids: str = Query(..., max_length=200)):
    selected = list(dict.fromkeys(i.strip() for i in ids.split(",") if i.strip()))
    if not 2 <= len(selected) <= 4:
        raise HTTPException(422, "Choose two to four distinct investigation IDs.")
    by_id = {r["id"]: r for r in CATALOG}
    if any(i not in by_id for i in selected):
        raise HTTPException(404, "Unknown investigation ID.")
    return {"investigations": [by_id[i] for i in selected], "limitations": LIMITATIONS}
