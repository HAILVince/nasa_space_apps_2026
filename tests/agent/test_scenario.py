"""The fire-lab scenario the SI can set: the merge rules, the per-visitor store and the tools,
called through the real MCP toolbox (the path the site's agent uses)."""

import asyncio
import json

import pytest

from blackfox.harness.toolbox import MCPToolbox
from blackfox.physics import fire
from blackfox.physics import scenario as sc

VISITOR = "v" * 20


def test_merge_changes_only_what_is_given_and_reports_it():
    new, changed = sc.merge(sc.clean(None), {"o2_pct": 25, "vent_cm_s": 5})
    assert new["o2_pct"] == 25 and new["vent_cm_s"] == 5 and new["environment"] == "leo"
    assert changed == {"o2_pct": {"from": 21.0, "to": 25.0}, "vent_cm_s": {"from": 12.0, "to": 5.0}}
    again, nothing = sc.merge(new, {"o2_pct": 25})
    assert again == new and nothing == {}


def test_a_new_environment_starts_from_its_own_atmosphere_like_the_lab():
    cur, _ = sc.merge(sc.clean(None), {"o2_pct": 25, "pressure_kpa": 90, "temp_c": 30})
    moon, changed = sc.merge(cur, {"environment": "moon"})
    assert (moon["pressure_kpa"], moon["o2_pct"], moon["temp_c"]) == (None, None, None)
    assert changed["o2_pct"]["to"] == 34.0 and changed["pressure_kpa"]["to"] == 56.5
    kept, _ = sc.merge(cur, {"environment": "moon", "o2_pct": 30})
    assert kept["o2_pct"] == 30 and kept["pressure_kpa"] is None            # given values win, the rest resets
    same, _ = sc.merge(cur, {"environment": "leo"})
    assert same["o2_pct"] == 25                                              # same environment: nothing resets
    back, _ = sc.merge(cur, {}, reset_atmosphere=True)
    assert back["o2_pct"] is None


def test_a_new_place_gets_its_typical_material_unless_one_is_given():
    cur, _ = sc.merge(sc.clean(None), {"material": "nylon"})
    galley, changed = sc.merge(cur, {"location": "galley"})
    assert galley["material"] is None and changed["material"]["to"] == "polyethylene"
    both, _ = sc.merge(cur, {"location": "galley", "material": "kydex"})
    assert both["material"] == "kydex"
    default, _ = sc.merge(cur, {"material": "default"})
    assert default["material"] is None


@pytest.mark.parametrize("changes, words", [
    ({"o2_pct": 80}, "outside the allowed range 15 to 50"),
    ({"vent_cm_s": -3}, "outside the allowed range 0 to 40"),
    ({"pressure_kpa": "lots"}, "must be a number"),
    ({"environment": "venus"}, "choose one of: leo, lunar_orbit, moon, mars, earth"),
    ({"material": "wood"}, "ptfe_wire"),
    ({"suppression": "foam"}, "none, co2, water_mist"),
    ({"auto_vent_shutdown": "maybe"}, "use on or off"),
    ({"colour": "red"}, "unknown setting colour"),
])
def test_bad_values_are_refused_with_the_valid_choices(changes, words):
    with pytest.raises(ValueError, match=words):
        sc.merge(sc.clean(None), changes)


def test_limits_match_the_limits_the_api_and_the_model_use():
    from app.main import FireIn
    cat = fire.catalog()["limits"]
    for name, (lo, hi) in sc.LIMITS.items():
        if name in cat:
            assert tuple(cat[name]) == (lo, hi), name
        meta = {type(m).__name__: m for m in FireIn.model_fields[name].metadata}
        assert (meta["Ge"].ge, meta["Le"].le) == (lo, hi), name
    assert set(sc.FIELDS) == set(FireIn.model_fields)
    assert sc.clean(FireIn().model_dump()) == sc.clean(None)                 # same defaults as the API


def test_every_allowed_extreme_is_a_scenario_the_model_can_simulate():
    for k, (lo, hi) in sc.LIMITS.items():
        for v in (lo, hi):
            new, _ = sc.merge(sc.clean(None), {k: v})
            assert sc.brief(sc.run(new))["risk"]
    for env in sc._names()["environment"]:
        for loc in sc._names()["location"]:
            sc.run(sc.merge(sc.clean(None), {"environment": env, "location": loc})[0])


def test_store_keeps_a_scenario_per_visitor(tmp_path):
    store = sc.ScenarioStore(tmp_path / "s.db")
    assert store.get("a") == sc.clean(None)
    store.put("a", {"environment": "mars", "o2_pct": 30.0, "junk": 1})
    assert store.get("a")["environment"] == "mars" and "junk" not in store.get("a")
    assert store.get("b") == sc.clean(None)
    store.delete("a")
    assert store.get("a") == sc.clean(None)


def call(name, **args):
    async def go():
        async with MCPToolbox(context={"visitor_id": VISITOR}) as tb:
            out, err = await tb.call(name, args)
            return json.loads(out), err, [t["function"]["name"] for t in tb.openai_tools()]
    return asyncio.run(go())


def test_the_model_sees_the_tools_but_never_the_visitor_id():
    _, _, names = call("fire_scenario_options")
    assert {"fire_scenario_options", "get_fire_scenario", "set_fire_scenario", "simulate_cabin_fire"} <= set(names)

    async def schema():
        async with MCPToolbox(context={"visitor_id": VISITOR}) as tb:
            await tb.call("open_tool_category", {"category": "physics"})     # tools are hidden until opened
            return next(t for t in tb.openai_tools() if t["function"]["name"] == "set_fire_scenario")
    params = asyncio.run(schema())["function"]["parameters"]["properties"]
    assert "visitor_id" not in params and {"environment", "o2_pct", "vent_cm_s", "suppression", "location"} <= set(params)


def test_set_fire_scenario_changes_what_get_fire_scenario_and_the_next_call_see():
    sc.get_store().put(VISITOR, sc.clean(None))
    out, err, _ = call("set_fire_scenario", environment="moon", o2_pct=30.0, vent_cm_s=0.0, suppression="water_mist")
    assert not err and "error" not in out
    assert out["scenario"]["environment"] == "moon" and out["scenario"]["o2_pct"] == 30.0
    assert out["scenario"]["pressure_kpa"] == 56.5 and out["scenario"]["vent_cm_s"] == 0.0     # 0 is a real value
    assert out["changed"]["environment"] == {"from": "leo", "to": "moon"}
    assert out["results"]["risk"] and "oxygen_margin_pct" in out["results"]
    assert sc.get_store().get(VISITOR)["environment"] == "moon"
    got, _, _ = call("get_fire_scenario")
    assert got["scenario"] == out["scenario"] and got["results"] == out["results"]
    rel, _, _ = call("set_fire_scenario", location="galley")                      # unset values keep their value
    assert rel["scenario"]["environment"] == "moon" and rel["scenario"]["material"] == "polyethylene"
    assert rel["changed"] == {"location": {"from": "avionics_rack", "to": "galley"},
                              "material": {"from": "ultem", "to": "polyethylene"}}


def test_a_refused_value_changes_nothing():
    sc.get_store().put(VISITOR, sc.clean({"environment": "mars", "o2_pct": 28.0}))
    out, _, _ = call("set_fire_scenario", environment="moon", o2_pct=70.0)
    assert "outside the allowed range 15 to 50" in out["error"]
    assert sc.get_store().get(VISITOR)["environment"] == "mars"                    # not even the valid half applied
    out, _, _ = call("set_fire_scenario", suppression="foam")
    assert "none, co2, water_mist" in out["error"]
    none, _, _ = call("set_fire_scenario")
    assert none["changed"] == "nothing differed from the current scenario"


def test_without_a_visitor_the_tools_point_to_the_stateless_run():
    async def go():
        async with MCPToolbox(context={}) as tb:
            return [json.loads((await tb.call(n, a))[0]) for n, a in
                    (("get_fire_scenario", {}), ("set_fire_scenario", {"o2_pct": 25}))]
    for out in asyncio.run(go()):
        assert "simulate_cabin_fire" in out["error"]


def test_simulate_cabin_fire_now_takes_every_setting_and_leaves_the_lab_alone():
    sc.get_store().put(VISITOR, sc.clean(None))
    on, _, _ = call("simulate_cabin_fire", environment="leo", auto_vent_shutdown=True, duration_s=240)
    off, _, _ = call("simulate_cabin_fire", environment="leo", auto_vent_shutdown=False, duration_s=240)
    assert on["inputs"]["duration_s"] == 240 and on["inputs"]["auto_vent_shutdown"] is True
    assert off["inputs"]["auto_vent_shutdown"] is False
    assert sc.get_store().get(VISITOR) == sc.clean(None)


def test_the_options_list_every_name_and_range():
    o = sc.options()
    assert set(o["environment"]) == set(fire.catalog()["environments"]) and "galley" in o["location"]
    assert o["ranges"]["o2_pct"] == {"min": 15, "max": 50, "unit": "% O2 by volume"}
    assert set(o["settings"]) == set(sc.FIELDS)


def test_the_mcp_server_publishes_the_tools_and_an_options_resource():
    from blackfox.mcp_server.server import INSTRUCTIONS, build_server
    server = build_server()
    assert "set_fire_scenario" in INSTRUCTIONS

    async def listing():
        tools = {t.name for t in await server.list_tools()}
        res = {str(r.uri) for r in await server.list_resources()}
        return tools, res
    tools, resources = asyncio.run(listing())
    assert {"set_fire_scenario", "get_fire_scenario", "fire_scenario_options"} <= tools
    assert "fire://options" in resources



def test_the_ai_reads_the_runs_the_user_started():
    from blackfox.physics.runs import get_runs
    get_runs().delete(VISITOR)
    empty, _, _ = call("get_simulation_runs")
    assert empty["runs"] == [] and "Start" in empty["note"]
    rid = get_runs().add(VISITOR, {**sc.effective({"environment": "mars"}), "lining": "pmma"}, {"risk": "high"}, {"tier": "low"})
    get_runs().set_spread(VISITOR, rid, {"status": "went_out", "rooms_reached": 1})
    out, err, _ = call("get_simulation_runs", limit=2)
    assert not err and out["runs"][0]["run_id"] == rid and out["runs"][0]["settings"]["environment"] == "mars"
    assert out["runs"][0]["spread_2d"]["status"] == "went_out" and out["runs"][0]["cabin_3d"]["risk"] == "high"
    for i in range(25):
        get_runs().add(VISITOR, {"n": i}, {}, {})
    assert len(get_runs().latest(VISITOR, 100)) == 20                      # only the newest 20 are kept


def test_the_new_suppression_agents_can_be_set_and_are_listed_with_their_behaviour():
    new, changed = sc.merge(sc.clean(None), {"suppression": "k_aerosol"})
    assert new["suppression"] == "k_aerosol" and changed == {"suppression": {"from": "co2", "to": "k_aerosol"}}
    assert set(sc.SUPPRESSION) == {"none", "co2", "water_mist", "k_aerosol", "clean_agent", "inert_n2"}
    o = sc.options()["suppression"]
    assert "by itself 10 s after the alarm" in o["clean_agent"] and "response_s does not apply" in o["inert_n2"]
    assert "by itself" not in o["co2"]
    assert sc.brief(sc.run(new))["risk"]
