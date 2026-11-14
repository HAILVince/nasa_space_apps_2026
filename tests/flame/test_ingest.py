"""PSI ingest: raw search hits -> Investigation rows. Offline; the fixture holds two real hits."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from flame.ingest import psi

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "psi_sample.json").read_text(encoding="utf-8"))
RAW = {h["_source"]["Accession"]: h["_source"] for h in SAMPLE["hits"]["hits"]}


class FakeHttp:
    def json(self, method, url, **kw):
        self.seen = (method, url, kw["params"])
        return SAMPLE


def test_fetch_raw_asks_for_every_hit():
    http = FakeHttp()
    raw = psi.fetch_raw(http)
    assert [r["Accession"] for r in raw] == list(RAW)
    assert http.seen[2]["size"] == 200          # the API's default page stops at 25 of 26


def test_split_list():
    assert psi.split_list("Flame Spread     extinction limits     MSG") == ["Flame Spread", "extinction limits", "MSG"]
    assert psi.split_list("") == [] and psi.split_list(None) == []


def test_normalize_bass2():
    inv = psi.normalize(RAW["PSI-25"])
    assert (inv.accession, inv.acronym, inv.kind, inv.fuel_phase) == ("PSI-25", "BASS-II", "flight", "solid")
    assert "MSG" in inv.hardware and inv.related == ["PSI-26"]
    assert len(inv.publications) >= 3
    assert inv.publications[0].title.startswith("Microgravity flammability boundary")
    assert inv.publications[0].authors == "Olson Sandra L., Ferkul Paul V."
    assert "suppression" in inv.topics and inv.summary == "" and "PSI-25" in inv.psi_url
    assert "  " not in inv.objectives


def test_normalize_flex():
    inv = psi.normalize(RAW["PSI-69"])
    assert inv.hardware == ["CIR", "MDCA"]      # PSI spells it "Appartatus"; the alias still has to match
    assert inv.fuel_phase == "liquid" and "suppression" in inv.topics


def test_overrides_win_and_are_validated():
    inv = psi.normalize(RAW["PSI-25"])
    assert psi.apply_overrides(inv, {"PSI-25": {"fuelPhase": "gas", "topics": ["detection"]}}).fuel_phase == "gas"
    assert psi.apply_overrides(inv, {"PSI-69": {"fuelPhase": "gas"}}) == inv
    with pytest.raises(ValidationError):
        psi.apply_overrides(inv, {"PSI-25": {"fuelphase": "gas"}})


def test_only_combustion_science_is_kept():
    assert psi.is_combustion(RAW["PSI-25"])
    assert not psi.is_combustion({**RAW["PSI-25"], "Research Area": "Fluid Physics"})


def test_ground_study_without_acronym_falls_back_to_accession():
    raw = {**RAW["PSI-25"], "Acronym": "", "Project Type": "Ground Investigation", "Experiment Hardware": ""}
    inv = psi.normalize(raw)
    assert (inv.acronym, inv.kind, inv.hardware) == ("PSI-25", "ground", [])
