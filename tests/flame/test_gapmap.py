"""Gap map data: what gets a rectangle, what is only listed, and how coverage is counted."""

import pytest

from flame import calc, data
from flame.gapmap import gap_map, iso_po2_curve
from flame.models import Incident

from test_rank import envelope, habitat, investigation     # same row builders as the ranking tests

ISS = habitat([21, 21], [101.3, 101.3], "micro").model_copy(update={"id": "iss"})
MOON = habitat([30, 34], [56.5, 70.3]).model_copy(update={"id": "moon-base"})
INVS = [investigation("PSI-1"), investigation("PSI-2", phase="liquid")]


def incident(id_, cabin, o2=100, kpa=115.1):
    return Incident.model_validate({"id": id_, "name": id_, "year": 1967, "o2Pct": o2, "pressureKPa": kpa,
                                    "cabinFire": cabin, "lesson": "l", "sourceUrl": ""})


def build(envs, **kw):
    return gap_map(envelopes=envs, investigations=INVS, habitats=[ISS, MOON],
                   incidents=[incident("apollo-1", True), incident("apollo-13", False), incident("mir", True, None, None)], **kw)


def test_only_envelopes_with_both_numbers_get_a_rectangle():
    out = build([envelope([15, 21], [101.3, 101.3]), envelope(None, [50, 150], accession="PSI-2")])
    assert [r["accession"] for r in out["rectangles"]] == ["PSI-1"]
    rect = out["rectangles"][0]
    assert rect["o2Pct"] == (15, 21) and rect["fuelPhase"] == "solid" and rect["verified"] is False
    # the other one is not dropped: it is listed with what is missing
    assert out["unplaced"] == [{"accession": "PSI-2", "acronym": "PSI-2", "label": "l", "missing": ["o2Pct"]}]


def test_micro_only_leaves_out_ground_tests():
    envs = [envelope([15, 21], [101.3, 101.3]), envelope([14, 18], [101.3, 101.3], "earth")]
    assert len(build(envs)["rectangles"]) == 2
    assert [r["gravity"] for r in build(envs, micro_only=True)["rectangles"]] == ["micro"]


def test_coverage_counts_investigations_whose_envelope_contains_the_habitat():
    envs = [envelope([15, 21], [101.3, 101.3]), envelope([20, 22], [90, 110]),            # both PSI-1: counted once
            envelope([10, 40], [50, 150], accession="PSI-2")]
    assert build(envs)["coverage"] == {"iss": 2, "moon-base": 1}
    assert build(envs[:2])["coverage"] == {"iss": 1, "moon-base": 0}
    assert build([envelope([21, 21], [101.3, 101.3], "earth")], micro_only=True)["coverage"]["iss"] == 0


def test_only_cabin_fires_with_a_known_atmosphere_are_drawn():
    assert [i["id"] for i in build([])["incidents"]] == ["apollo-1"]


def test_iso_curves_are_constant_oxygen_partial_pressure():
    curve = iso_po2_curve(21.3)
    assert curve[0] == (21.3, 100.0) and curve[-1][0] == 120
    assert all(p * o2 / 100 == pytest.approx(21.3) for p, o2 in curve)
    assert [c["po2KPa"] for c in build([])["isoPo2"]] == [21.3, 29.6, 50.0]


def test_real_dataset_agrees_with_the_calculator():
    out = gap_map()
    assert len(out["rectangles"]) + len(out["unplaced"]) == len(data.get_envelopes())
    assert {h["id"] for h in out["habitats"]} == {h.id for h in data.get_habitats()}
    for h in data.get_habitats():
        inside = {r["accession"] for r in calc.coverage_for_habitat(h.id)["envelopes"] if r["status"] == "inside"}
        assert out["coverage"][h.id] == len(inside), h.id


def test_coverage_by_phase_separates_the_fuels_that_covered_an_atmosphere():
    envs = [envelope([15, 21], [101.3, 101.3]),                                   # PSI-1 solid: covers the ISS
            envelope([10, 40], [50, 150], accession="PSI-2")]                     # PSI-2 liquid: covers both
    out = build(envs)
    assert out["coverage"] == {"iss": 2, "moon-base": 1}                          # the total is unchanged
    assert out["coverageByPhase"]["iss"] == {"solid": 1, "liquid": 1, "gas": 0, "aerosol": 0}
    assert out["coverageByPhase"]["moon-base"] == {"solid": 0, "liquid": 1, "gas": 0, "aerosol": 0}
    for hid, total in out["coverage"].items():                                    # one investigation has one phase
        assert sum(out["coverageByPhase"][hid].values()) == total


def test_real_data_moon_and_mars_atmospheres_have_no_solid_fuel_test():
    """The finding the gap map exists to show: at 30-34 % O2 / 56.5-70.3 kPa NASA tested liquid and gas fuels only."""
    out = gap_map()
    for hid in ("moon-base", "mars-base"):
        assert out["coverage"][hid] > 0 and out["coverageByPhase"][hid]["solid"] == 0, hid
        assert out["coverageByPhase"][hid]["liquid"] + out["coverageByPhase"][hid]["gas"] == out["coverage"][hid]
    assert out["coverage"]["suit"] == 0                                           # nothing at all near the suit atmosphere


def test_covered_by_names_the_investigations_behind_each_count():
    envs = [envelope([15, 21], [101.3, 101.3]), envelope([10, 40], [50, 150], accession="PSI-2")]
    assert build(envs)["coveredBy"] == {"iss": ["PSI-1", "PSI-2"], "moon-base": ["PSI-2"]}
    real = gap_map()
    assert all(len(real["coveredBy"][hid]) == n for hid, n in real["coverage"].items())
    assert real["coveredBy"]["suit"] == [] and "PSI-69" in real["coveredBy"]["moon-base"]
