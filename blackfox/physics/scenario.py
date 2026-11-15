"""The fire-lab scenario as data: what the SI may read and change.

The lab page (frontend/js/lab.js) keeps ONE scenario - the fields below. Each chat message carries
the scenario the user has open; the server stores it per visitor (ScenarioStore), the SI's tools
(blackfox/tools/scenario_tools.py) change it here with exactly the rules the lab itself follows, and
the chat answer returns the changed scenario so the page shows it. So "set the oxygen to 25 %" typed
in the chat and the oxygen slider are the same operation.

A None pressure / oxygen / temperature means "this environment's default cabin atmosphere" and a None
material means "the typical material of this place", exactly as in the lab.
"""

import json
import sqlite3
import time
from pathlib import Path

from ..settings import get_settings
from . import fire

FIELDS = ("environment", "location", "material", "pressure_kpa", "o2_pct", "temp_c", "vent_cm_s",
          "auto_vent_shutdown", "suppression", "response_s")
DEFAULT = {"environment": "leo", "location": "avionics_rack", "material": None, "pressure_kpa": None,
           "o2_pct": None, "temp_c": None, "vent_cm_s": 12.0, "auto_vent_shutdown": True,
           "suppression": "co2", "response_s": 60.0}
LIMITS = {"pressure_kpa": (20, 110), "o2_pct": (15, 50), "temp_c": (5, 45), "vent_cm_s": (0, 40),
          "response_s": (0, 300)}                     # the same ranges app.main.FireIn enforces (tested)
UNITS = {"pressure_kpa": "kPa", "o2_pct": "% O2 by volume", "temp_c": "deg C", "vent_cm_s": "cm/s",
         "response_s": "s"}
SUPPRESSION = tuple(fire.SUPPRESSANTS)       # none, co2, water_mist, k_aerosol, clean_agent, inert_n2
ATMOSPHERE = ("pressure_kpa", "o2_pct", "temp_c")
NUMBERS = ("pressure_kpa", "o2_pct", "temp_c", "vent_cm_s", "response_s")


def _names() -> dict[str, list[str]]:
    cat = fire.catalog()
    return {"environment": list(cat["environments"]), "location": list(cat["locations"]),
            "material": list(cat["materials"]), "suppression": list(SUPPRESSION)}


def _pick(name: str, value, allowed: list[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{name} {value!r} is not known; choose one of: {', '.join(allowed)}")
    return value


def _flag(value) -> bool:
    if isinstance(value, bool):
        return value
    word = str(value).strip().lower()
    if word in ("on", "true", "yes", "1", "automatic", "auto"):
        return True
    if word in ("off", "false", "no", "0", "manual"):
        return False
    raise ValueError(f"auto_vent_shutdown {value!r} is not understood; use on or off")


def clean(scenario: dict | None) -> dict:
    """A complete, valid scenario: unknown keys dropped, missing ones at their defaults."""
    out = {k: DEFAULT[k] for k in FIELDS}
    for k in FIELDS:
        if scenario and scenario.get(k) is not None:
            out[k] = scenario[k]
    return out


def effective(scenario: dict) -> dict:
    """The scenario with every None filled in (the numbers the simulation really uses)."""
    cat = fire.catalog()
    s = clean(scenario)
    d = cat["environments"][s["environment"]]["defaults"]
    for k in ATMOSPHERE:
        if s[k] is None:
            s[k] = d[k]
    if s["material"] is None:
        s["material"] = cat["locations"][s["location"]]["default_material"]
    return s


def merge(current: dict | None, changes: dict, reset_atmosphere: bool = False) -> tuple[dict, dict]:
    """Apply `changes` (only the keys to change) to `current`.
    -> (new scenario, {field: {"from": old, "to": new}} for every value that really changed).
    Raises ValueError, naming the valid choices, when a value is not allowed; nothing is changed then.

    Same rules as the lab page: moving to another environment starts from that environment's own
    cabin atmosphere (unless pressure / oxygen / temperature are given too), and moving to another
    place switches to that place's typical material (unless a material is given too).
    """
    names = _names()
    unknown = [k for k in changes if k not in FIELDS]
    if unknown:
        raise ValueError(f"unknown setting {', '.join(unknown)}; the settings are: {', '.join(FIELDS)}")
    old = clean(current)
    new = dict(old)
    if "environment" in changes:
        env = _pick("environment", changes["environment"], names["environment"])
        if env != old["environment"]:
            new.update({k: None for k in ATMOSPHERE})
        new["environment"] = env
    if reset_atmosphere:
        new.update({k: None for k in ATMOSPHERE})
    if "location" in changes:
        loc = _pick("location", changes["location"], names["location"])
        if loc != old["location"]:
            new["material"] = None
        new["location"] = loc
    if "material" in changes:
        m = changes["material"]
        new["material"] = None if m in (None, "", "default") else _pick("material", m, names["material"])
    for k in NUMBERS:
        if k not in changes:
            continue
        lo, hi = LIMITS[k]
        try:
            v = float(changes[k])
        except (TypeError, ValueError):
            raise ValueError(f"{k} must be a number between {lo} and {hi} {UNITS[k]}") from None
        if not lo <= v <= hi:
            raise ValueError(f"{k} {v:g} is outside the allowed range {lo} to {hi} {UNITS[k]}")
        new[k] = v
    if "suppression" in changes:
        new["suppression"] = _pick("suppression", changes["suppression"], names["suppression"])
    if "auto_vent_shutdown" in changes:
        new["auto_vent_shutdown"] = _flag(changes["auto_vent_shutdown"])
    a, b = effective(old), effective(new)
    return new, {k: {"from": a[k], "to": b[k]} for k in FIELDS if a[k] != b[k]}


def run(scenario: dict) -> dict:
    """The full simulation of a scenario (without the big time series)."""
    r = fire.simulate(**effective(scenario))
    r.pop("series", None)
    return r


def brief(r: dict) -> dict:
    """The few numbers worth telling the user, from a simulation result."""
    f, tl, pk, v = r["flammability"], r["timeline"], r["peaks"], r["verdict"]
    return {"risk": v["level"], "flammable": f["flammable"], "oxygen_margin_pct": round(f["margin_pct"], 2),
            "moc_1g_pct": round(f["moc_1g"], 2), "moc_effective_pct": round(f["moc_eff"], 2),
            "gravity_fraction": round(r["atmosphere"]["gravity_fraction"], 4),
            "spread_cm_s": round(r["flame"]["spread_cm_s"], 3), "peak_heat_release_kw": round(pk["hrr_kw"], 2),
            "peak_co_ppm": round(pk["co_ppm"], 1), "co_1h_limit_ppm": pk["co_smac_1h_ppm"],
            "alarm_s": tl["alarm_s"], "extinguished_s": tl["extinguished_s"], "co_limit_reached_s": tl["co_smac_s"],
            "detected": v["detected"], "contained": v["contained"]}


def options() -> dict:
    """Everything a caller may set: valid names with labels and defaults, and the numeric ranges."""
    cat = fire.catalog()
    return {
        "settings": list(FIELDS),
        "environment": {k: {"label": v["label"], "gravity_fraction": round(v["g_fraction"], 4),
                            "default_atmosphere": v["defaults"]} for k, v in cat["environments"].items()},
        "location": {k: {"label": v["label"], "default_material": v["default_material"]}
                     for k, v in cat["locations"].items()},
        "material": {k: v["label"] for k, v in cat["materials"].items()},
        "suppression": {k: (f"{v['label']}; discharges by itself {v['delay_s']:g} s after the alarm (response_s does not apply)"
                           if v["kind"] == "fixed" else v["label"]) for k, v in fire.SUPPRESSANTS.items()},
        "ranges": {k: {"min": lo, "max": hi, "unit": UNITS[k]} for k, (lo, hi) in LIMITS.items()},
        "auto_vent_shutdown": "on = the crew switches the ventilation off when the alarm sounds (as ISS crews do); off = it keeps running",
        "rules": ["a new environment starts from its own cabin atmosphere unless pressure/oxygen/temperature are given",
                  "a new location starts with its typical material unless a material is given"],
    }


# ---- per-visitor storage ---------------------------------------------------------------

class ScenarioStore:
    """The scenario each visitor currently has open in the lab (SQLite, like the design store)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS scenarios (visitor_id TEXT PRIMARY KEY, scenario TEXT NOT NULL, "
                      "updated_at REAL NOT NULL)")

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def get(self, visitor_id: str) -> dict:
        with self._conn() as c:
            row = c.execute("SELECT scenario FROM scenarios WHERE visitor_id=?", (visitor_id,)).fetchone()
        return clean(json.loads(row[0])) if row else clean(None)

    def put(self, visitor_id: str, scenario: dict) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO scenarios (visitor_id, scenario, updated_at) VALUES (?,?,?) "
                      "ON CONFLICT(visitor_id) DO UPDATE SET scenario=excluded.scenario, updated_at=excluded.updated_at",
                      (visitor_id, json.dumps(clean(scenario)), time.time()))

    def delete(self, visitor_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM scenarios WHERE visitor_id=?", (visitor_id,))


_store: ScenarioStore | None = None


def get_store() -> ScenarioStore:
    global _store
    if _store is None:
        _store = ScenarioStore(get_settings().data_dir / "fire_scenarios.db")
    return _store
