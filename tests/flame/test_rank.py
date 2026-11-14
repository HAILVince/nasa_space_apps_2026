"""Relevance ranking per habitat: the formula from docs/flame/plan.md, Task 9."""

import pytest

from flame import data
from flame.models import Envelope, Habitat, Investigation
from flame.rank import DEFAULT_WEIGHTS, Weights, condition_proximity, rank_for_habitat


def habitat(o2, kpa, gravity="lunar"):
    return Habitat.model_validate({"id": "h", "name": "h", "body": "moon", "o2Pct": o2, "pressureKPa": kpa,
                                   "gravity": gravity, "gravityG": 0.166, "assumed": True, "sourceUrl": "", "notes": ""})


def envelope(o2, kpa, gravity="micro", accession="PSI-1"):
    return Envelope.model_validate({"accession": accession, "label": "l", "fuel": "f", "geometry": "g", "o2Pct": o2,
                                    "pressureKPa": kpa, "flowMps": None, "gravity": gravity, "measured": [],
                                    "sensors": [], "keyFinding": "k", "provenance": [], "verified": False})


def investigation(accession, kind="flight", phase="solid", topics=("prevention", "detection", "suppression")):
    return Investigation.model_validate({
        "accession": accession, "acronym": accession, "title": "t", "kind": kind, "subArea": "", "fuelPhase": phase,
        "hardware": [], "topics": list(topics), "objectives": "", "approach": "", "hypothesis": "",
        "earthBenefits": "", "related": [], "publications": [], "psiUrl": "", "summary": ""})


MOON = habitat([30, 34], [56.5, 70.3])


def test_overlap_is_full_proximity_before_the_gravity_factor():
    assert condition_proximity(MOON, [envelope([21, 40], [50, 101.3])]) == pytest.approx(0.85)   # lunar vs micro
    assert condition_proximity(MOON, [envelope([21, 40], [50, 101.3], "partial-proxy")]) == 1
    iss = habitat([21, 21], [101.3, 101.3], "micro")
    assert condition_proximity(iss, [envelope([21, 21], [101.3, 101.3])]) == 1
    assert condition_proximity(iss, [envelope([21, 21], [101.3, 101.3], "earth")]) == pytest.approx(0.6)


def test_distance_uses_oxygen_points_and_log_pressure():
    # 9 points of oxygen away, same pressure: d = 9/79
    assert condition_proximity(MOON, [envelope([15, 21], [56.5, 70.3], "partial-proxy")]) == pytest.approx(1 - 9 / 79)
    far, near = envelope([15, 21], [101.3, 101.3]), envelope([28, 29], [70.3, 80])
    assert condition_proximity(MOON, [far, near]) == condition_proximity(MOON, [near])        # the closest one counts
    assert condition_proximity(MOON, [envelope([0, 1], [5000, 5000])]) == 0                      # never negative


def test_missing_numbers_do_not_crash():
    assert condition_proximity(MOON, []) == 0
    assert condition_proximity(MOON, [envelope(None, [56.5, 70.3]), envelope([30, 34], None)]) == 0
    (row,) = rank_for_habitat(MOON, [investigation("PSI-1")], [envelope(None, None)])
    assert row.no_condition_data and row.parts["condition"] == 0
    assert rank_for_habitat(MOON, [investigation("PSI-1")], [])[0].no_condition_data


def test_score_is_the_weighted_sum():
    (row,) = rank_for_habitat(MOON, [investigation("PSI-1")], [envelope([21, 40], [50, 101.3])])
    assert row.parts == {"condition": pytest.approx(0.85), "topic": 1, "fuel": 1, "flight": 1}
    assert row.score == pytest.approx(0.45 * 0.85 + 0.25 + 0.20 + 0.10, abs=1e-9) and not row.no_condition_data
    (ground,) = rank_for_habitat(MOON, [investigation("PSI-2", "ground", "gas", ("fundamental",))], [])
    assert ground.parts == {"condition": 0, "topic": 0, "fuel": 0.5, "flight": 0.5}
    assert ground.score == pytest.approx(0.20 * 0.5 + 0.10 * 0.5)


def test_weights_change_the_order_and_ties_go_by_accession():
    invs = [investigation("PSI-10", topics=("fundamental",)), investigation("PSI-9", "ground")]
    envs = [envelope([30, 34], [56.5, 70.3], accession="PSI-10")]
    assert [r.accession for r in rank_for_habitat(MOON, invs, envs)] == ["PSI-10", "PSI-9"]
    no_condition = Weights(condition=0, topic=0.25, fuel=0.20, flight=0.10)
    assert [r.accession for r in rank_for_habitat(MOON, invs, envs, no_condition)] == ["PSI-9", "PSI-10"]
    same = [investigation("PSI-10"), investigation("PSI-9")]
    assert [r.accession for r in rank_for_habitat(MOON, same, [])] == ["PSI-9", "PSI-10"]


def test_real_dataset_ranks_all_24_for_every_habitat():
    assert DEFAULT_WEIGHTS == Weights(0.45, 0.25, 0.20, 0.10)
    for h in data.get_habitats():
        rows = rank_for_habitat(h)
        assert len(rows) == 24 and all(0 <= r.score <= 1 for r in rows)
        assert [r.score for r in rows] == sorted((r.score for r in rows), reverse=True)
        assert all(r.acronym and r.title for r in rows)
