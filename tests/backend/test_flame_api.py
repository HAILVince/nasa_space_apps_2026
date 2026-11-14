"""Backend workspace: the flame-calculator endpoints used by the 2D simulation (frontend/sim.html)."""

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



def test_context_includes_cited_habitat_insights(client):
    data = client.get('/api/flame/context').json()
    assert len(data['insights']['moon-base']) >= 2
    accessions = {i['accession'] for i in data['investigations']}
    for insights in data['insights'].values():
        for insight in insights:
            assert insight['text'] and insight['cited']
            assert all(c in accessions for c in insight['cited'] if c.startswith('PSI-'))
