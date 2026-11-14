"""Read-only Flame in Freefall endpoints: search, ranking per habitat, gap map.

The calculator endpoints (context, check, coverage, tests, sweep) live in main.py; these
three views sit on flame/search.py, flame/rank.py and flame/gapmap.py. No AI, no cookies.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from flame import data
from flame.gapmap import gap_map
from flame.rank import DEFAULT_WEIGHTS, Weights, rank_for_habitat
from flame.search import search_investigations

router = APIRouter(prefix="/api/flame")

FuelPhase = Literal["solid", "liquid", "gas", "aerosol", "none"]
Topic = Literal["prevention", "detection", "suppression", "fundamental"]


@router.get("/investigations")
def investigations(q: str = Query("", max_length=200), fuel_phase: FuelPhase | None = None,
                   kind: Literal["flight", "ground"] | None = None, topic: Topic | None = None,
                   hardware: str | None = Query(None, max_length=60)):
    """Keyword search with filters. No q: everything that passes the filters, by accession."""
    hits = search_investigations(q, fuel_phase=fuel_phase, kind=kind, topic=topic, hardware=hardware, k=None)
    rows = []
    for hit in hits:
        inv = data.get_investigation(hit.accession)
        rows.append({**hit._asdict(), "kind": inv.kind, "fuelPhase": inv.fuel_phase, "topics": inv.topics,
                     "hardware": inv.hardware, "psiUrl": inv.psi_url})
    return {"count": len(rows), "investigations": rows}


@router.get("/investigations/{accession}")
def investigation(accession: str):
    inv = data.get_investigation(accession)
    if inv is None:
        raise HTTPException(404, "Unknown PSI accession.")
    return {**inv.model_dump(by_alias=True),
            "envelopes": [e.model_dump(by_alias=True) for e in data.get_envelopes(accession)]}


def _weight(default: float):
    return Query(default, ge=0, le=1)


@router.get("/habitats/{habitat_id}/ranking")
def ranking(habitat_id: str, condition: float = _weight(DEFAULT_WEIGHTS.condition),
            topic: float = _weight(DEFAULT_WEIGHTS.topic), fuel: float = _weight(DEFAULT_WEIGHTS.fuel),
            flight: float = _weight(DEFAULT_WEIGHTS.flight)):
    """Investigations ordered by how close their test conditions are to one cabin atmosphere."""
    h = data.get_habitat(habitat_id)
    if h is None:
        raise HTTPException(404, "Unknown habitat.")
    weights = Weights(condition, topic, fuel, flight)
    rows = [{"accession": r.accession, "acronym": r.acronym, "title": r.title, "score": round(r.score, 4),
             "parts": {k: round(v, 4) for k, v in r.parts.items()}, "noConditionData": r.no_condition_data}
            for r in rank_for_habitat(h, weights=weights)]
    return {"habitat": {"id": h.id, "name": h.name, "o2Pct": h.o2_pct, "pressureKPa": h.pressure_kpa,
                        "gravity": h.gravity, "assumed": h.assumed},
            "weights": weights._asdict(),
            "method": "score = sum of weight x part; condition = closeness of the nearest test envelope in "
                      "oxygen and log pressure, scaled down when gravity differs. A judgement, not a risk estimate.",
            "investigations": rows}


@router.get("/gapmap")
def gapmap(micro_only: bool = False):
    """What to draw on the oxygen-vs-pressure map, and how many investigations cover each habitat."""
    return gap_map(micro_only)
