"""Simulation workspace (blackfox/design/): physics sanity + the public interface."""

import math

import pytest

from blackfox.design import (LOCATIONS, PART_TYPES, add_part, new_design, report, run_command, set_value,
                             simulate)


def check(sim, name):
    return next(c for c in sim["checks"] if c["check"] == name)


def test_default_design_simulates():
    d = new_design()
    sim = simulate(d)
    assert set(sim) >= {"parts", "totals", "checks"}
    assert sim["totals"]["total_mass_kg"] > 0
    assert all(c["status"] in ("OK", "WARN", "FAIL") for c in sim["checks"])


def test_hoop_stress_formula():
    d = new_design()
    set_value(d, "hab", "radius_m", 2.0)
    set_value(d, "hab", "wall_thickness_mm", 5)
    set_value(d, "environment", "cabin_pressure_kpa", 100)
    hab = simulate(d)["parts"]["hab"]
    assert hab["hoop_stress_mpa"] == pytest.approx(100e3 * 2.0 / 0.005 / 1e6)     # sigma = P r / t


def test_bigger_module_more_volume_and_mass():
    d = new_design()
    a = simulate(d)["parts"]["hab"]
    set_value(d, "hab", "radius_m", 3.0)
    b = simulate(d)["parts"]["hab"]
    assert b["habitable_volume_m3"] > a["habitable_volume_m3"] and b["mass_kg"] > a["mass_kg"]


def test_lunar_night_fails_storage():
    d = new_design(location="moon_surface")
    assert check(simulate(d), "night / eclipse storage")["status"] == "FAIL"


def test_spacecraft_delta_v_rocket_equation():
    d = new_design(kind="spacecraft", location="mars_transit")
    sim = simulate(d)
    m0 = sim["totals"]["total_mass_kg"]
    p = d["parts"]["engine"]
    assert sim["totals"]["delta_v_m_s"] == pytest.approx(p["isp_s"] * 9.80665 * math.log(m0 / (m0 - p["propellant_kg"])))


def test_every_part_type_and_location_works():
    d = new_design()
    for i, t in enumerate(PART_TYPES):
        add_part(d, f"p{i}", t)
    for loc in LOCATIONS:
        set_value(d, "environment", "location", loc)
        sim = simulate(d)
        assert all(math.isfinite(v) for v in sim["totals"].values())


@pytest.mark.parametrize("target,prop,value", [
    ("hab", "nope", "1"), ("nobody", "radius_m", "1"), ("hab", "radius_m", "-2"),
    ("hab", "material", "cheese"), ("environment", "location", "pluto"), ("hab", "radius_m", "nan"),
])
def test_bad_values_rejected(target, prop, value):
    with pytest.raises(ValueError):
        set_value(new_design(), target, prop, value)


def test_report_shows_selected_part():
    d = new_design()
    d["selected"] = "solar"
    assert "SELECTED PART: solar (solar_array)" in report(d)


def test_typed_commands():
    v = "visitor-for-commands-test"
    assert "radius_m=3.5" in run_command(v, "set hab.radius_m = 3.5")
    assert "SELECTED PART: solar" in run_command(v, "select solar")
    assert run_command(v, "set hab.colour = red").startswith("error:")
    assert run_command(v, "set the habitat a bit bigger please") is None      # sentence -> goes to the agent
    assert run_command(v, "hello") is None
    assert "SELECTED PART: solar" in run_command(v, "show")                 # selection is remembered
    assert "radius_m=3.5" in run_command(v, "select hab")                   # and so is the change
