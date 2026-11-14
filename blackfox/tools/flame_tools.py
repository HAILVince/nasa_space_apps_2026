"""Flame in Freefall evidence tools: how the agent reads flame/data (the 24 PSI combustion
investigations, their test envelopes, habitats, insights and measured material limits) and the
evidence calculator flame/calc.py.

Rules the answers must follow (also in the system prompt):
- cite the PSI accession (PSI-25) or the paper (NTRS id) given in each result's provenance/sources;
- say "not yet checked" when a row has verified=false;
- never present a microgravity result as lunar or Martian behaviour - use coverage() gaps.
Numbers < 0 mean "not given" (the registry builds schemas from plain type hints).
"""
from flame import calc, data

from .registry import tool

_FIELDS = ("accession", "acronym", "title", "kind", "fuel_phase", "topics", "summary", "psi_url")


def _inv_brief(i) -> dict:
    return {k: getattr(i, k) for k in _FIELDS}


@tool("research")
def fire_habitats() -> dict:
    """The cabin atmospheres the Flame dashboard knows (ISS, Orion, EVA suit, lunar habitat,
    pressurized rover, Mars habitat): oxygen % range, pressure kPa range, gravity, whether the values
    are assumed, and the source. Start here to turn 'Moon base' into numbers."""
    return {"habitats": [{"id": h.id, "name": h.name, "o2_pct": h.o2_pct, "pressure_kpa": h.pressure_kpa,
                          "gravity": h.gravity, "gravity_g": h.gravity_g, "assumed": h.assumed,
                          "source_url": h.source_url, "notes": h.notes} for h in data.get_habitats()]}


@tool("research")
def fire_find_investigations(topic: str = "", fuel_phase: str = "", query: str = "", limit: int = 10) -> dict:
    """List NASA PSI combustion investigations with a plain-language summary. topic: prevention,
    detection, suppression, fundamental (empty = all). fuel_phase: solid, liquid, gas, aerosol.
    query: words matched against acronym, title and summary. Use fire_get_investigation for details."""
    q = query.casefold().split()
    rows = [i for i in data.get_investigations()
            if (not topic or topic in i.topics) and (not fuel_phase or i.fuel_phase == fuel_phase)
            and all(w in f"{i.acronym} {i.title} {i.summary}".casefold() for w in q)]
    return {"count": len(rows), "investigations": [_inv_brief(i) for i in rows[:max(1, min(limit, 24))]]}


@tool("research")
def fire_get_investigation(accession: str) -> dict:
    """One PSI investigation (e.g. PSI-25 = BASS-II, PSI-99 = Saffire-II): summary, objectives,
    hardware, publications with DOI, and its test envelopes (oxygen %, pressure kPa, flow m/s,
    gravity, what was measured, key finding, provenance quotes, verified flag)."""
    i = data.get_investigation(accession.strip().upper())
    if i is None:
        return {"error": f"unknown accession '{accession}'; use fire_find_investigations"}
    out = _inv_brief(i)
    out.update(objectives=i.objectives[:1200], hardware=i.hardware, related=i.related, dataset_doi=i.doi,
               publications=[p.model_dump() for p in i.publications[:10]], n_publications=len(i.publications),
               envelopes=[e.model_dump(by_alias=False) for e in data.get_envelopes(i.accession)])
    return out


@tool("research")
def fire_coverage(habitat_id: str = "", o2_pct: float = -1, pressure_kpa: float = -1, fuel_phase: str = "") -> dict:
    """Which PSI test envelopes cover a cabin atmosphere - the data-gap check. Give habitat_id
    (from fire_habitats) OR o2_pct and pressure_kpa. Each envelope is inside / near / partial / outside /
    no_numbers, with the oxygen and pressure distance. solid_fuel_covered tells whether any burning-
    materials test was run at those conditions. fuel_phase filters (solid, liquid, gas, aerosol)."""
    phase = fuel_phase or None
    if habitat_id:
        out = calc.coverage_for_habitat(habitat_id, phase)
    elif o2_pct >= 0 and pressure_kpa > 0:
        out = calc.coverage(o2_pct, pressure_kpa, phase)
    else:
        return {"error": "give habitat_id, or both o2_pct and pressure_kpa"}
    if "envelopes" in out:   # keep the tool reply short: the closest 12 rows
        out["envelopes"] = out["envelopes"][:12]
    return out


@tool("research")
def fire_material_limits(material_id: str = "") -> dict:
    """Measured oxygen limits of a material at each gravity level on record (1 g, Mars, Moon,
    0 g) and the change vs 1 g - e.g. mylar_g, ultem_1000, nomex_ht90_40, pmma. Empty material_id
    lists the materials. These come from NASA tests outside PSI (drop-tower centrifuge, LUCI rocket)."""
    if not material_id:
        return {"materials": calc.known_materials()}
    return calc.gravity_profile(material_id)


@tool("research")
def fire_material_check(material_id: str, o2_pct: float, pressure_kpa: float, gravity: str) -> dict:
    """Is a cabin oxygen level above the measured flammability limit of a material? gravity: micro,
    lunar, martian, earth. Returns the measured limit at the nearest gravity, margin_pct (cabin O2
    minus limit; > 0 means the material was seen to burn there), margin_range_pct for the pressure
    effect, the verdict and every caveat. Evidence only - for spread, heat release and CO use
    simulate_cabin_fire."""
    return calc.material_check(material_id, o2_pct, pressure_kpa, gravity)


@tool("research")
def fire_insights(habitat_id: str) -> dict:
    """Short, cited takeaways for one habitat (moon-base, rover, mars-base, iss, orion, suit):
    what PSI covers, what it does not, and NASA results outside PSI."""
    rows = data.get_insights(habitat_id)
    if not rows:
        return {"error": f"no insights for '{habitat_id}'", "habitats": [h.id for h in data.get_habitats()]}
    return {"habitat_id": habitat_id, "insights": [{"text": r.text, "cited": r.cited} for r in rows]}
