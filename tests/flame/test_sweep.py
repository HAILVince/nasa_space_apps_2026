"""flame.sweep: every configuration one PSI investigation tested, grouped from psi_tests.json."""
import csv
from pathlib import Path

import pytest

from flame import data, sweep

RAW = Path(__file__).resolve().parents[2] / "blackfox" / "db" / "knowledge" / "raw_data" / "psi_combustion" / "tables"
WITH_ROWS = sorted({t.accession for t in data.get_psi_tests()})


@pytest.mark.parametrize("acc", WITH_ROWS)
def test_configuration_rows_add_up_to_the_investigations_rows(acc):
    out = sweep.sweep(acc)
    assert sum(c["rows"] for c in out["configurations"]) == out["rows"] == len(data.get_psi_tests(acc))
    for c in out["configurations"]:
        assert c["ignited"] + c["not_ignited"] + c["ignition_unreported"] == c["rows"]
        assert sum(c["kinds"].values()) == c["rows"]


@pytest.mark.parametrize("table", ["PSI-25_bass-ii.csv", "PSI-39_cfi.csv", "PSI-101_same-r.csv"])
def test_row_count_equals_the_raw_csv_rows(table):
    acc = table.split("_")[0]
    with open(RAW / table, encoding="utf-8-sig", newline="") as f:
        raw_rows = sum(1 for _ in csv.reader(f)) - 1          # minus the header line
    assert sweep.sweep(acc)["rows"] == raw_rows


def test_ranges_and_ignition_counts_match_the_rows():
    rows = data.get_psi_tests("PSI-10")
    out = sweep.sweep("PSI-10")
    assert {c["config"] for c in out["configurations"]} == {t.config for t in rows} == {"inverse", "normal"}
    for c in out["configurations"]:
        mine = [t for t in rows if t.config == c["config"]]
        o2 = [x for t in mine if t.o2_pct for x in t.o2_pct]
        assert c["o2_pct"] == [min(o2), max(o2)]
        assert c["ignited"] == sum(t.ignited is True for t in mine)
        assert c["unreported"]["flow_mps"] == sum(t.flow_mps is None for t in mine)


def test_rows_without_a_configuration_are_their_own_group():
    out = sweep.sweep("PSI-25")                       # BASS-II tables give no configuration
    assert [c["config"] for c in out["configurations"]] == [None]
    assert out["configurations"][0]["rows"] == 129


def test_sources_point_back_to_file_and_rows():
    out = sweep.sweep("PSI-25")
    src = out["configurations"][0]["sources"]
    assert src == [{"table": "PSI-25_bass-ii.csv", "row_ranges": [[1, 129]], "rows": 129}]
    assert out["tables"] == ["PSI-25_bass-ii.csv"]


def test_unknown_accession_is_none():
    assert sweep.sweep("PSI-9999") is None and sweep.sweep("nonsense") is None


def test_investigation_without_rows_states_its_reason_instead_of_an_empty_table():
    out = sweep.sweep("PSI-26")                       # BASS: a raw CSV exists, but only material + test number
    assert out["rows"] == 0 and out["configurations"] == []
    assert "material and test number only" in out["gap"]["reason"]
    assert out["gap"]["raw_table"] == "PSI-26_bass.csv"
    model = sweep.sweep("PSI-62")                     # ground modelling study: no table at all
    assert model["gap"]["raw_table"] is None and "no experiment table" in model["gap"]["reason"]
    assert sweep.sweep("PSI-25")["gap"] is None


def test_gaps_list_every_investigation_with_no_rows():
    gaps = {g["accession"]: g for g in sweep.gaps()}
    assert set(gaps) == {i.accession for i in data.get_investigations()} - set(WITH_ROWS)
    assert len(gaps) == 11 and all(g["reason"] for g in gaps.values())
    assert sweep.sweep("PSI-25")["without_rows"] == sweep.gaps()
