"""Fire-safety screening model (blackfox/physics/fire.py): numbers come from the curated
knowledge base (NASA NTRS sources) and behave the way the source experiments report."""

import pytest

from blackfox.physics import fire


def test_moc_reproduces_the_measured_nasa_std_6001_points():
    for m in ("ptfe_wire", "nomex", "polyethylene", "ultem", "delrin", "silicone"):
        for p, v in fire.moc_table()[fire.MATERIALS[m]["moc"]]:
            assert fire.moc_1g(m, p) == pytest.approx(v, abs=1e-6)
    # PTFE is harder to burn at low pressure (halogenated, pressure dependent)
    assert fire.moc_1g("ptfe_wire", 48.3) > fire.moc_1g("ptfe_wire", 101.4)


def test_environment_defaults_come_from_the_knowledge_base():
    cat = fire.catalog()
    env = cat["environments"]
    assert env["leo"]["defaults"]["pressure_kpa"] == 101.4 and env["leo"]["defaults"]["o2_pct"] == 21
    assert env["moon"]["defaults"] == {"pressure_kpa": 56.5, "o2_pct": 34, "temp_c": 22.0}
    assert env["mars"]["g_m_s2"] == 3.71 and env["moon"]["g_m_s2"] == 1.62
    assert cat["references"]["co_smac_1h_ppm"] == 55
    assert cat["references"]["ventilation_nominal_cm_s"] == [5, 20]


def test_gravity_and_flow_corrections():
    g0 = fire.G0
    # generic material: 0 g with ventilation burns up to 3 % O2 lower than 1 g, the Moon in between
    zero = fire.effective_moc("polyethylene", 70.3, 1e-6 * g0, 15, 22)["moc_eff"]
    moon = fire.effective_moc("polyethylene", 70.3, 1.62, 15, 22)["moc_eff"]
    earth = fire.effective_moc("polyethylene", 70.3, g0, 30, 22)["moc_eff"]
    assert earth - zero == pytest.approx(3.0, abs=0.01) and zero < moon < earth
    # measured material (team data, Olson & Ferkul 2012 Table I): the drop-tower MOC changes
    for mat, d_moon, d_mars, d_zero in (("ultem", 19.9 - 23.0, 21.1 - 23.0, 0.0), ("nomex", 19.9 - 22.1, 19.0 - 22.1, 22.0 - 22.1)):
        sh = {g: fire.gravity_shift(g * g0, mat) for g in (0.166, 0.38, 0.0)}
        assert all(b == "measured" for _, b in sh.values())
        assert sh[0.166][0] == pytest.approx(d_moon, abs=1e-6) and sh[0.38][0] == pytest.approx(d_mars, abs=1e-6)
        assert sh[0.0][0] == pytest.approx(d_zero, abs=1e-6)
    assert fire.gravity_shift(g0, "ultem") == (0.0, "measured")
    # quiescent microgravity starves the flame
    assert fire.effective_moc("ultem", 70.3, 1e-6 * g0, 0.03, 22)["moc_eff"] > 40


def test_nomex_does_not_spread_in_iss_air_but_polyethylene_does():
    nomex = fire.simulate("leo", material="nomex", location="crew_quarters")
    assert not nomex["flammability"]["flammable"] and nomex["verdict"]["level"] == "low"
    assert nomex["timeline"]["events"][-1]["key"] == "self_extinguished"
    pe = fire.simulate("leo", material="polyethylene", location="galley")
    assert pe["flammability"]["flammable"] and pe["flame"]["spread_cm_s"] > 0.1
    assert [e["key"] for e in pe["timeline"]["events"]][:3] == ["ignition", "alarm", "vent_off"]


def test_exploration_atmosphere_is_riskier_than_iss_air():
    iss = fire.simulate("leo", material="ultem", location="avionics_rack")
    ea = fire.simulate("moon", material="ultem", location="avionics_rack")
    assert ea["flammability"]["margin_pct"] > iss["flammability"]["margin_pct"]
    assert ea["peaks"]["hrr_kw"] > iss["peaks"]["hrr_kw"]


def test_flame_survives_ventilation_shutdown_for_a_while():
    # Saffire V: flames do not go out at once when the flow stops
    r = fire.simulate("leo", material="polyethylene", location="galley", suppression="none", response_s=200)
    off = r["timeline"]["alarm_s"]
    out = r["timeline"]["extinguished_s"]
    assert off is not None and out is not None and out - off > 20


def test_series_map_and_validation():
    r = fire.simulate("mars", location="galley")
    assert r["series"][0]["t"] == 0 and r["series"][-1]["t"] == r["inputs"]["duration_s"]
    assert len(r["map"]["pressure_kpa"]) == len(r["map"]["moc_eff"]) == len(r["map"]["normoxic"])
    with pytest.raises(ValueError):
        fire.simulate("pluto")
    with pytest.raises(ValueError):                       # props only, not a fire source
        fire.simulate("leo", location="stowage")
    with pytest.raises(ValueError):
        fire.simulate("leo", material="unobtainium")


def test_evidence_keeps_fire_topics_and_drops_biology():
    assert not fire.relevant({"topic": "biology_plants", "title": "Plant growth"})
    assert not fire.relevant({"topic": "combustion_fire", "title": "Microbial biofilm on cables", "summary": ""})
    assert fire.relevant({"topic": "combustion_fire", "title": "Flame spread over thin fuels", "summary": ""})
    ev = fire.evidence("moon", "polyethylene")
    assert ev[0]["slug"] == "nasa-std-6001-moc-pressure" and all(e["url"].startswith("https://ntrs.nasa.gov") for e in ev)


# ---- suppression agents -----------------------------------------------------------------------
def _fire(**kw):
    base = dict(environment="moon", location="galley", o2_pct=34.0, pressure_kpa=56.5, vent_cm_s=5, response_s=120)
    return fire.simulate(**{**base, **kw})


def test_every_agent_is_known_and_unknown_ones_list_the_choices():
    assert list(fire.SUPPRESSANTS) == ["none", "co2", "water_mist", "k_aerosol", "clean_agent", "inert_n2"]
    with pytest.raises(ValueError, match="none, co2, water_mist, k_aerosol, clean_agent, inert_n2"):
        _fire(suppression="foam")


def test_fixed_systems_discharge_by_themselves_after_the_alarm_not_after_the_crew_response():
    for agent in ("k_aerosol", "clean_agent", "inert_n2"):
        r = _fire(suppression=agent)
        ev = {e["key"]: e for e in r["timeline"]["events"]}
        assert ev[agent]["detail"] == "automatic"
        assert abs(ev[agent]["t"] - (r["timeline"]["alarm_s"] + 10.0)) < 1.0          # alarm + the 10 s delay
        assert r["timeline"]["extinguished_s"] is not None
        assert r["suppressant"]["id"] == agent and r["suppressant"]["kind"] == "fixed"
    co2 = _fire(suppression="co2")                                                    # portable: waits for response_s = 120
    assert co2["timeline"]["extinguished_s"] > _fire(suppression="k_aerosol")["timeline"]["extinguished_s"] + 60


def test_crew_response_time_does_not_matter_for_a_fixed_system_but_does_for_a_portable_one():
    for agent, matters in (("k_aerosol", False), ("clean_agent", False), ("water_mist", True)):
        quick, slow = _fire(suppression=agent, response_s=20), _fire(suppression=agent, response_s=150)
        same = quick["timeline"]["extinguished_s"] == slow["timeline"]["extinguished_s"]
        assert same != matters, agent


def test_agents_rank_as_modelled_and_ventilation_running_at_discharge_slows_a_fixed_system():
    t = {a: _fire(suppression=a)["timeline"]["extinguished_s"] for a in ("k_aerosol", "clean_agent", "inert_n2")}
    assert t["k_aerosol"] < t["clean_agent"] < t["inert_n2"]                          # tau 2.0 < 2.5 < 6.0
    shut = _fire(suppression="k_aerosol", auto_vent_shutdown=True)["timeline"]["extinguished_s"]
    running = _fire(suppression="k_aerosol", auto_vent_shutdown=False)["timeline"]["extinguished_s"]
    assert running > shut                                                             # the fans dilute the agent


def test_the_result_says_which_numbers_are_assumptions():
    r = _fire(suppression="k_aerosol")
    assert any("potassium" in a and "assumed" in a for a in r["assumptions"])
    assert not any("suppression:" in a for a in _fire(suppression="co2")["assumptions"])
    assert "ntrs-20040161262" in fire.SUPPRESSANTS["inert_n2"]["note"]                # the one NASA-backed ordering
