"""The committed dataset in flame/data/ loads, validates and is consistent across files."""

import pytest

from flame import data
from flame.units import kpa_to_psi, mid, o2_partial_kpa, psi_to_kpa


def test_all_files_load():
    assert len(data.get_habitats()) == 6
    assert len(data.get_investigations()) >= 3
    assert len(data.get_incidents()) == 4
    assert data.get_insights("moon-base") == () or data.get_insights("moon-base")[0].habitat_id == "moon-base"
    assert isinstance(data.get_demo_answers(), tuple)


def test_lookups():
    moon = data.get_habitat("moon-base")
    assert moon.gravity == "lunar" and moon.o2_pct == (30, 34) and moon.pressure_kpa == (56.5, 70.3)
    assert data.get_habitat("nope") is None and data.get_investigation("PSI-0") is None
    assert data.get_investigation("PSI-25").acronym == "BASS-II"
    assert all(e.accession == "PSI-25" for e in data.get_envelopes("PSI-25")) and data.get_envelopes("PSI-25")


def test_files_agree_with_each_other():
    known = {i.accession for i in data.get_investigations()}
    assert len(known) == len(data.get_investigations()), "duplicate accession"
    assert {e.accession for e in data.get_envelopes()} <= known
    habitats = [h.id for h in data.get_habitats()]
    assert len(set(habitats)) == len(habitats)
    assert {i.habitat_id for h in habitats for i in data.get_insights(h)} <= set(habitats)


def test_no_source_means_assumed():
    # a habitat may only drop the "assumed" tag once a source is on record
    for h in data.get_habitats():
        assert h.assumed or h.source_url.startswith("https://"), h.id
    assert data.get_habitat("mars-base").assumed


def test_only_cabin_fires_carry_an_atmosphere_point():
    by_id = {i.id: i for i in data.get_incidents()}
    assert by_id["apollo-1"].cabin_fire and by_id["apollo-1"].o2_pct == 100
    assert not by_id["apollo-13"].cabin_fire


def test_bad_file_names_the_file(tmp_path, monkeypatch):
    (tmp_path / "habitats.json").write_text('[{"id": "x", "pressureKPa": "10.2 psi"}]')
    monkeypatch.setattr(data, "DATA", tmp_path)
    data._load.cache_clear()
    with pytest.raises(ValueError, match="habitats.json"):
        data.get_habitats()
    data._load.cache_clear()


def test_units():
    assert kpa_to_psi(101.3) == pytest.approx(14.69, abs=0.01)
    assert psi_to_kpa(10.2) == pytest.approx(70.33, abs=0.01)
    assert o2_partial_kpa(21, 101.3) == pytest.approx(21.27, abs=0.01)
    assert mid((30, 34)) == 32
