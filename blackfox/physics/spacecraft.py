"""Habitat / spacecraft design simulator.

A design is plain JSON:

    {"name": "...", "kind": "habitat" | "spacecraft",
     "environment": {"location": "mars_surface", "crew": 4, "mission_days": 500,
                     "cabin_pressure_kpa": 70.3},
     "parts": {"hab": {"type": "pressurized_module", "radius_m": 3.0, ...}, ...},
     "selected": "hab"}

simulate(design) is deterministic and first-order (sizing-level, not CFD/FEA): every
number comes from a formula below, so the agent never has to invent one.
SI units unless the property name says otherwise.
"""

import math
from copy import deepcopy

G0 = 9.80665
SIGMA = 5.670374419e-8          # Stefan-Boltzmann, W/m^2/K^4
R_AIR = 287.05                  # J/kg/K
CABIN_T = 295.0                 # K

# location -> solar irradiance at the location (W/m^2), mean fraction of time in sunlight,
# longest dark period (h), radiator sink temperature (K), surface gravity (m/s^2), dust/atm. loss
LOCATIONS = {
    "leo":          {"irradiance": 1361, "sun_fraction": 0.62, "dark_h": 0.6,   "sink_k": 250, "g": 0.0,  "loss": 0.0},
    "lunar_orbit":  {"irradiance": 1361, "sun_fraction": 0.80, "dark_h": 2.5,   "sink_k": 200, "g": 0.0,  "loss": 0.0},
    "moon_surface": {"irradiance": 1361, "sun_fraction": 0.50, "dark_h": 354.0, "sink_k": 250, "g": 1.62, "loss": 0.0},
    "moon_south_pole": {"irradiance": 1361, "sun_fraction": 0.85, "dark_h": 100.0, "sink_k": 150, "g": 1.62, "loss": 0.0},
    "mars_transit": {"irradiance": 900,  "sun_fraction": 1.00, "dark_h": 0.0,   "sink_k": 30,  "g": 0.0,  "loss": 0.0},
    "mars_surface": {"irradiance": 590,  "sun_fraction": 0.45, "dark_h": 13.0,  "sink_k": 210, "g": 3.71, "loss": 0.35},
    "deep_space":   {"irradiance": 1361, "sun_fraction": 1.00, "dark_h": 0.0,   "sink_k": 30,  "g": 0.0,  "loss": 0.0},
}

# density kg/m^3, allowable (yield) stress Pa
MATERIALS = {
    "aluminum_2219": {"density": 2840, "yield_pa": 290e6},
    "aluminum_lithium_2195": {"density": 2710, "yield_pa": 490e6},
    "titanium_6al4v": {"density": 4430, "yield_pa": 880e6},
    "stainless_304": {"density": 8000, "yield_pa": 215e6},
    "carbon_composite": {"density": 1600, "yield_pa": 600e6},
    "vectran_inflatable": {"density": 1400, "yield_pa": 1000e6},
}

# per crew member per day (NASA BVAD-style round numbers)
O2_KG = 0.84
WATER_KG = 3.6          # drinking + food prep + hygiene
FOOD_KG = 1.8
METABOLIC_W = 120.0     # heat per crew member
CREW_POWER_KW = 1.0     # ECLSS + avionics + galley share per crew member

PART_TYPES = {
    "pressurized_module": {
        "about": "Rigid pressurized cylinder (crew volume). Hoop stress = P*r/t.",
        "defaults": {"radius_m": 2.2, "length_m": 8.0, "wall_thickness_mm": 4.8,
                     "material": "aluminum_2219", "shielding_g_cm2": 5.0,
                     "habitable_fraction": 0.6, "outfitting_kg_m3": 25.0},
    },
    "inflatable_module": {
        "about": "Inflatable soft-goods module: big volume for little launch mass.",
        "defaults": {"radius_m": 3.2, "length_m": 9.0, "wall_thickness_mm": 2.0,
                     "material": "vectran_inflatable", "shielding_g_cm2": 3.0,
                     "habitable_fraction": 0.7, "outfitting_kg_m3": 15.0},
    },
    "solar_array": {
        "about": "Photovoltaic array. Mean power = area*efficiency*irradiance*sun_fraction*(1-loss).",
        "defaults": {"area_m2": 80.0, "efficiency": 0.30, "specific_mass_kg_m2": 2.5},
    },
    "fission_reactor": {
        "about": "Kilopower-class fission power unit: constant power, day and night.",
        "defaults": {"power_kw": 10.0, "mass_kg": 1500.0},
    },
    "battery": {
        "about": "Energy storage that carries the loads through eclipse / night.",
        "defaults": {"capacity_kwh": 120.0, "specific_energy_wh_kg": 160.0, "depth_of_discharge": 0.8},
    },
    "radiator": {
        "about": "Heat rejection panel. Q = emissivity*sigma*A*(T^4 - Tsink^4), two-sided if deployable.",
        "defaults": {"area_m2": 40.0, "emissivity": 0.85, "temperature_k": 280.0,
                     "two_sided": False, "specific_mass_kg_m2": 6.0},
    },
    "life_support": {
        "about": "ECLSS: recycles water and oxygen; the rest is carried as consumables.",
        "defaults": {"water_recovery": 0.93, "o2_recovery": 0.5, "mass_kg": 1800.0, "power_kw": 0.0},
    },
    "propulsion": {
        "about": "Engine + tanks. Delta-v = Isp*g0*ln(m0/mf) for the whole vehicle.",
        "defaults": {"isp_s": 320.0, "thrust_n": 25000.0, "propellant_kg": 12000.0, "dry_mass_kg": 1800.0},
    },
    "cargo": {
        "about": "Any extra fixed mass and power load (science, rover, spares...).",
        "defaults": {"mass_kg": 500.0, "power_kw": 0.5},
    },
}


def new_design(name: str = "Untitled design", kind: str = "habitat", location: str = "mars_surface",
               crew: int = 4, mission_days: int = 500) -> dict:
    d = {"name": name, "kind": kind if kind in ("habitat", "spacecraft") else "habitat",
         "environment": {"location": location if location in LOCATIONS else "mars_surface",
                         "crew": crew, "mission_days": mission_days, "cabin_pressure_kpa": 70.3},
         "parts": {}, "selected": ""}
    add_part(d, "hab", "pressurized_module")
    add_part(d, "solar", "solar_array")
    add_part(d, "battery", "battery")
    add_part(d, "radiator", "radiator")
    add_part(d, "eclss", "life_support")
    if d["kind"] == "spacecraft":
        add_part(d, "engine", "propulsion")
    d["selected"] = "hab"
    return d


def add_part(design: dict, name: str, ptype: str, **props) -> dict:
    if ptype not in PART_TYPES:
        raise ValueError(f"unknown part type '{ptype}'; types: {', '.join(PART_TYPES)}")
    name = name.strip()
    if not name or len(name) > 40:
        raise ValueError("part name must be 1-40 characters")
    if name in design["parts"]:
        raise ValueError(f"a part named '{name}' already exists")
    part = {"type": ptype, **deepcopy(PART_TYPES[ptype]["defaults"])}
    design["parts"][name] = part
    for k, v in props.items():
        set_value(design, name, k, v)
    design["selected"] = name
    return part


def _coerce(old, value):
    if isinstance(old, bool):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on", "igen")
        return bool(value)
    if isinstance(old, (int, float)):
        v = float(str(value).replace(",", ".")) if not isinstance(value, (int, float)) else float(value)
        if not math.isfinite(v):
            raise ValueError("value must be a finite number")
        return int(v) if isinstance(old, int) and v.is_integer() else v
    return str(value).strip()


def set_value(design: dict, target: str, prop: str, value) -> None:
    """target = 'environment', 'design' (name/kind) or a part name."""
    if target in ("environment", "env"):
        box = design["environment"]
        if prop == "location" and str(value) not in LOCATIONS:
            raise ValueError(f"unknown location; known: {', '.join(LOCATIONS)}")
    elif target == "design":
        if prop not in ("name", "kind"):
            raise ValueError("design properties: name, kind")
        box = design
    elif target in design["parts"]:
        box = design["parts"][target]
        if prop == "type":
            raise ValueError("a part's type cannot change; remove it and add a new part")
        if prop == "material" and str(value) not in MATERIALS:
            raise ValueError(f"unknown material; known: {', '.join(MATERIALS)}")
    else:
        raise ValueError(f"no part named '{target}'; parts: {', '.join(design['parts']) or 'none'}")
    if prop not in box:
        raise ValueError(f"'{target}' has no property '{prop}'; it has: {', '.join(k for k in box if k != 'type')}")
    new = _coerce(box[prop], value)
    if isinstance(new, (int, float)) and not isinstance(new, bool) and new < 0:
        raise ValueError("value cannot be negative")
    box[prop] = new


# ---- simulation ----------------------------------------------------------------
def _module(p: dict, env: dict) -> dict:
    mat = MATERIALS.get(p["material"], MATERIALS["aluminum_2219"])
    r, L, t = p["radius_m"], p["length_m"], p["wall_thickness_mm"] / 1000
    vol = math.pi * r * r * L + (4 / 3) * math.pi * r ** 3          # cylinder + two hemispherical end caps
    area = 2 * math.pi * r * L + 4 * math.pi * r * r
    P = env["cabin_pressure_kpa"] * 1000
    hoop = P * r / t if t > 0 else math.inf
    shell = area * t * mat["density"]
    shield = area * p["shielding_g_cm2"] * 10                         # g/cm^2 -> kg/m^2
    atm = P * vol / (R_AIR * CABIN_T)
    outfit = vol * p["outfitting_kg_m3"]
    return {"pressurized_volume_m3": vol, "habitable_volume_m3": vol * p["habitable_fraction"],
            "surface_area_m2": area, "hoop_stress_mpa": hoop / 1e6,
            "safety_factor": mat["yield_pa"] / hoop if hoop else math.inf,
            "shell_mass_kg": shell, "shielding_mass_kg": shield, "outfitting_mass_kg": outfit,
            "atmosphere_mass_kg": atm, "mass_kg": shell + shield + outfit + atm,
            "power_kw": 0.02 * vol / 10}   # fans, lights, heaters ~ 2 W/m^3


def simulate(design: dict) -> dict:
    env = design["environment"]
    loc = LOCATIONS.get(env["location"], LOCATIONS["mars_surface"])
    crew, days = max(0, env["crew"]), max(0, env["mission_days"])
    parts: dict[str, dict] = {}
    gen_kw = steady_kw = load_kw = 0.0
    storage_kwh = rejection_kw = 0.0
    hab_vol = 0.0
    dry = 0.0
    water_rec = o2_rec = 0.0
    eclss = False
    props_ = []

    for name, p in design["parts"].items():
        t = p["type"]
        if t in ("pressurized_module", "inflatable_module"):
            o = _module(p, env)
            hab_vol += o["habitable_volume_m3"]
            load_kw += o["power_kw"]
        elif t == "solar_array":
            peak = p["area_m2"] * p["efficiency"] * loc["irradiance"] * (1 - loc["loss"]) / 1000
            mean = peak * loc["sun_fraction"]
            o = {"peak_power_kw": peak, "mean_power_kw": mean, "mass_kg": p["area_m2"] * p["specific_mass_kg_m2"]}
            gen_kw += mean
        elif t == "fission_reactor":
            o = {"mean_power_kw": p["power_kw"], "mass_kg": p["mass_kg"], "waste_heat_kw": p["power_kw"] * 3}
            gen_kw += p["power_kw"]
            steady_kw += p["power_kw"]
        elif t == "battery":
            usable = p["capacity_kwh"] * p["depth_of_discharge"]
            o = {"usable_energy_kwh": usable,
                 "mass_kg": p["capacity_kwh"] * 1000 / p["specific_energy_wh_kg"] if p["specific_energy_wh_kg"] else math.inf}
            storage_kwh += usable
        elif t == "radiator":
            sides = 2 if p["two_sided"] else 1
            q = p["emissivity"] * SIGMA * p["area_m2"] * sides * max(0.0, p["temperature_k"] ** 4 - loc["sink_k"] ** 4) / 1000
            o = {"heat_rejection_kw": q, "sink_temperature_k": loc["sink_k"], "mass_kg": p["area_m2"] * p["specific_mass_kg_m2"]}
            rejection_kw += q
        elif t == "life_support":
            eclss = True
            water_rec, o2_rec = min(p["water_recovery"], 0.999), min(p["o2_recovery"], 0.999)
            pw = p["power_kw"] or CREW_POWER_KW * crew
            o = {"power_kw": pw, "mass_kg": p["mass_kg"]}
            load_kw += pw
        elif t == "propulsion":
            o = {"mass_kg": p["dry_mass_kg"], "propellant_kg": p["propellant_kg"],
                 "exhaust_velocity_m_s": p["isp_s"] * G0}
            props_.append((name, p))
        elif t == "cargo":
            o = {"mass_kg": p["mass_kg"], "power_kw": p["power_kw"]}
            load_kw += p["power_kw"]
        else:
            o = {"mass_kg": 0.0}
        parts[name] = o
        dry += o["mass_kg"]

    if not eclss:
        load_kw += CREW_POWER_KW * crew
    water = crew * days * WATER_KG * (1 - water_rec)
    o2 = crew * days * O2_KG * (1 - o2_rec)
    food = crew * days * FOOD_KG
    consumables = water + o2 + food
    propellant = sum(p["propellant_kg"] for _, p in props_)
    total = dry + consumables + propellant

    # propulsion: all stages burn in order (simple single-stack model)
    dv = 0.0
    m = total
    for name, p in props_:
        mf = m - p["propellant_kg"]
        stage_dv = p["isp_s"] * G0 * math.log(m / mf) if mf > 0 and m > 0 else 0.0
        accel = p["thrust_n"] / m if m else 0.0
        parts[name].update({"delta_v_m_s": stage_dv, "initial_accel_m_s2": accel,
                            "thrust_to_weight_local": (p["thrust_n"] / (m * loc["g"])) if loc["g"] and m else None})
        dv += stage_dv
        m = mf

    heat_kw = load_kw + crew * METABOLIC_W / 1000
    night_need_kwh = max(0.0, load_kw - steady_kw) * loc["dark_h"]
    sun_frac = loc["sun_fraction"]
    # solar must cover load during the day plus recharge for the night
    energy_margin = gen_kw - load_kw

    checks = []

    def check(name, ok, warn, detail):
        checks.append({"check": name, "status": "OK" if ok else ("WARN" if warn else "FAIL"), "detail": detail})

    for name, o in parts.items():
        if "safety_factor" in o:
            sf = o["safety_factor"]
            check(f"{name} hull strength", sf >= 2.0, sf >= 1.4,
                  f"safety factor {sf:.2f} (NASA crewed pressure vessels: >= 2.0)")
    if crew:
        per = hab_vol / crew
        need = 25.0 if days > 30 else 10.0
        check("habitable volume", per >= need, per >= need * 0.6,
              f"{per:.1f} m^3 per crew member (guideline >= {need:.0f} for a {days}-day mission)")
    check("power balance", energy_margin >= 0.15 * load_kw, energy_margin >= 0,
          f"mean generation {gen_kw:.1f} kW vs load {load_kw:.1f} kW")
    if loc["dark_h"]:
        check("night / eclipse storage", storage_kwh >= night_need_kwh, storage_kwh >= 0.7 * night_need_kwh,
              f"{storage_kwh:.0f} kWh usable vs {night_need_kwh:.0f} kWh needed for {loc['dark_h']:.1f} h dark")
    check("heat rejection", rejection_kw >= heat_kw * 1.1, rejection_kw >= heat_kw,
          f"radiators reject {rejection_kw:.1f} kW vs heat load {heat_kw:.1f} kW")
    if design["kind"] == "spacecraft":
        check("propulsion", dv > 0, False, f"total delta-v {dv:.0f} m/s")

    return {
        "location": env["location"], "crew": crew, "mission_days": days,
        "parts": parts,
        "totals": {"dry_mass_kg": dry, "consumables_kg": consumables, "water_kg": water, "oxygen_kg": o2,
                   "food_kg": food, "propellant_kg": propellant, "total_mass_kg": total,
                   "habitable_volume_m3": hab_vol, "mean_power_generation_kw": gen_kw, "power_load_kw": load_kw,
                   "battery_usable_kwh": storage_kwh, "night_energy_need_kwh": night_need_kwh,
                   "heat_load_kw": heat_kw, "heat_rejection_kw": rejection_kw, "delta_v_m_s": dv,
                   "sun_fraction": sun_frac},
        "checks": checks,
    }


def _fmt(v) -> str:
    if isinstance(v, bool) or v is None:
        return str(v)
    if isinstance(v, float):
        if math.isinf(v):
            return "inf"
        a = abs(v)
        return f"{v:,.0f}" if a >= 1000 else f"{v:.1f}" if a >= 10 else f"{v:.3g}"
    return str(v)


def report(design: dict, sim: dict | None = None) -> str:
    """Plain-text snapshot: checks, totals and the selected part's properties."""
    sim = sim or simulate(design)
    e = design["environment"]
    lines = [f"DESIGN: {design['name']} ({design['kind']}) @ {e['location']}, crew {e['crew']}, "
             f"{e['mission_days']} days, cabin {e['cabin_pressure_kpa']} kPa",
             "parts: " + ", ".join(f"{n} ({p['type']})" for n, p in design["parts"].items())]
    lines.append("")
    lines.append("CHECKS")
    for c in sim["checks"]:
        lines.append(f"  [{c['status']:4}] {c['check']}: {c['detail']}")
    t = sim["totals"]
    lines.append("")
    lines.append("TOTALS")
    for k in ("total_mass_kg", "dry_mass_kg", "consumables_kg", "propellant_kg", "habitable_volume_m3",
              "mean_power_generation_kw", "power_load_kw", "battery_usable_kwh", "night_energy_need_kwh",
              "heat_load_kw", "heat_rejection_kw", "delta_v_m_s"):
        if k in ("propellant_kg", "delta_v_m_s") and not t[k]:
            continue
        lines.append(f"  {k} = {_fmt(t[k])}")
    sel = design.get("selected")
    if sel in design["parts"]:
        p = design["parts"][sel]
        lines.append("")
        lines.append(f"SELECTED PART: {sel} ({p['type']})")
        lines.append("  inputs:  " + ", ".join(f"{k}={_fmt(v)}" for k, v in p.items() if k != "type"))
        lines.append("  results: " + ", ".join(f"{k}={_fmt(v)}" for k, v in sim["parts"][sel].items()))
    return "\n".join(lines)
