"""The raw PSI tables -> flame/data/psi_tests.json cleaning step and the rows the calculator reads."""

import csv
import json

import pytest

from flame import calc, data
from flame.ingest import clean_tables as ct


def test_cell_parsing_handles_the_messy_spellings():
    assert ct.nums("~ 22.1") == [22.1]
    assert ct.nums("21.5 - 21.7") == [21.5, 21.7]
    assert ct.nums("LOW O2") == []                      # a formula is not a number
    assert ct.pct(0.21) == 21.0 and ct.pct(21) == 21 and ct.pct(3400) == 34.0


def test_committed_rows_match_a_fresh_cleaning_run():
    built = [t.model_dump(by_alias=True) for t in ct.build()]
    committed = [t.model_dump(by_alias=True) for t in data.get_psi_tests()]
    assert built == committed, "raw tables or cleaning changed: run `python -m flame.ingest clean`"


def test_every_row_points_back_to_its_raw_file_and_row():
    counts = {}
    for t in data.get_psi_tests():
        if t.table not in counts:
            counts[t.table] = len(ct.read(t.table))
        assert 1 <= t.source_row <= counts[t.table], (t.table, t.source_row)


def test_units_are_converted():
    flex = [t for t in data.get_psi_tests("PSI-69") if t.pressure_kpa]
    assert all(60 < t.pressure_kpa[0] < 320 for t in flex)             # mmHg -> kPa
    assert all(10 <= t.o2_pct[0] <= 40 for t in data.get_psi_tests("PSI-159") if t.o2_pct and t.config == "normal")
    assert max(t.flow_mps[1] for t in data.get_psi_tests("PSI-98")) == pytest.approx(0.2)   # cm/s -> m/s


def test_transcription_errors_stay_out_of_the_ranges():
    bass = data.get_psi_tests("PSI-25")
    assert min(t.o2_pct[0] for t in bass) > 10                          # final O2 '1.6' is dropped
    assert any("transcription error" in t.notes for t in bass)
    assert all(t.flow_mps is None or t.flow_mps[0] >= 0 for t in data.get_psi_tests("PSI-107"))


def test_envelopes_carry_the_raw_table_ranges():
    tests = data.get_psi_tests()
    for s in ct.summarise(tests):
        for e in data.get_envelopes(s["accession"]):
            if ct._envelope_key(e) == (s["accession"], s["gravity"], s["config"]) and s["o2_pct"]:
                assert list(e.o2_pct) == s["o2_pct"]
                assert any(p.source.startswith("PSI raw table") for p in e.provenance)


def test_clean_csvs_are_written(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "CLEAN", tmp_path / "clean")
    monkeypatch.setattr(ct.data, "DATA", tmp_path)
    tests = ct.build()
    ct.write(tests, ct.summarise(tests), list(data.get_envelopes()))
    with open(tmp_path / "clean" / "psi_tests.csv", encoding="utf-8") as f:
        assert sum(1 for _ in csv.DictReader(f)) == len(tests)
    assert len(json.loads((tmp_path / "psi_tests.json").read_text(encoding="utf-8"))) == len(tests)


def test_nearest_tests_cite_real_runs():
    out = calc.nearest_tests(21.0, 101.3, fuel_phase="liquid", limit=3)
    assert out["tests"] and out["tests"][0]["distance"] == 0
    assert all(".csv row " in t["source"] for t in out["tests"])


def test_mars_habitat_has_no_nearby_solid_runs():
    # 34 % O2 at 56.5 kPa: the closest burning-materials run in PSI is far below in oxygen
    near = calc.nearest_tests(34.0, 56.5, fuel_phase="solid", limit=1)["tests"][0]
    assert near["o2_gap_pct"] > 10
