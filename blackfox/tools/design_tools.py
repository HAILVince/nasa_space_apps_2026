"""Design + simulation tools. They edit the visitor's current design (visitor_id is a
context parameter filled in by the harness) and every edit re-runs the simulation, so the
model always answers from fresh, computed numbers."""

from ..design import get_store, load_or_new
from ..physics import spacecraft as sc
from .registry import tool


def _result(visitor_id: str, d: dict) -> dict:
    sim = sc.simulate(d)
    sel = d.get("selected")
    return {"design": {"name": d["name"], "kind": d["kind"], "environment": d["environment"],
                       "parts": {n: p["type"] for n, p in d["parts"].items()}},
            "checks": sim["checks"], "totals": {k: round(v, 3) for k, v in sim["totals"].items()},
            "selected_part": ({"name": sel, "inputs": d["parts"][sel],
                               "results": {k: (round(v, 3) if isinstance(v, float) else v)
                                           for k, v in sim["parts"][sel].items()}}
                              if sel in d["parts"] else None)}


def _edit(visitor_id: str, fn) -> dict:
    if not visitor_id:
        return {"error": "no visitor context"}
    d = load_or_new(visitor_id)
    try:
        fn(d)
    except ValueError as e:
        return {"error": str(e)}
    get_store().put(visitor_id, d)
    return _result(visitor_id, d)


@tool("design")
def design_catalog() -> dict:
    """Every part type (with its editable properties and defaults), location and material
    the simulator knows. Call this before adding parts or when unsure of a property name."""
    return {"part_types": {k: {"about": v["about"], "properties": v["defaults"]} for k, v in sc.PART_TYPES.items()},
            "locations": list(sc.LOCATIONS), "materials": list(sc.MATERIALS),
            "environment_properties": ["location", "crew", "mission_days", "cabin_pressure_kpa"]}


@tool("design")
def get_design(visitor_id: str = "") -> dict:
    """The user's current design with a fresh simulation: checks (OK/WARN/FAIL), totals and
    the selected part's inputs and computed results."""
    if not visitor_id:
        return {"error": "no visitor context"}
    return _result(visitor_id, load_or_new(visitor_id))


@tool("design", writes=True)
def new_design(name: str = "Untitled design", kind: str = "habitat", location: str = "mars_surface",
               crew: int = 4, mission_days: int = 500, visitor_id: str = "") -> dict:
    """Start a new design from a sensible default (module, solar array, battery, radiator,
    life support; spacecraft also get propulsion). Replaces the current design.
    kind: habitat or spacecraft. location: see design_catalog."""
    def f(d):
        d.clear()
        d.update(sc.new_design(name, kind, location, crew, mission_days))
    return _edit(visitor_id, f)


@tool("design", writes=True)
def set_design_value(target: str, property: str, value: str, visitor_id: str = "") -> dict:
    """Change one value and re-simulate. target = a part name, 'environment' (location, crew,
    mission_days, cabin_pressure_kpa) or 'design' (name, kind). value is given as text,
    e.g. '3.5', 'true', 'titanium_6al4v'. Call once per value the user changes."""
    def f(d):
        sc.set_value(d, target, property, value)
        if target in d["parts"]:
            d["selected"] = target
    return _edit(visitor_id, f)


@tool("design", writes=True)
def add_design_part(name: str, part_type: str, visitor_id: str = "") -> dict:
    """Add a part with default properties (then set_design_value to tune it) and select it."""
    return _edit(visitor_id, lambda d: sc.add_part(d, name, part_type))


@tool("design", writes=True)
def remove_design_part(name: str, visitor_id: str = "") -> dict:
    """Remove a part from the design."""
    def f(d):
        if name not in d["parts"]:
            raise ValueError(f"no part named '{name}'")
        del d["parts"][name]
        if d["selected"] == name:
            d["selected"] = next(iter(d["parts"]), "")
    return _edit(visitor_id, f)


@tool("design")
def select_design_part(name: str, visitor_id: str = "") -> dict:
    """Select a part so its current properties and computed results are shown."""
    def f(d):
        if name not in d["parts"]:
            raise ValueError(f"no part named '{name}'; parts: {', '.join(d['parts'])}")
        d["selected"] = name
    return _edit(visitor_id, f)
