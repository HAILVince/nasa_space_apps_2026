"""Evidence calculator: what the data can and cannot say about one cabin atmosphere.

Two questions, both answered only from flame/data (no physics model, no extrapolation):

1. coverage()      - which PSI test envelopes cover this oxygen / pressure, which are near,
                     which are far, and which have no numbers. Drives the gap map.
2. material_check() - for a material with measured limits (material_limits.json): the measured
                     oxygen limit at the nearest gravity level, the cabin's margin above it, and
                     every reason the comparison is uncertain (different pressure, short drop-tower
                     tests, gravity not measured).

The full cabin-fire screening model (spread, heat release, CO, alarm) is
blackfox/physics/fire.py; this module is the evidence layer the agent cites.
"""
from __future__ import annotations

from . import data
from .models import Envelope

# NASA WSTF (Hirsch et al., NTRS 20110008636): for materials with MOC 25-35 % O2, MOC = m*Pt + b with
# a maximum slope of -0.975 % O2 per psia - the limit RISES as total pressure falls.
MOC_SLOPE_PCT_PER_PSI = 0.975
KPA_PER_PSI = 6.89476
# "near": within this distance of an envelope edge (one of the two is enough to be useful)
NEAR_O2_PCT = 3.0
NEAR_KPA = 15.0
GRAVITY_G = {"micro": 0.0, "lunar": 0.166, "martian": 0.38, "earth": 1.0}


def _gap(rng: tuple[float, float] | None, lo: float, hi: float) -> float | None:
    """distance between the target interval [lo, hi] and an envelope range; 0 = overlap"""
    if rng is None:
        return None
    return max(0.0, rng[0] - hi, lo - rng[1])


def _status(env: Envelope, o2: tuple[float, float], kpa: tuple[float, float]) -> dict:
    d_o2, d_p = _gap(env.o2_pct, *o2), _gap(env.pressure_kpa, *kpa)
    if d_o2 is None and d_p is None:
        status = "no_numbers"
    elif d_o2 is None or d_p is None:
        known = d_o2 if d_p is None else d_p
        limit = NEAR_O2_PCT if d_p is None else NEAR_KPA
        status = "partial_overlap" if known == 0 else ("partial_near" if known <= limit else "outside")
    elif d_o2 == 0 and d_p == 0:
        status = "inside"
    elif d_o2 <= NEAR_O2_PCT and d_p <= NEAR_KPA:
        status = "near"
    else:
        status = "outside"
    return {"accession": env.accession, "label": env.label, "fuel": env.fuel, "gravity": env.gravity,
            "o2_pct": env.o2_pct, "pressure_kpa": env.pressure_kpa, "status": status,
            "o2_gap_pct": d_o2, "pressure_gap_kpa": d_p, "verified": env.verified}


def coverage(o2_pct: tuple[float, float] | float, pressure_kpa: tuple[float, float] | float,
             fuel_phase: str | None = None) -> dict:
    """Classify every envelope against a target atmosphere (single value or [min, max]).
    fuel_phase filters by the investigation's fuel phase (solid, liquid, gas, aerosol)."""
    o2 = (o2_pct, o2_pct) if isinstance(o2_pct, (int, float)) else tuple(o2_pct)
    kpa = (pressure_kpa, pressure_kpa) if isinstance(pressure_kpa, (int, float)) else tuple(pressure_kpa)
    phase = {i.accession: i.fuel_phase for i in data.get_investigations()}
    rows = [_status(e, o2, kpa) for e in data.get_envelopes()
            if fuel_phase is None or phase.get(e.accession) == fuel_phase]
    for r in rows:
        r["fuel_phase"] = phase.get(r["accession"])
    order = {"inside": 0, "near": 1, "partial_overlap": 2, "partial_near": 3, "outside": 4, "no_numbers": 5}
    rows.sort(key=lambda r: (order[r["status"]], r["o2_gap_pct"] or 0, r["accession"]))
    counts = {k: sum(r["status"] == k for r in rows) for k in order}
    solids = [r for r in rows if r["fuel_phase"] == "solid" and r["o2_pct"]]
    return {"target": {"o2_pct": o2, "pressure_kpa": kpa}, "counts": counts, "envelopes": rows,
            "solid_fuel_covered": any(r["status"] in ("inside", "partial_overlap") for r in solids),
            "max_solid_o2_tested_pct": max((r["o2_pct"][1] for r in solids), default=None),
            "note": "Envelopes are PSI test ranges (microgravity unless gravity says otherwise). "
                    "'partial_*' = one of oxygen/pressure is not reported. verified=false rows are not yet "
                    "checked against their source by a teammate."}


def coverage_for_habitat(habitat_id: str, fuel_phase: str | None = None) -> dict:
    h = data.get_habitat(habitat_id)
    if h is None:
        return {"error": f"unknown habitat '{habitat_id}'; known: {', '.join(x.id for x in data.get_habitats())}"}
    out = coverage(h.o2_pct, h.pressure_kpa, fuel_phase)
    out["habitat"] = {"id": h.id, "name": h.name, "gravity": h.gravity, "gravity_g": h.gravity_g, "assumed": h.assumed}
    if h.gravity in ("lunar", "martian"):
        out["gravity_note"] = ("PSI holds no partial-gravity combustion data; microgravity and 1 g results bound it only "
                               "loosely - for the materials measured, the lowest oxygen limit was at lunar or Martian gravity.")
    return out


def _mean_limit(m) -> float | None:
    vals = [v for v in (m.uloi_pct, m.moc_pct) if v is not None]
    return sum(vals) / len(vals) if vals else m.extinction_pct


def gravity_profile(material_id: str) -> dict:
    """Measured limit of one material at every gravity level on record, and the change vs 1 g."""
    rows = data.get_material_limits(material_id)
    if not rows:
        return {"error": f"no measured limits for '{material_id}'; known: {', '.join(known_materials())}"}
    earth = next((m for m in rows if m.gravity == "earth"), None)
    base = _mean_limit(earth) if earth else None
    levels = []
    for m in sorted(rows, key=lambda r: r.gravity_g):
        lim = _mean_limit(m)
        levels.append({"gravity": m.gravity, "gravity_g": m.gravity_g, "pressure_kpa": m.pressure_kpa,
                       "uloi_pct": m.uloi_pct, "moc_pct": m.moc_pct, "extinction_pct": m.extinction_pct,
                       "limit_pct": lim, "delta_vs_1g_pct": None if base is None or lim is None else round(lim - base, 2),
                       "method": m.method, "source": m.provenance[0].source})
    lowest = min((x for x in levels if x["limit_pct"] is not None), key=lambda x: x["limit_pct"])
    return {"material_id": material_id, "material": rows[0].material, "levels": levels,
            "lowest_limit_at": lowest["gravity"], "in_psi": any(m.in_psi for m in rows)}


def known_materials() -> list[str]:
    return sorted({m.material_id for m in data.get_material_limits()})


def material_check(material_id: str, o2_pct: float, pressure_kpa: float, gravity: str) -> dict:
    """Compare a cabin oxygen level with the measured limit of a material at the nearest gravity.
    margin > 0: cabin oxygen is above the measured limit (the material was seen to burn there).
    margin_pct is at the test pressure; margin_range_pct spans the possible pressure effect, and
    pressure_may_change_verdict flags when that range crosses the limit."""
    if gravity not in GRAVITY_G:
        return {"error": f"gravity must be one of {', '.join(GRAVITY_G)}"}
    rows = data.get_material_limits(material_id)
    if not rows:
        return {"error": f"no measured limits for '{material_id}'; known: {', '.join(known_materials())}"}
    g = GRAVITY_G[gravity]
    best = min(rows, key=lambda m: (abs(m.gravity_g - g), abs(m.pressure_kpa - pressure_kpa)))
    limit = _mean_limit(best)
    caveats = []
    if best.gravity != gravity:
        caveats.append(f"No measurement at {gravity} gravity; nearest is {best.gravity} ({best.gravity_g} g).")
    pressure_shift = None   # change of the limit going from test pressure to cabin pressure (+ = needs more O2)
    if abs(best.pressure_kpa - pressure_kpa) > 5:
        pressure_shift = round(MOC_SLOPE_PCT_PER_PSI * (best.pressure_kpa - pressure_kpa) / KPA_PER_PSI, 2)
        direction = "rises" if pressure_shift > 0 else "falls"
        caveats.append(f"Limit measured at {best.pressure_kpa} kPa, cabin is {pressure_kpa} kPa. At the same oxygen fraction the "
                       f"limit {direction} toward cabin pressure by up to {abs(pressure_shift)} points (max slope "
                       f"{MOC_SLOPE_PCT_PER_PSI} % O2 per psi for materials with MOC 25-35 %, NASA WSTF, NTRS 20110008636); "
                       "see margin_range_pct.")
    if best.gravity in ("lunar", "martian", "micro") and "drop" in best.method:
        caveats.append("Reduced-gravity limit from a 5.18 s drop test: flames may have gone out later, so it is a conservative estimate.")
    if best.extinction_pct is not None and best.uloi_pct is None:
        caveats.append("Limit is the oxygen at which one flame went out in a closed chamber, not a statistical limit.")
    if not best.in_psi:
        caveats.append("Source is a NASA test outside the PSI database.")
    if not best.verified:
        caveats.append("Row not yet checked against its source by a teammate.")
    margin = None if limit is None else round(o2_pct - limit, 2)
    if margin is None:
        mrange = None
    elif pressure_shift is None:
        mrange = (margin, margin)
    else:   # the true margin lies between "no pressure effect" and "full max-slope effect"
        mrange = tuple(sorted((margin, round(margin - pressure_shift, 2))))
    verdict = ("no_limit_on_record" if margin is None else
               "above_measured_limit" if margin > 0.5 else
               "near_measured_limit" if margin >= -0.5 else "below_measured_limit")
    flips = mrange is not None and (mrange[0] < -0.5 < mrange[1] or mrange[0] < 0.5 < mrange[1])
    return {"material_id": material_id, "material": best.material, "cabin": {"o2_pct": o2_pct, "pressure_kpa": pressure_kpa, "gravity": gravity},
            "measured_limit_pct": limit, "limit_basis": {"gravity": best.gravity, "pressure_kpa": best.pressure_kpa,
            "uloi_pct": best.uloi_pct, "moc_pct": best.moc_pct, "extinction_pct": best.extinction_pct, "method": best.method},
            "margin_pct": margin, "margin_range_pct": mrange, "pressure_may_change_verdict": flips, "verdict": verdict, "caveats": caveats,
            "sources": [f"{p.source}: {p.quote}" for p in best.provenance]}
