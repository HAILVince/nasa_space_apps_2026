"""Flame workspace (flame/): the data contract every other part codes against."""

import pytest
from pydantic import ValidationError

from flame.models import Envelope, Habitat, Incident, Investigation

BASS2 = {
    "accession": "PSI-25", "acronym": "BASS-II", "title": "Burning and Suppression of Solids - II",
    "kind": "flight", "subArea": "Solid fuels", "fuelPhase": "solid", "hardware": ["MSG", "SPICE duct"],
    "topics": ["prevention", "suppression"], "objectives": "o", "approach": "a", "hypothesis": "h",
    "earthBenefits": "e", "related": ["PSI-26"],
    "publications": [{"title": "Microgravity flammability boundary for PMMA rods", "doi": "10.1/x"}],
    "psiUrl": "https://psi.nasa.gov/", "summary": "",
}
ENVELOPE = {
    "accession": "PSI-25", "label": "PMMA rods, opposed flow", "fuel": "PMMA", "geometry": "rod, 6.35 mm dia",
    "o2Pct": [15, 21], "pressureKPa": [101.3, 101.3], "flowMps": None, "gravity": "micro",
    "measured": ["flame spread rate"], "sensors": ["color video"], "keyFinding": "k",
    "provenance": [{"source": "PSI-25", "quote": "q"}], "verified": False,
}
MOON_BASE = {
    "id": "moon-base", "name": "Lunar surface habitat", "body": "moon", "o2Pct": [30, 34],
    "pressureKPa": [56.5, 70.3], "gravity": "lunar", "gravityG": 0.166, "assumed": False,
    "sourceUrl": "https://www.nasa.gov/", "notes": "challenge: >=30 % O2, <=10.2 psi",
    "marker": {"planet": "moon", "lat": -89.5, "lon": 0},
}


def test_investigation_reads_and_writes_the_camelcase_contract():
    inv = Investigation.model_validate(BASS2)
    assert inv.fuel_phase == "solid" and inv.psi_url.startswith("https://") and inv.doi is None
    out = inv.model_dump(by_alias=True)
    assert out["fuelPhase"] == "solid" and out["earthBenefits"] == "e" and "fuel_phase" not in out


def test_envelope_pressure_key_is_kpa_and_ranges_may_be_null():
    env = Envelope.model_validate(ENVELOPE)
    assert env.pressure_kpa == (101.3, 101.3) and env.flow_mps is None and env.diluent is None
    assert "pressureKPa" in env.model_dump(by_alias=True)
    assert Envelope.model_validate({**ENVELOPE, "o2Pct": None, "pressureKPa": None}).o2_pct is None


def test_habitat_rejects_pressure_given_in_psi():
    assert Habitat.model_validate(MOON_BASE).marker.lat == -89.5
    with pytest.raises(ValidationError):
        Habitat.model_validate({**MOON_BASE, "pressureKPa": "10.2 psi"})


@pytest.mark.parametrize("model, good, patch", [
    (Envelope, ENVELOPE, {"o2Pct": [40, 21]}),            # range the wrong way round
    (Envelope, ENVELOPE, {"o2Pct": [21, 140]}),           # more than 100 % oxygen
    (Envelope, ENVELOPE, {"gravity": "lunar"}),           # PSI has no lunar-g tests; only a proxy class
    (Habitat, MOON_BASE, {"pressureKPa": [0, 70.3]}),     # a cabin at zero pressure is a typo
    (Investigation, BASS2, {"accession": "BASS-II"}),     # accession must look like PSI-25
    (Investigation, BASS2, {"fuelphase": "solid"}),       # misspelt key must not pass silently
    (Investigation, BASS2, {"topics": ["safety"]}),
])
def test_bad_rows_are_rejected(model, good, patch):
    with pytest.raises(ValidationError):
        model.model_validate({**good, **patch})


def test_incident_without_a_cabin_atmosphere():
    apollo13 = Incident.model_validate({
        "id": "apollo-13", "name": "Apollo 13", "year": 1970, "o2Pct": None, "pressureKPa": None,
        "cabinFire": False, "lesson": "l", "sourceUrl": "https://www.nasa.gov/"})
    assert apollo13.cabin_fire is False and apollo13.pressure_kpa is None
