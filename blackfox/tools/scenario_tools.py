"""Fire-lab scenario tools: the AI reads and changes the scenario the user has open in the lab.

set_fire_scenario edits the visitor's current scenario (visitor_id is a context parameter filled in
by the harness) with the lab's own rules (blackfox/physics/scenario.py), re-runs the simulation and
returns fresh numbers; the chat answer then carries the new scenario and the lab page shows it.
Use simulate_cabin_fire instead for a what-if that must NOT change what the user sees.

Unset convention (the registry builds schemas from plain type hints): "" and negative numbers mean
"leave this setting alone" - every real value of these settings is zero or positive.
"""

from ..physics import scenario as sc
from .registry import tool

NO_VISITOR = {"error": "no visitor context: the lab scenario belongs to a website visitor. "
                       "Call simulate_cabin_fire to run a scenario without one."}


@tool("physics")
def fire_scenario_options() -> dict:
    """Everything set_fire_scenario accepts: the environments (with gravity and default cabin
    atmosphere), places in the module (with their typical material), materials, extinguisher types
    and the allowed numeric ranges. Call it when unsure of a name or limit."""
    return sc.options()


@tool("physics")
def get_fire_scenario(visitor_id: str = "") -> dict:
    """The fire scenario the user has open in the lab right now, with every default filled in, and
    its fresh simulation result (risk, oxygen margin, spread, heat release, CO, alarm and
    extinguishment times). Call it before changing anything when the request is relative
    ("a bit more oxygen", "half the ventilation")."""
    if not visitor_id:
        return NO_VISITOR
    s = sc.get_store().get(visitor_id)
    try:
        return {"scenario": sc.effective(s), "results": sc.brief(sc.run(s))}
    except ValueError as e:
        return {"error": str(e)}


@tool("physics", writes=True)
def set_fire_scenario(environment: str = "", location: str = "", material: str = "", pressure_kpa: float = -1,
                      o2_pct: float = -1, temp_c: float = -1, vent_cm_s: float = -1,
                      auto_vent_shutdown: str = "", suppression: str = "", response_s: float = -1,
                      reset_atmosphere: bool = False, visitor_id: str = "") -> dict:
    """Change the fire scenario in the user's lab; the lab page updates itself when you answer.
    Give ONLY the settings that change - everything else keeps its value.
    environment: leo (ISS), lunar_orbit (Gateway), moon, mars, earth. Moving to another environment
    starts from its own cabin atmosphere unless you also give pressure/oxygen/temperature.
    location: avionics_rack, crew_quarters, galley, glovebox. A new location starts with its typical
    material unless you give one (material "default" = the location's typical one).
    material: ptfe_wire, nomex, silicone, polyethylene, nylon, pet_film, ultem, delrin, viton, kydex.
    pressure_kpa 20-110, o2_pct 15-50, temp_c 5-45, vent_cm_s 0-40 (0 = no ventilation),
    response_s 0-300 (seconds until the crew reaches the fire). auto_vent_shutdown: on or off.
    suppression: none, co2, water_mist. reset_atmosphere: true = back to the environment's default
    cabin atmosphere. Returns what changed (from/to), the full scenario and the fresh results; a value
    outside its range is refused with the allowed range and nothing is changed."""
    if not visitor_id:
        return NO_VISITOR
    changes: dict = {}
    for k, v in (("environment", environment), ("location", location), ("material", material),
                 ("suppression", suppression), ("auto_vent_shutdown", auto_vent_shutdown)):
        if str(v).strip():
            changes[k] = str(v).strip().lower()
    for k, v in (("pressure_kpa", pressure_kpa), ("o2_pct", o2_pct), ("temp_c", temp_c),
                 ("vent_cm_s", vent_cm_s), ("response_s", response_s)):
        if v is not None and float(v) >= 0:
            changes[k] = float(v)
    store = sc.get_store()
    try:
        new, changed = sc.merge(store.get(visitor_id), changes, reset_atmosphere=bool(reset_atmosphere))
        results = sc.brief(sc.run(new))          # run first: a scenario the model cannot simulate is never stored
    except ValueError as e:
        return {"error": str(e)}
    store.put(visitor_id, new)
    return {"changed": changed or "nothing differed from the current scenario", "scenario": sc.effective(new),
            "results": results, "lab": "the user's lab shows this scenario as soon as your answer is displayed"}
