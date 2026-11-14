"""Data for the gap map: total pressure (x) against oxygen percentage (y).

Python only decides what is on the map; the page draws it.

rectangles  envelopes that state both oxygen and pressure
unplaced    envelopes missing one of the two. They cannot be drawn, so they are listed.
habitats    the planned cabin atmospheres, as ranges
incidents   historic cabin fires with a known atmosphere (Apollo 13 was not a cabin fire)
isoPo2      curves of constant oxygen partial pressure: what the lungs and, roughly, a flame see
coverage    per habitat, how many investigations have an envelope that overlaps its atmosphere (any fuel).
            Same rule as "inside" in flame.calc.coverage; gravity is not considered here.
coverageByPhase  the same count split by fuel phase (solid, liquid, gas, aerosol). A habitat can be covered by
            gas and liquid fuel tests and still have no solid-fuel test: that is the gap that matters for
            cabin materials, and the page must not have to recompute the overlap rule to show it.
coveredBy   the accessions behind each coverage count, so a page can name them.
"""

from . import data

AXES = {"pressureKPa": (0, 120), "o2Pct": (0, 100)}
PHASES = ("solid", "liquid", "gas", "aerosol")
ISO_PO2 = ((21.3, "sea-level air"), (29.6, "pure oxygen at suit pressure"), (50.0, "50 kPa of oxygen"))


def iso_po2_curve(po2_kpa: float, step: float = 2.0) -> list[tuple[float, float]]:
    """(pressure, oxygen %) points with pressure * oxygen = po2, from 100 % oxygen out to the axis end."""
    end = AXES["pressureKPa"][1]
    pressures = [po2_kpa]
    while pressures[-1] + step < end:
        pressures.append(round(pressures[-1] + step, 6))
    return [(p, 100 * po2_kpa / p) for p in [*pressures, end]]


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def gap_map(micro_only: bool = False, *, envelopes=None, investigations=None, habitats=None, incidents=None) -> dict:
    envelopes = data.get_envelopes() if envelopes is None else envelopes
    by_acc = {i.accession: i for i in (data.get_investigations() if investigations is None else investigations)}
    habitats = data.get_habitats() if habitats is None else habitats
    incidents = data.get_incidents() if incidents is None else incidents
    if micro_only:
        envelopes = [e for e in envelopes if e.gravity == "micro"]

    rectangles, unplaced = [], []
    for e in envelopes:
        name = by_acc[e.accession].acronym if e.accession in by_acc else e.accession
        if e.o2_pct and e.pressure_kpa:
            rectangles.append({"accession": e.accession, "acronym": name, "label": e.label, "fuel": e.fuel,
                               "fuelPhase": by_acc[e.accession].fuel_phase if e.accession in by_acc else "none",
                               "gravity": e.gravity, "o2Pct": e.o2_pct, "pressureKPa": e.pressure_kpa,
                               "verified": e.verified, "keyFinding": e.key_finding})
        else:
            missing = [k for k, v in (("o2Pct", e.o2_pct), ("pressureKPa", e.pressure_kpa)) if not v]
            unplaced.append({"accession": e.accession, "acronym": name, "label": e.label, "missing": missing})

    covering = {h.id: [r for r in rectangles
                       if _overlap(h.o2_pct, r["o2Pct"]) and _overlap(h.pressure_kpa, r["pressureKPa"])]
                for h in habitats}
    coverage = {hid: len({r["accession"] for r in rs}) for hid, rs in covering.items()}
    coverage_by_phase = {hid: {ph: len({r["accession"] for r in rs if r["fuelPhase"] == ph}) for ph in PHASES}
                         for hid, rs in covering.items()}
    return {
        "axes": AXES,
        "rectangles": rectangles,
        "unplaced": unplaced,
        "habitats": [{"id": h.id, "name": h.name, "o2Pct": h.o2_pct, "pressureKPa": h.pressure_kpa,
                      "gravity": h.gravity, "assumed": h.assumed} for h in habitats],
        "incidents": [{"id": i.id, "name": i.name, "year": i.year, "o2Pct": i.o2_pct, "pressureKPa": i.pressure_kpa,
                       "lesson": i.lesson} for i in incidents if i.cabin_fire and i.o2_pct and i.pressure_kpa],
        "isoPo2": [{"po2KPa": po2, "label": label, "points": iso_po2_curve(po2)} for po2, label in ISO_PO2],
        "coverage": coverage,
        "coverageByPhase": coverage_by_phase,
        "coveredBy": {hid: sorted({r["accession"] for r in rs}, key=lambda a: int(a[4:]))
                      for hid, rs in covering.items()},
    }
