"""Evidence calculator (flame/calc.py) and the material_limits.json data it reads."""

import pytest

from flame import calc, data


def test_material_limits_load_and_cite():
    rows = data.get_material_limits()
    assert len(rows) >= 13 and all(r.provenance and r.provenance[0].quote for r in rows)
    assert {r.gravity for r in data.get_material_limits("mylar_g")} == {"micro", "lunar", "martian", "earth"}


def test_moon_base_has_no_solid_fuel_coverage():
    c = calc.coverage_for_habitat("moon-base")
    assert c["solid_fuel_covered"] is False and c["max_solid_o2_tested_pct"] == pytest.approx(22.2)
    assert c["counts"]["inside"] >= 1 and "partial-gravity" in c["gravity_note"]
    assert all(r["status"] != "inside" for r in c["envelopes"] if r["fuel_phase"] == "solid")


def test_iss_solids_are_covered():
    c = calc.coverage_for_habitat("iss", fuel_phase="solid")
    assert c["solid_fuel_covered"] and {r["fuel_phase"] for r in c["envelopes"]} == {"solid"}


def test_unknown_habitat_and_material_are_errors_not_crashes():
    assert "error" in calc.coverage_for_habitat("venus")
    assert "error" in calc.material_check("wood", 21, 101.3, "earth")
    assert "error" in calc.material_check("mylar_g", 21, 101.3, "jupiter")


def test_gravity_profile_finds_the_partial_g_minimum():
    p = calc.gravity_profile("mylar_g")
    assert p["lowest_limit_at"] == "lunar"
    lunar = next(x for x in p["levels"] if x["gravity"] == "lunar")
    assert lunar["delta_vs_1g_pct"] == pytest.approx(-5.75)


def test_material_check_is_conservative_about_pressure():
    r = calc.material_check("nomex_ht90_40", 34, 56.5, "lunar")
    assert r["verdict"] == "above_measured_limit" and r["margin_pct"] == pytest.approx(13.55)
    # lower cabin pressure raises the limit: the range only extends downward, and stays above the limit here
    lo, hi = r["margin_range_pct"]
    assert hi == pytest.approx(13.55) and lo == pytest.approx(7.21) and not r["pressure_may_change_verdict"]
    assert any("rises toward cabin pressure" in c for c in r["caveats"])


def test_material_check_below_limit_in_air():
    r = calc.material_check("ultem_1000", 21, 101.3, "micro")
    # measured at 70.3 kPa; at higher cabin pressure the limit can fall, so the verdict is flagged as uncertain
    assert r["verdict"] == "below_measured_limit" and r["margin_range_pct"][1] > r["margin_pct"]
    assert r["pressure_may_change_verdict"]


def test_same_pressure_gives_a_point_range():
    r = calc.material_check("mylar_g", 21, 70.3, "earth")
    assert r["margin_range_pct"] == (r["margin_pct"], r["margin_pct"]) and r["verdict"] == "near_measured_limit"
