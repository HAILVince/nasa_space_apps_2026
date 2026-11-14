"""Cabin fire screening model: will a material burn at this place, in this gravity and
atmosphere, how fast does the fire grow, when is it detected and what does it do to the cabin?

First-order engineering model, built on numbers from the knowledge base
(blackfox/db/knowledge/curated/*.json, each read from a NASA Technical Reports Server
document) and documented below. It is a screening tool for design trades and training,
not a substitute for NASA-STD-6001 testing or CFD.

1. Flammability limit. The NASA-STD-6001 Test 1 maximum oxygen concentration (MOC) is
   interpolated in log(pressure) between the measured points of each material
   [nasa-std-6001-moc-pressure]. It is then corrected for gravity and flow:
     MOC_eff = MOC_1g(P) - 3.0 % * (1 - sqrt(g/g0)) + Q(U_eff) - 0.05 %/K * (T - 22 C)
   The 0 g limit is up to 4 % O2 below the 1 g limit (Ultem -2.75 %) [zero-g-flammability-margin],
   lunar gravity also lowers it [lunar-gravity-flammability-goldilocks]; Q is the radiative
   quench penalty in nearly quiescent flow, 2.0 * ln(6 cm/s / U_eff)^2 below 6 cm/s.
   U_eff = sqrt(U_forced^2 + U_buoyant^2), U_buoyant = 30 cm/s * sqrt(g/g0)
   [low-speed-flow-flammability].
2. Flame spread. Opposed spread over thin fuels ~ X^0.9 P^0.05 (about 1 cm/s at 21 % O2);
   concurrent spread y = 0.2498 x + 0.4038 with x linear in flow and oxygen and ~sqrt(P)
   (about 3 cm/s at 30 cm/s) [zero-g-flammability-margin]; scaled by fuel form and by
   the oxygen margin (spread falls off near the limit). Flames reach a limiting burning
   length (burnout behind the front) [saffire-iv-v-results].
3. Heat release, products. Heat release = burning rate x heat of combustion; O2 consumed
   13.1 MJ/kg (Thornton's rule); CO and smoke from yields. Heats of combustion and yields
   are typical well-ventilated values (Tewarson, SFPE Handbook), marked as such.
4. Cabin. Two zones (local enclosure + well-mixed cabin), ventilation exchange and
   transport to the smoke detector; alarm at 1 mg/m^3 smoke (model assumption between
   the clean ISS background and the 2-15 mg/m^3 of SAME-2 [same-smoke-particles]).
   CO judged against the 55 ppm 1-hour SMAC [smac-carbon-monoxide]. Closed-cabin
   pressure rise from gas heating.
5. Response. Ventilation shutdown on alarm (ISS practice) starves the flame of forced flow
   but does not extinguish it at once (a cotton flame survived 70 s without flow in
   Saffire V); portable CO2 or water-mist extinguisher after the crew response time.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

G0 = 9.80665
R_GAS = 8.314462618
LAYOUT_FILE = Path(__file__).with_name("habitat_layout.json")
KNOWLEDGE = Path(__file__).resolve().parents[1] / "db" / "knowledge"

# ---------------------------------------------------------------------------------------
# knowledge base access


@lru_cache(maxsize=1)
def curated() -> dict[str, dict]:
    """every curated record by id (small hand-checked files, read directly)"""
    out = {}
    for p in sorted((KNOWLEDGE / "curated").glob("*.json")):
        for r in json.loads(p.read_text(encoding="utf-8"))["records"]:
            out[r["id"]] = r
    return out


def fact(record_id: str, name: str) -> float:
    for f in curated()[record_id].get("facts", []):
        if f["name"] == name:
            return float(f["value"])
    raise KeyError(f"{record_id}: no fact {name!r}")


@lru_cache(maxsize=1)
def layout() -> dict:
    return json.loads(LAYOUT_FILE.read_text())


@lru_cache(maxsize=1)
def moc_table() -> dict[str, list[tuple[float, float]]]:
    rows = curated()["nasa-std-6001-moc-pressure"]["data"]["moc_table"]
    return {r["material"]: [(p["pressure_kpa"], p["moc_vol_pct"]) for p in r["points"]] for r in rows}


# ---------------------------------------------------------------------------------------
# catalog: environments, materials, locations

def _environments() -> dict:
    gr = "gravity-levels-compared"
    resid = fact("zero-g-what-microgravity-means", "typical residual acceleration on a space station")
    ea = "exploration-atmospheres"
    return {
        "leo": {"label": {"hu": "Föld körüli pálya · ISS", "en": "Earth orbit · ISS"},
                "g": resid * G0, "gravity_folder": "zero_g", "kind": "orbit", "body": "earth",
                "defaults": {"pressure_kpa": fact(ea, "ISS cabin pressure"), "o2_pct": fact(ea, "ISS cabin O2"), "temp_c": 22.0},
                "facts": [("Keringési idő / orbital period", fact("zero-g-what-microgravity-means", "ISS orbital period"), "min"),
                          ("Gravitáció 400 km-en / gravity at 400 km", fact("zero-g-what-microgravity-means", "gravity at 400 km altitude"), "m/s²"),
                          ("Maradék gyorsulás / residual acceleration", resid, "g")]},
        "lunar_orbit": {"label": {"hu": "Holdpálya · Gateway", "en": "Lunar orbit · Gateway"},
                        "g": resid * G0, "gravity_folder": "zero_g", "kind": "orbit", "body": "moon",
                        "defaults": {"pressure_kpa": fact(ea, "Gateway pressure range low"), "o2_pct": 26.5, "temp_c": 22.0},
                        "facts": [("Gateway nyomástartomány / pressure range", "70.3–101.4", "kPa"),
                                  ("Gateway O₂", "21–26.5", "%"),
                                  ("Rádiókésés / one-way radio delay", fact("moon-gravity-and-environment", "one-way radio delay"), "s")]},
        "moon": {"label": {"hu": "Holdfelszín · 0,165 g", "en": "Lunar surface · 0.165 g"},
                 "g": fact(gr, "Moon surface gravity"), "gravity_folder": "moon", "kind": "surface", "body": "moon",
                 "defaults": {"pressure_kpa": fact(ea, "exploration atmosphere pressure"), "o2_pct": fact(ea, "exploration atmosphere O2"), "temp_c": 22.0},
                 "facts": [("Felszíni gravitáció / surface gravity", fact(gr, "Moon surface gravity"), "m/s²"),
                           ("Nappal–éjszaka ciklus / day-night cycle", fact("moon-gravity-and-environment", "day-night cycle (synodic period)"), "nap/days"),
                           ("Felszíni hőmérséklet / surface temperature", "95–390", "K")]},
        "mars": {"label": {"hu": "Marsfelszín · 0,378 g", "en": "Mars surface · 0.378 g"},
                 "g": fact(gr, "Mars surface gravity"), "gravity_folder": "mars", "kind": "surface", "body": "mars",
                 "defaults": {"pressure_kpa": fact(ea, "exploration atmosphere pressure"), "o2_pct": fact(ea, "exploration atmosphere O2"), "temp_c": 22.0},
                 "facts": [("Felszíni gravitáció / surface gravity", fact(gr, "Mars surface gravity"), "m/s²"),
                           ("Légnyomás kint / outside pressure", fact("mars-gravity-and-environment", "mean surface pressure"), "mbar"),
                           ("CO₂ a légkörben / CO₂ in atmosphere", fact("mars-gravity-and-environment", "carbon dioxide in atmosphere"), "%"),
                           ("Rádiókésés / radio delay", "3–22", "min")]},
        "earth": {"label": {"hu": "Földi referencia · 1 g", "en": "Earth reference · 1 g"},
                  "g": fact(gr, "Earth surface gravity"), "gravity_folder": None, "kind": "lab", "body": "earth",
                  "defaults": {"pressure_kpa": 101.3, "o2_pct": 20.9, "temp_c": 22.0},
                  "facts": [("Gravitáció / gravity", fact(gr, "Earth surface gravity"), "m/s²")]},
    }


# Heats of combustion (effective, MJ/kg) and well-ventilated yields (kg/kg) are typical
# literature values (Tewarson, SFPE Handbook) - not NASA measurements; marked "typical".
# form: thin = fabric/film, wire = insulation on a conductor, thick = moulded part.
MATERIALS = {
    "ptfe_wire": {"moc": "PTFE", "label": {"hu": "PTFE (teflon) kábelszigetelés", "en": "PTFE (Teflon) wire insulation"},
                  "form": "wire", "dhc": 4.2, "s": 0.32, "y_co": 0.09, "y_soot": 0.003, "toxic": ["HF", "COF₂"], "color": "#d8d4c8"},
    "nomex": {"moc": "Nomex HT90-40", "label": {"hu": "Nomex HT90-40 szövet", "en": "Nomex HT90-40 fabric"},
              "form": "thin", "dhc": 21.0, "s": 2.0, "y_co": 0.05, "y_soot": 0.05, "toxic": ["HCN", "CO"], "color": "#d9cfb3"},
    "silicone": {"moc": "Silicone", "label": {"hu": "Szilikongumi (tömítés, tömlő)", "en": "Silicone rubber (seals, hoses)"},
                 "form": "thick", "dhc": 10.0, "s": 2.2, "y_co": 0.021, "y_soot": 0.065, "toxic": ["SiO₂ por / dust", "CO"], "color": "#9aa3a8"},
    "polyethylene": {"moc": "Polyethylene (PE)", "label": {"hu": "Polietilén csomagolófólia", "en": "Polyethylene packaging film"},
                     "form": "thin", "dhc": 38.4, "s": 3.43, "y_co": 0.024, "y_soot": 0.06, "toxic": ["CO"], "color": "#e7ece9"},
    "nylon": {"moc": "Zytel 42 (nylon 6,6)", "label": {"hu": "Nejlon 6,6 (Zytel 42) csatlakozó", "en": "Nylon 6,6 (Zytel 42) connector"},
              "form": "thick", "dhc": 27.1, "s": 2.33, "y_co": 0.038, "y_soot": 0.075, "toxic": ["HCN", "NH₃", "CO"], "color": "#e9e2cf"},
    "pet_film": {"moc": "Melinex 515 (PET film)", "label": {"hu": "PET fólia (Melinex 515, címke)", "en": "PET film (Melinex 515, labels)"},
                 "form": "thin", "dhc": 16.0, "s": 1.67, "y_co": 0.05, "y_soot": 0.09, "toxic": ["CO"], "color": "#dfe6ea"},
    "ultem": {"moc": "Ultem 1000", "label": {"hu": "Ultem 1000 (PEI) panel", "en": "Ultem 1000 (PEI) panel"},
              "form": "thick", "dhc": 19.0, "s": 2.3, "y_co": 0.026, "y_soot": 0.05, "toxic": ["CO", "HCN"], "color": "#b9873e"},
    "delrin": {"moc": "Delrin (acetal)", "label": {"hu": "Delrin (acetál) alkatrész", "en": "Delrin (acetal) part"},
               "form": "thick", "dhc": 14.4, "s": 1.07, "y_co": 0.001, "y_soot": 0.001, "toxic": ["formaldehid / formaldehyde"], "color": "#f2f1ec"},
    "viton": {"moc": "Viton-A", "label": {"hu": "Viton-A O-gyűrű", "en": "Viton-A O-ring"},
              "form": "thick", "dhc": 6.0, "s": 0.5, "y_co": 0.07, "y_soot": 0.04, "toxic": ["HF", "CO"], "color": "#2b2b2b"},
    "kydex": {"moc": "Kydex 100", "label": {"hu": "Kydex 100 burkolólemez", "en": "Kydex 100 closeout panel"},
              "form": "thick", "dhc": 12.0, "s": 1.4, "y_co": 0.06, "y_soot": 0.12, "toxic": ["HCl", "CO"], "color": "#c8ccc6"},
}
# form factors: spread relative to the thin-cellulose correlations, burnout time,
# reference burning rate (g/m^2 s) in air at 1 g
FORMS = {"thin": (0.55, 8.0, 12.0), "wire": (0.22, 30.0, 7.0), "thick": (0.09, 240.0, 11.0)}

LOCATIONS_LABEL = {
    "avionics_rack": {"hu": "Avionikai rack (zárt, saját ventilátor)", "en": "Avionics rack (enclosed, own fan)"},
    "cable_standoff": {"hu": "Kábelcsatorna a burkolat mögött", "en": "Cable run behind closeout"},
    "crew_quarters": {"hu": "Személyzeti hálófülke", "en": "Crew quarters"},
    "galley": {"hu": "Konyha / étkezőasztal", "en": "Galley table"},
    "stowage": {"hu": "Raktérzsákok (CTB)", "en": "Stowage bags (CTB)"},
    "glovebox": {"hu": "Kísérleti kesztyűsdoboz", "en": "Experiment glovebox"},
}
ENCLOSURE_VOLUME = {"rack": 0.45, "closeout": 0.9, "crew_quarters": 2.1, "glovebox": 0.25, "open": 4.0}
DEFAULT_MATERIAL = {"avionics_rack": "ultem", "cable_standoff": "ptfe_wire", "crew_quarters": "nomex",
                    "galley": "polyethylene", "stowage": "nomex", "glovebox": "delrin"}
SMOKE_ALARM_MG_M3 = 1.0
THORNTON_MJ_PER_KG_O2 = 13.1


def catalog() -> dict:
    envs = _environments()
    lay = layout()
    return {
        "provenance": "Numbers from blackfox/db/knowledge/curated (NASA NTRS sources); heats of combustion and yields are typical literature values.",
        "environments": {k: {"label": v["label"], "g_m_s2": v["g"], "g_fraction": v["g"] / G0, "kind": v["kind"],
                             "body": v["body"], "defaults": v["defaults"],
                             "facts": [{"name": n, "value": val, "unit": u} for n, val, u in v["facts"]]}
                         for k, v in envs.items()},
        "materials": {k: {"label": m["label"], "form": m["form"], "moc_material": m["moc"],
                          "moc_points": [{"pressure_kpa": p, "moc_pct": v} for p, v in moc_table()[m["moc"]]],
                          "heat_of_combustion_mj_kg": m["dhc"], "toxic_products": m["toxic"], "color": m["color"]}
                      for k, m in MATERIALS.items()},
        "locations": {k: {"label": LOCATIONS_LABEL[k], "anchor": v["anchor"], "enclosure": v["enclosure"],
                          "default_material": DEFAULT_MATERIAL[k]} for k, v in lay["locations"].items()},
        "layout": {"ventilation": lay["ventilation"], "free_gas_volume_m3": lay["module"]["free_gas_volume_m3"]},
        "limits": {"pressure_kpa": [20, 110], "o2_pct": [15, 50], "temp_c": [5, 45], "vent_cm_s": [0, 40]},
        "references": {"co_smac_1h_ppm": fact("smac-carbon-monoxide", "CO 1-hour SMAC"),
                       "co_smac_24h_ppm": fact("smac-carbon-monoxide", "CO 24-hour SMAC"),
                       "ventilation_nominal_cm_s": [fact("zero-g-flammability-margin", "nominal spacecraft ventilation, low"),
                                                    fact("zero-g-flammability-margin", "nominal spacecraft ventilation, high")],
                       "smoke_alarm_mg_m3": SMOKE_ALARM_MG_M3},
    }


# ---------------------------------------------------------------------------------------
# physics

def moc_1g(material: str, pressure_kpa: float) -> float:
    """NASA-STD-6001 Test 1 MOC (% O2) at a total pressure, log-pressure interpolation of the
    measured points; outside them the nearest segment's slope is extended (and kept >= 0
    so lower pressure never makes a material easier to burn), with the steep rise below
    41 kPa reported by the source."""
    pts = moc_table()[MATERIALS[material]["moc"]]
    lp = math.log(max(pressure_kpa, 5.0))
    xs = [math.log(p) for p, _ in pts]
    ys = [v for _, v in pts]
    if len(pts) == 1:
        val = ys[0]
    else:
        i = 0 if lp < xs[0] else len(xs) - 2 if lp > xs[-1] else max(k for k in range(len(xs) - 1) if xs[k] <= lp)
        slope = (ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i])
        if lp < xs[0] or lp > xs[-1]:
            slope = min(slope, 0.0)
        val = ys[i] + slope * (lp - xs[i])
    if pressure_kpa < 41.0:
        val += 10.0 * math.log(41.0 / pressure_kpa)
    return min(100.0, max(val, 5.0))


def buoyant_velocity_cm_s(g: float) -> float:
    return fact("low-speed-flow-flammability", "typical buoyant flow speed near a flame on Earth") * math.sqrt(max(g, 0.0) / G0)


def gravity_shift(g: float) -> float:
    return -3.0 * (1.0 - math.sqrt(min(max(g, 0.0) / G0, 1.0)))


def quench_penalty(u_eff_cm_s: float) -> float:
    return 2.0 * max(0.0, math.log(6.0 / max(u_eff_cm_s, 0.01))) ** 2


def effective_moc(material: str, pressure_kpa: float, g: float, u_eff_cm_s: float, temp_c: float) -> dict:
    base = moc_1g(material, pressure_kpa)
    dg, dq, dt = gravity_shift(g), quench_penalty(u_eff_cm_s), -0.05 * (temp_c - 22.0)
    return {"moc_1g": base, "gravity_shift": dg, "quench_penalty": dq, "temperature_shift": dt,
            "moc_eff": min(100.0, base + dg + dq + dt)}


def spread_rate_cm_s(material: str, o2_pct: float, pressure_kpa: float, u_eff_cm_s: float, margin: float) -> dict:
    x = o2_pct / 100.0
    v_opp = 1.0 * (x / 0.21) ** 0.9 * (pressure_kpa / 101.3) ** 0.05
    corr = 10.4 * (u_eff_cm_s / 30.0) * (x / 0.21) * math.sqrt(pressure_kpa / 101.3)
    v_conc = 0.2498 * corr + 0.4038 if u_eff_cm_s > 0.5 else 0.0
    k = FORMS[MATERIALS[material]["form"]][0]
    near_limit = 1.0 - math.exp(-max(margin, 0.0) / 3.0)
    return {"opposed": v_opp * k * near_limit, "concurrent": v_conc * k * near_limit,
            "rate": max(v_opp, v_conc) * k * near_limit, "near_limit_factor": near_limit}


def flame_temperature_k(material: str, o2_pct: float, temp_c: float, u_eff_cm_s: float) -> float:
    """Burke-Schumann diffusion-flame temperature with a radiative loss fraction that grows
    with soot and with low flow (longer residence time)."""
    m = MATERIALS[material]
    x = o2_pct / 100.0
    y_o2 = 32 * x / (32 * x + 28 * (1 - x))
    dt = m["dhc"] * 1e6 / 1300.0 * y_o2 / (m["s"] + y_o2)
    chi = 0.15 + 2.0 * m["y_soot"] + 0.2 * math.exp(-u_eff_cm_s / 5.0)
    return min(temp_c + 273.15 + (1 - min(chi, 0.6)) * dt, 2450.0)


def _local_flow(loc: dict, vent_cm_s: float, vent_on: bool) -> float:
    if loc["local_flow_m_s"] > 0:                      # enclosure with its own fan
        return loc["local_flow_m_s"] * 100.0 if vent_on else 0.0
    return vent_cm_s * loc["local_flow_factor"] if vent_on else 0.0


def simulate(environment: str = "leo", material: str | None = None, location: str = "avionics_rack",
             pressure_kpa: float | None = None, o2_pct: float | None = None, temp_c: float | None = None,
             vent_cm_s: float = 12.0, auto_vent_shutdown: bool = True, suppression: str = "co2",
             response_s: float = 60.0, duration_s: float = 480.0) -> dict:
    envs = _environments()
    if environment not in envs:
        raise ValueError(f"unknown environment {environment!r}")
    lay = layout()
    if location not in lay["locations"]:
        raise ValueError(f"unknown location {location!r}")
    material = material or DEFAULT_MATERIAL[location]
    if material not in MATERIALS:
        raise ValueError(f"unknown material {material!r}")
    if suppression not in ("none", "co2", "water_mist"):
        raise ValueError("suppression must be none, co2 or water_mist")
    env = envs[environment]
    d = env["defaults"]
    p = float(d["pressure_kpa"] if pressure_kpa is None else pressure_kpa)
    x_pct = float(d["o2_pct"] if o2_pct is None else o2_pct)
    t_c = float(d["temp_c"] if temp_c is None else temp_c)
    if not (10 <= p <= 120 and 10 <= x_pct <= 100 and -20 <= t_c <= 60 and 0 <= vent_cm_s <= 100):
        raise ValueError("atmosphere outside the model range")
    g = env["g"]
    m = MATERIALS[material]
    loc = lay["locations"][location]
    spread_k, burnout_s, mref = FORMS[m["form"]]

    u_b = buoyant_velocity_cm_s(g)
    u_f0 = _local_flow(loc, vent_cm_s, True)
    u_eff0 = math.hypot(u_f0, u_b)
    lim0 = effective_moc(material, p, g, u_eff0, t_c)
    margin0 = x_pct - lim0["moc_eff"]
    spread0 = spread_rate_cm_s(material, x_pct, p, u_eff0, margin0)
    t_flame0 = flame_temperature_k(material, x_pct, t_c, u_eff0)

    # cabin gas
    v_cabin = lay["module"]["free_gas_volume_m3"]
    v_loc = ENCLOSURE_VOLUME[loc["enclosure"]]
    t0 = t_c + 273.15
    n_gas = p * 1e3 * v_cabin / (R_GAS * t0)                      # mol
    rho = p * 1e3 * (0.032 * x_pct / 100 + 0.028 * (1 - x_pct / 100)) / (R_GAS * t0)
    m_gas = rho * v_cabin
    n_o2 = n_gas * x_pct / 100
    # detector distance and transport
    anchor = loc["anchor"]
    det = lay["ventilation"]["cabin_detector"]
    dist = loc["local_detector_m"] or math.dist(anchor, det)
    fuel_len, fuel_w, fuel_mass = loc["fuel_length_m"], loc["fuel_width_m"], loc["fuel_mass_kg"]

    dt_s = 0.5
    steps = int(duration_s / dt_s)
    front = 0.02             # burning front position along the fuel (m), ignition patch 2 cm
    burned = 0.0
    co_cabin = soot_cabin = soot_loc = co_loc = 0.0          # kg
    t_gas = t0
    alive, ignited_until = True, 6.0                          # igniter heats the sample for 6 s
    vent_on, decay_tau, decay_from = True, None, None
    events = [{"t": 0.0, "key": "ignition"}]
    t_alarm = t_resp = t_out = t_sensed = None
    peak = {"hrr_kw": 0.0, "co_ppm": 0.0, "dp_kpa": 0.0, "smoke_mg_m3": 0.0}
    series = []
    smac = fact("smac-carbon-monoxide", "CO 1-hour SMAC")
    t_smac = None
    hrr = 0.0
    margin = margin0
    nl_last = 0.0
    burning_len = 0.02
    for k in range(steps + 1):
        t = k * dt_s
        u_f = _local_flow(loc, vent_cm_s, vent_on)
        u_eff = math.hypot(u_f, u_b)
        x_now = n_o2 / n_gas * 100
        lim = effective_moc(material, p, g, u_eff, t_c)
        margin = x_now - lim["moc_eff"]
        sp = spread_rate_cm_s(material, x_now, p, u_eff, margin)
        # flame strength 0..1
        if alive:
            if margin <= 0 and t > ignited_until and decay_tau is None:
                decay_tau, decay_from = 4.0 + 6.0 * max(margin0, 0.0) + (0 if m["form"] == "thin" else 6.0), t
            strength = 1.0 if decay_tau is None else math.exp(-(t - decay_from) / decay_tau)
            if margin > 0 and decay_tau is not None and t_resp is None:
                decay_tau = None                                     # recovered (e.g. igniter period)
                strength = 1.0
            if strength < 0.04 or burned >= fuel_mass * 0.98:
                alive = False
                t_out = t
                events.append({"t": t, "key": "self_extinguished" if t_resp is None else "extinguished",
                               "detail": "burnout" if burned >= fuel_mass * 0.98 else ""})
        else:
            strength = 0.0
        if alive:
            if margin > 0:
                front = min(fuel_len, front + sp["rate"] / 100 * dt_s)
            if sp["rate"] > 0:
                burning_len = min(front, max(sp["rate"] / 100 * burnout_s, 0.02))
            # the fire grows as a patch from the ignition point; without a positive margin only
            # the 2 x 2 cm patch under the igniter burns
            if margin > 0 or decay_tau is not None:
                area = min(fuel_w, 0.02 + 2 * front) * max(burning_len, 0.02)
            else:
                area = min(fuel_w, 0.02) * 0.02
            # burning-rate model and an igniter-sustained patch while margin <= 0
            mpp = mref * (x_now / 21.0) * (max(u_eff, 1.0) / 20.0) ** 0.3 * (p / 101.3) ** 0.3
            if sp["near_limit_factor"] > 0:
                nl_last = sp["near_limit_factor"]
            # a dying flame (no longer above its limit) keeps burning at its last rate x strength
            mpp *= max(sp["near_limit_factor"], nl_last if decay_tau is not None else 0.0,
                       0.25 if t <= ignited_until else 0.0)
            mdot = mpp * area * strength / 1000.0                 # kg/s
            mdot = min(mdot, max(fuel_mass - burned, 0.0) / dt_s)
        else:
            mdot, burning_len = 0.0, 0.0
        burned += mdot * dt_s
        hrr = mdot * m["dhc"] * 1e3                               # kW
        # products: local zone exchanges with the cabin
        o2_used = hrr / THORNTON_MJ_PER_KG_O2 / 1e3 * dt_s / 0.032   # mol
        n_o2 = max(n_o2 - o2_used, 0.0)
        soot_rate = mdot * m["y_soot"] * (1.4 if g < 0.1 else 1.0)   # longer residence in 0 g
        co_rate = mdot * m["y_co"]
        exch = (max(u_f, 0.3) / 100 * 0.25 + (0.04 * u_b / 100 if loc["enclosure"] == "open" else 0.006 * u_b / 100)) / v_loc
        soot_loc += soot_rate * dt_s - soot_loc * min(exch * dt_s, 1.0)
        co_loc += co_rate * dt_s - co_loc * min(exch * dt_s, 1.0)
        soot_cabin += soot_loc * min(exch * dt_s, 1.0)
        co_cabin += co_loc * min(exch * dt_s, 1.0)
        # cabin air scrubbing / filtration when ventilation runs (HEPA, 1 cabin volume per ~10 min)
        if vent_on:
            soot_cabin *= 1 - dt_s / 600.0
        # closed-cabin heating
        t_gas += (0.35 * hrr * 1e3 / (m_gas * 718.0) - (t_gas - t0) / 120.0) * dt_s
        dp = p * (t_gas / t0 - 1.0)
        co_ppm = co_cabin / 0.028 / n_gas * 1e6
        smoke_loc = soot_loc / v_loc * 1e6
        transport = dist / max(u_f / 100 if vent_on else 0.0, u_b / 100 * 0.3, 0.003)
        smoke_det = (soot_loc / v_loc if loc["local_detector_m"] else soot_cabin / v_cabin) * 1e6
        # detection
        if t_alarm is None:
            seen = loc["crew_visibility"] > 0 and alive and hrr > 0.02 and t > 4.0 / loc["crew_visibility"] + 2
            if smoke_det >= SMOKE_ALARM_MG_M3 and t >= (0 if loc["local_detector_m"] else transport):
                t_sensed = t if t_sensed is None else t_sensed
            # detectors sample and confirm for about 5 s before they alarm
            if (t_sensed is not None and t >= t_sensed + 5.0) or seen:
                t_alarm = t
                events.append({"t": t, "key": "alarm", "detail": "detector" if t_sensed is not None else "crew"})
                if auto_vent_shutdown:
                    vent_on = False
                    events.append({"t": t, "key": "vent_off"})
        if t_alarm is not None and t_resp is None and t >= t_alarm + response_s:
            t_resp = t
            if suppression != "none" and alive:
                events.append({"t": t, "key": suppression})
                # CO2 dilutes the local oxygen far below any MOC; water mist cools the surface
                decay_tau, decay_from = (3.0 if suppression == "co2" else 5.0) * (1 + hrr / 5.0), t
            elif alive:
                events.append({"t": t, "key": "crew_on_scene"})
        if t_smac is None and co_ppm >= smac:
            t_smac = t
            events.append({"t": t, "key": "co_smac"})
        peak["hrr_kw"] = max(peak["hrr_kw"], hrr)
        peak["co_ppm"] = max(peak["co_ppm"], co_ppm)
        peak["dp_kpa"] = max(peak["dp_kpa"], dp)
        peak["smoke_mg_m3"] = max(peak["smoke_mg_m3"], smoke_loc)
        if k % 4 == 0:
            series.append({"t": t, "hrr_kw": round(hrr, 4), "front_m": round(front if alive or burned else 0, 4),
                           "flame": round(strength if alive else 0.0, 3), "o2_pct": round(x_now, 3),
                           "co_ppm": round(co_ppm, 3), "smoke_local": round(smoke_loc, 3),
                           "smoke_detector": round(smoke_det, 3), "dp_kpa": round(dp, 4),
                           "vent": vent_on, "margin": round(margin, 2)})
    flammable = margin0 > 0
    t_flame = flame_temperature_k(material, x_pct, t_c, u_eff0)
    soot_index = min(1.5, m["y_soot"] / 0.06 * (p / 101.3) ** 1.5 * (1.3 if g < 0.1 else 1.0))
    elong = 1.0 + 2.2 * (u_b / 30.0) ** 0.8 + 1.1 * (u_f0 / 30.0)
    verdict = _verdict(flammable, margin0, t_alarm, peak, smac, t_out)
    return {
        "inputs": {"environment": environment, "material": material, "location": location, "pressure_kpa": p,
                   "o2_pct": x_pct, "temp_c": t_c, "vent_cm_s": vent_cm_s, "auto_vent_shutdown": auto_vent_shutdown,
                   "suppression": suppression, "response_s": response_s, "duration_s": duration_s},
        "atmosphere": {"o2_partial_kpa": p * x_pct / 100, "density_kg_m3": rho, "gravity_m_s2": g,
                       "gravity_fraction": g / G0, "cabin_gas_volume_m3": v_cabin},
        "flammability": {**lim0, "o2_pct": x_pct, "margin_pct": margin0, "flammable": flammable,
                         "buoyant_flow_cm_s": u_b, "forced_flow_cm_s": u_f0, "effective_flow_cm_s": u_eff0},
        "flame": {"spread_cm_s": spread0["rate"], "opposed_cm_s": spread0["opposed"], "concurrent_cm_s": spread0["concurrent"],
                  "temperature_k": t_flame0 if flammable else t_flame * 0.85, "soot_index": soot_index,
                  "elongation": elong if flammable else 1.0, "flow_dir": [1.0, 0.0, 0.0],
                  "buoyancy": min(1.0, u_b / 30.0), "color_hint": m["color"]},
        "timeline": {"alarm_s": t_alarm, "response_s": t_resp, "extinguished_s": t_out, "co_smac_s": t_smac,
                     "detector_distance_m": dist, "events": events},
        "peaks": {**peak, "burned_g": burned * 1000, "co_smac_1h_ppm": smac},
        "series": series,
        "map": flammability_map(material, g, u_eff0, t_c),
        "verdict": verdict,
        "knowledge": ["nasa-std-6001-moc-pressure", "zero-g-flammability-margin", "saffire-iv-v-results",
                      "lunar-gravity-flammability-goldilocks", "exploration-atmospheres", "smac-carbon-monoxide",
                      "same-smoke-particles", "low-speed-flow-flammability"],
        "assumptions": ["heats of combustion and yields: typical literature values (SFPE), not NASA measurements",
                        "smoke alarm threshold 1 mg/m3 (model assumption)", "two-zone well-mixed cabin",
                        "gravity shift -3 % O2 x (1 - sqrt(g/g0)), from 0 g tests (up to -4 %)"],
    }


def flammability_map(material: str, g: float, u_eff_cm_s: float, temp_c: float) -> dict:
    """oxygen-pressure map for the chart: the measured 1 g limit, the corrected limit at this
    gravity and flow, and the normoxic curve (same O2 partial pressure as sea-level air)"""
    ps = [20 + 2 * i for i in range(46)]
    return {"pressure_kpa": ps,
            "moc_1g": [round(moc_1g(material, q), 2) for q in ps],
            "moc_eff": [round(effective_moc(material, q, g, u_eff_cm_s, temp_c)["moc_eff"], 2) for q in ps],
            "normoxic": [round(min(100.0, 21.3 / q * 100), 2) for q in ps],
            "measured": [{"pressure_kpa": q, "moc_pct": v} for q, v in moc_table()[MATERIALS[material]["moc"]]]}


def _verdict(flammable, margin, t_alarm, peak, smac, t_out) -> dict:
    if not flammable:
        level = "low"
    elif peak["co_ppm"] >= smac or peak["hrr_kw"] > 5:
        level = "critical"
    elif t_alarm is None or t_alarm > 60 or margin > 6:
        level = "high"
    else:
        level = "elevated"
    return {"level": level, "flammable": flammable, "margin_pct": round(margin, 2),
            "detected": t_alarm is not None, "contained": t_out is not None}


# ---------------------------------------------------------------------------------------
# research evidence: only fire-relevant topics (no biology, health, radiation, ...)

RELEVANT_TOPICS = ("combustion_fire", "habitats_structures", "life_support", "materials_manufacturing",
                   "fluids_heat_transfer")
OFF_TOPIC_WORDS = ("plant", "microb", "bacteri", "cell ", "cells", "gene", "bone", "muscle", "mice", "rat ",
                   "rats", "seed", "root", "yeast", "biofilm", "astronaut health", "immune", "radiation",
                   "reentry", "hypersonic", "entry vehicle", "rocket engine", "propellant", "thruster")


def relevant(rec: dict) -> bool:
    if rec.get("topic") and rec["topic"] not in RELEVANT_TOPICS:
        return False
    text = (str(rec.get("title", "")) + " " + str(rec.get("summary", ""))[:400]).lower()
    return not any(w in text for w in OFF_TOPIC_WORDS)


def evidence(environment: str, material: str, store=None, limit: int = 8) -> list[dict]:
    envs = _environments()
    env = envs.get(environment) or envs["leo"]
    m = MATERIALS.get(material) or MATERIALS["nomex"]
    cur = curated()
    picks = ["nasa-std-6001-moc-pressure", "zero-g-flammability-margin" if env["g"] < 0.1 * G0
             else "lunar-gravity-flammability-goldilocks", "saffire-iv-v-results", "exploration-atmospheres",
             "smac-carbon-monoxide"]
    out = [{"slug": i, "title": cur[i]["title"], "summary": cur[i]["summary"], "year": cur[i].get("year"),
            "source": "Black Fox curated · NASA NTRS", "url": (cur[i].get("sources") or [{}])[0].get("url", ""),
            "status": "curated"} for i in picks if i in cur]
    if store is not None:
        name = m["moc"].split(" (")[0]
        queries = [f"{name} flammability", "spacecraft fire flame spread microgravity", "material flammability oxygen"]
        seen = {o["slug"] for o in out}
        for q in queries:
            try:
                hits = store.search(q, gravity=env["gravity_folder"], topic="combustion_fire", limit=10)
            except Exception:       # index still building or unavailable: curated evidence is enough
                hits = []
            for h in hits:
                if len(out) >= limit:
                    break
                if h.get("slug") and h["slug"] not in seen and relevant(h):
                    seen.add(h["slug"])
                    out.append({k: h.get(k) for k in ("slug", "title", "summary", "year", "source", "url", "status")})
    return out[:limit]
