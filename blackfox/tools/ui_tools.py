"""Page guide: the AI shows the user where something is on the website.

show_on_page returns an action; /api/chat passes it to the browser (reply["ui"]), which opens the right
page if needed, scrolls to the element, highlights it for a few seconds and makes it pulse once
(frontend/js/guide.js). The targets are a fixed list: each one is an element with
data-guide="<target>" in that page (tests/frontend/test_guide.py checks every one exists), so the
model can never point at something that is not there.

The group "ui" is always on (registry.ALWAYS_ON) and the tool is visible without opening a category
(harness QUICK_TOOLS): showing the user around needs no other tools.
"""

from typing import Literal

from .registry import tool

PAGES = {"home": "/", "lab": "/lab.html"}

# target -> (page, what it is). Names are unique across pages, so the model gives only the target.
TARGETS: dict[str, tuple[str, str]] = {
    "home_top": ("home", "the top of the landing page"),
    "physics": ("home", "the three short physics chapters: no buoyancy, low pressure + high oxygen, smoke follows the air"),
    "experiments": ("home", "the NASA PSI experiment dashboard: investigations ranked per mission"),
    "mission_picker": ("home", "the mission and focus selectors of the experiment dashboard"),
    "experiment_compare": ("home", "the button that compares the selected experiments"),
    "sources": ("home", "the sources and method section"),
    "simulator": ("lab", "the simulator view in the middle of the lab"),
    "view_switch": ("lab", "the switch between the 3D cabin, the spacecraft 2D section and the CFD model"),
    "environment": ("lab", "step 1: environment (ISS, Gateway, Moon, Mars, Earth) and its gravity"),
    "cabin_air": ("lab", "step 2: the cabin air - preset buttons and sliders for pressure, oxygen and temperature"),
    "oxygen": ("lab", "the oxygen slider (step 2, % O2 by volume)"),
    "pressure": ("lab", "the total pressure slider (step 2, kPa)"),
    "fire_source": ("lab", "step 3: where the fire starts, what burns, the wall lining"),
    "material": ("lab", "the burning material drop-down (step 3)"),
    "ventilation": ("lab", "step 4: airflow at the fire and the automatic ventilation shutdown"),
    "extinguisher": ("lab", "the extinguisher choice and the crew response time"),
    "start_button": ("lab", "the Start button that runs the simulation"),
    "spread_2d": ("lab", "the spacecraft cabin fire 2D section simulator"),
    "cfd": ("lab", "the realistic CFD fire model"),
    "camera": ("lab", "the 3D camera and display mode buttons (exterior, cutaway, interior, fire; x-ray, thermal, airflow)"),
    "timeline": ("lab", "the playback bar: play, time slider, speed"),
    "verdict": ("lab", "the risk verdict at the top of the results"),
    "results": ("lab", "the key numbers: oxygen limit, margin, spread, heat release, CO, alarm time"),
    "nasa_tested": ("lab", "'Has NASA tested this?': the PSI experiments closest to the scenario"),
    "gap_map": ("lab", "the gap map: where PSI experiments burned things vs planned cabin atmospheres"),
    "flammability_map": ("lab", "the flammability map: oxygen vs pressure limit for the material"),
    "time_series": ("lab", "the chart of the fire over time"),
    "event_log": ("lab", "the event log: ignition, alarm, vent shutdown, extinguishing"),
    "lab_sources": ("lab", "the NASA sources behind the numbers"),
}

Target = Literal[
    "home_top", "physics", "experiments", "mission_picker", "experiment_compare", "sources",
    "simulator", "view_switch", "environment", "cabin_air", "oxygen", "pressure", "fire_source", "material",
    "ventilation", "extinguisher", "start_button", "spread_2d", "cfd", "camera", "timeline", "verdict",
    "results", "nasa_tested", "gap_map", "flammability_map", "time_series", "event_log", "lab_sources",
]


@tool("ui")
def show_on_page(target: Target, note: str = "") -> dict:
    """Show the user where something is on the website: their browser opens the right page, scrolls
    to it and highlights it with one pulse. Use it when the user asks where something is or how to do
    something on the page ("where do I change the oxygen?", "show me the gap map", "how do I start?").
    Home page: home_top, physics, experiments (NASA PSI dashboard), mission_picker, experiment_compare,
    sources. Lab: the steps environment, cabin_air (oxygen, pressure), fire_source (material),
    ventilation, extinguisher, start_button; the views simulator, view_switch, spread_2d, cfd, camera,
    timeline; the results verdict, results, nasa_tested, gap_map, flammability_map, time_series,
    event_log, lab_sources. note: a few words shown with the highlight, in the user's language.
    One call per answer (the last one wins); still answer in words."""
    if target not in TARGETS:
        return {"error": f"unknown target {target!r}; choose one of: {', '.join(TARGETS)}"}
    page, what = TARGETS[target]
    action = {"type": "show", "page": page, "url": PAGES[page], "target": target,
              "note": " ".join(str(note).split())[:120]}
    return {"action": action, "shown": what,
            "user_sees": "the page scrolls to it and it pulses once, as soon as your answer is displayed"}
