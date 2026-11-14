"""Flame evidence tools (blackfox/tools/flame_tools.py) over flame/data and flame/calc."""

from blackfox.tools import load_all
from blackfox.tools import flame_tools as ft


def test_tools_are_registered_in_an_enabled_group():
    tools = load_all()
    names = {"fire_habitats", "fire_find_investigations", "fire_get_investigation", "fire_coverage",
             "fire_material_limits", "fire_material_check", "fire_insights"}
    assert names <= set(tools) and all(tools[n].group == "research" for n in names)


def test_find_and_get():
    r = ft.fire_find_investigations(topic="prevention", fuel_phase="solid")
    assert r["count"] >= 4 and all(i["summary"] for i in r["investigations"])
    d = ft.fire_get_investigation("psi-99")
    assert d["acronym"] == "SAFFIRE-II" and len(d["envelopes"]) == 2 and d["envelopes"][0]["provenance"]
    assert "error" in ft.fire_get_investigation("PSI-0")


def test_coverage_by_habitat_or_numbers():
    moon = ft.fire_coverage(habitat_id="moon-base")
    assert moon["solid_fuel_covered"] is False and len(moon["envelopes"]) <= 12
    assert ft.fire_coverage(o2_pct=21, pressure_kpa=101.3, fuel_phase="solid")["solid_fuel_covered"]
    assert "error" in ft.fire_coverage()


def test_material_tools_and_insights():
    assert "mylar_g" in ft.fire_material_limits()["materials"]
    assert ft.fire_material_limits("mylar_g")["lowest_limit_at"] == "lunar"
    assert ft.fire_material_check("nomex_ht90_40", 34, 56.5, "lunar")["verdict"] == "above_measured_limit"
    assert ft.fire_insights("moon-base")["insights"] and "error" in ft.fire_insights("pluto")
