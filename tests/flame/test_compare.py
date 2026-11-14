"""Side-by-side comparison rows: order, formatting and the 'differs' flag."""

from flame import data
from flame.compare import ATTRIBUTES, compare_rows, shared_hardware

from test_rank import envelope, investigation     # same row builders as the ranking tests


def inv(accession, hardware, **kw):
    return investigation(accession, **kw).model_copy(update={"hardware": hardware, "objectives": "Burn things."})


def rows(invs, envs):
    return {r["attribute"]: r for r in compare_rows(invs, envs)}


def test_attribute_order_is_fixed():
    assert ATTRIBUTES == ("Objective", "Fuel phase", "Fuel / geometry", "O₂ %", "Pressure (kPa)", "Flow (m/s)",
                          "Diluent", "Gravity", "Hardware", "Sensors", "Measured", "Key finding", "Flight / ground")
    out = compare_rows([inv("PSI-1", []), inv("PSI-2", [])], [])
    assert tuple(r["attribute"] for r in out) == ATTRIBUTES and all(len(r["values"]) == 2 for r in out)


def test_same_hardware_in_another_order_is_not_a_difference():
    a, b = inv("PSI-1", ["CIR", "MDCA"]), inv("PSI-2", ["MDCA", "CIR"], phase="liquid")
    out = rows([a, b], [])
    assert out["Hardware"]["values"] == ["CIR, MDCA", "CIR, MDCA"] and out["Hardware"]["differs"] is False
    assert out["Fuel phase"]["values"] == ["solid", "liquid"] and out["Fuel phase"]["differs"] is True
    assert shared_hardware([a, b]) == ["CIR", "MDCA"] and shared_hardware([a, inv("PSI-3", ["MSG"])]) == []


def test_ranges_and_missing_values():
    envs = [envelope([21, 40], [101.3, 101.3]), envelope(None, None, accession="PSI-2")]
    out = rows([inv("PSI-1", []), inv("PSI-2", []), inv("PSI-3", [])], envs)
    assert out["O₂ %"]["values"] == ["21–40", "—", "—"]              # null range, and no envelope at all
    assert out["Pressure (kPa)"]["values"] == ["101.3", "—", "—"]    # min = max is one number
    assert out["Flow (m/s)"]["differs"] is False and out["Hardware"]["values"] == ["—"] * 3
    assert out["Gravity"]["values"] == ["micro", "micro", "—"]


def test_several_envelopes_are_joined():
    envs = [envelope([13.6, 22.2], [101.3, 101.3]), envelope([14, 18], [101.3, 101.3], "earth")]
    out = rows([inv("PSI-1", []), inv("PSI-2", [])], envs)
    assert out["O₂ %"]["values"][0] == "13.6–22.2; 14–18"
    assert out["Gravity"]["values"][0] == "micro; earth"
    assert out["Fuel / geometry"]["values"][0] == "f, g"              # the same value twice is written once
    assert out["Pressure (kPa)"]["values"][0] == "101.3" and out["Diluent"]["values"][0] == "—"


def test_long_objectives_are_cut_at_a_word():
    long = inv("PSI-1", []).model_copy(update={"objectives": "word " * 200})
    text = rows([long, inv("PSI-2", [])], [])["Objective"]["values"][0]
    assert len(text) <= 301 and text.endswith("word…")


def test_flex_family_on_the_real_dataset():
    invs = [data.get_investigation(a) for a in ("PSI-69", "PSI-68", "PSI-39")]
    out = rows(invs, data.get_envelopes())
    assert shared_hardware(invs) == ["CIR", "MDCA"] and out["Hardware"]["differs"] is False
    assert out["Flight / ground"]["values"] == ["flight"] * 3 and out["Key finding"]["differs"] is True
