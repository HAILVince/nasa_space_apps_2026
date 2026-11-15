"""Backend workspace: the flame-calculator endpoints used by the 2D simulation (frontend/spread.html)."""

import json

import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def test_materials_lists_measured_ids(client):
    mats = client.get("/api/flame/materials").json()["materials"]
    assert {"nomex_ht90_40", "pmma"} <= set(mats)


def test_check_returns_verdict_and_margin_range(client):
    r = client.get("/api/flame/check", params={"material_id": "nomex_ht90_40", "o2_pct": 34,
                                               "pressure_kpa": 56.5, "gravity": "lunar"})
    assert r.status_code == 200
    d = r.json()
    assert d["verdict"] == "above_measured_limit"
    lo, hi = d["margin_range_pct"]
    assert lo <= d["margin_pct"] <= hi and d["caveats"] and d["sources"]


def test_check_rejects_unknown_material_and_bad_input(client):
    base = {"o2_pct": 21, "pressure_kpa": 101.3, "gravity": "earth"}
    assert client.get("/api/flame/check", params={**base, "material_id": "paper"}).status_code == 404
    assert client.get("/api/flame/check", params={**base, "material_id": "pmma", "gravity": "venus"}).status_code == 422
    assert client.get("/api/flame/check", params={**base, "material_id": "pmma", "o2_pct": 120}).status_code == 422


def test_coverage_counts_psi_envelopes(client):
    d = client.get("/api/flame/coverage", params={"o2_pct": 34, "pressure_kpa": 56.5}).json()
    assert sum(d["counts"].values()) == len(d["envelopes"]) > 0
    assert "solid_fuel_covered" in d


def test_tests_returns_real_rows_with_source(client):
    d = client.get("/api/flame/tests", params={"o2_pct": 21, "pressure_kpa": 101.3, "fuel_phase": "solid"}).json()
    assert d["tests"] and all(t["fuel_phase"] == "solid" and ".csv row " in t["source"] for t in d["tests"])
    assert client.get("/api/flame/tests", params={"o2_pct": 21, "pressure_kpa": 101.3, "fuel_phase": "plasma"}).status_code == 422


def test_context_exposes_earth_benefits_for_each_envelope(client):
    d = client.get("/api/flame/context").json()
    assert d["investigationCount"] == len(d["investigations"]) > 0
    by_acc = {i["accession"]: i for i in d["investigations"]}
    assert set(by_acc["PSI-10"]) == {"accession", "acronym", "title", "fuelPhase", "earthBenefits", "psiUrl"}
    assert "coal power plants" in by_acc["PSI-10"]["earthBenefits"]     # NASA's text, unmodified
    assert by_acc["PSI-10"]["psiUrl"].startswith("https://psi.nasa.gov/")
    # every envelope the lab draws can be matched to its investigation's Earth benefit
    assert all(by_acc[e["accession"]]["earthBenefits"] for e in d["envelopes"])


def test_every_investigation_links_to_its_own_psi_record(client):
    for i in client.get("/api/flame/context").json()["investigations"]:
        assert i["psiUrl"].startswith("https://psi.nasa.gov/"), i["accession"]
        assert f"q={i['accession']}&" in i["psiUrl"], i["accession"]     # the search page for that exact record



def test_context_includes_cited_habitat_insights(client):
    data = client.get('/api/flame/context').json()
    assert len(data['insights']['moon-base']) >= 2
    accessions = {i['accession'] for i in data['investigations']}
    for insights in data['insights'].values():
        for insight in insights:
            assert insight['text'] and insight['cited']
            assert all(c in accessions for c in insight['cited'] if c.startswith('PSI-'))


def test_sweep_groups_one_investigation_by_configuration(client):
    d = client.get("/api/flame/sweep", params={"accession": "PSI-10"}).json()
    assert d["accession"] == "PSI-10" and d["rows"] == 327
    assert {c["config"] for c in d["configurations"]} == {"inverse", "normal"}
    assert sum(c["rows"] for c in d["configurations"]) == d["rows"]
    c = d["configurations"][0]
    assert len(c["o2_pct"]) == 2 and c["sources"][0]["table"].startswith("PSI-10_") and c["sources"][0]["row_ranges"]
    assert d["gap"] is None and d["note"]


def test_sweep_states_why_an_investigation_has_no_table(client):
    d = client.get("/api/flame/sweep", params={"accession": "PSI-26"}).json()
    assert d["configurations"] == [] and d["rows"] == 0
    assert d["gap"]["reason_code"] == "no_conditions" and d["gap"]["raw_table"] == "PSI-26_bass.csv"
    assert len(d["without_rows"]) == 11 and "PSI-26" in {g["accession"] for g in d["without_rows"]}
    assert "PSI-26" not in d["with_rows"] and "PSI-25" in d["with_rows"]


def test_sweep_rejects_unknown_and_missing_accession(client):
    assert client.get("/api/flame/sweep", params={"accession": "PSI-9999"}).status_code == 404
    assert client.get("/api/flame/sweep", params={"accession": "../etc"}).status_code == 404
    assert client.get("/api/flame/sweep").status_code == 422


def test_check_reports_whether_the_limit_was_checked_against_its_source(client):
    base = {"o2_pct": 21, "pressure_kpa": 101.3}
    nomex = client.get("/api/flame/check", params={**base, "material_id": "nomex_ht90_40", "gravity": "earth"}).json()
    assert nomex["verified"] is True and nomex["unchecked_reason"] is None
    pmma = client.get("/api/flame/check", params={**base, "material_id": "pmma", "gravity": "lunar"}).json()
    assert pmma["verified"] is False and pmma["unchecked_reason"]


def test_gapmap_route_returns_the_map_data_unchanged(client):
    from flame.gapmap import gap_map
    d = client.get("/api/flame/gapmap").json()
    assert d["axes"] == {"pressureKPa": [0, 120], "o2Pct": [0, 100]}
    assert d["rectangles"] and all(len(r["o2Pct"]) == 2 and len(r["pressureKPa"]) == 2 for r in d["rectangles"])
    assert d["habitats"] and d["isoPo2"] and d["unplaced"] and "incidents" in d
    ids = {h["id"] for h in d["habitats"]}
    assert set(d["coverage"]) == ids and set(d["coverageByPhase"]) == ids          # one entry per habitat id
    assert all(isinstance(n, int) and n >= 0 for n in d["coverage"].values())
    assert d == json.loads(json.dumps(gap_map()))                                  # the function's output, only as JSON


def test_gapmap_micro_only_param_filters_ground_envelopes_and_rejects_junk(client):
    all_ = client.get("/api/flame/gapmap").json()
    micro = client.get("/api/flame/gapmap", params={"micro_only": "true"}).json()
    assert {r["gravity"] for r in micro["rectangles"]} <= {"micro"} and len(micro["rectangles"]) <= len(all_["rectangles"])
    assert client.get("/api/flame/gapmap", params={"micro_only": "maybe"}).status_code == 422


def test_finance_endpoint(client):
    items = client.get("/api/flame/finance").json()["items"]
    assert any(i["id"] == "iss_crew_time_price" and i["value"] == 130000 for i in items)
    assert all(i["group"] == "lunar_landers" for i in client.get("/api/flame/finance", params={"group": "lunar_landers"}).json()["items"])
    assert client.get("/api/flame/finance", params={"group": "mars"}).status_code == 422


def test_events_endpoint(client):
    ev = {e["id"]: e for e in client.get("/api/flame/events").json()["events"]}
    assert ev["mir-1997-candle-fire"]["masksH"] == 2.5 and ev["iss-2006-elektron"]["emergencyH"] == 2
