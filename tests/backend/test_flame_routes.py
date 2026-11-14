"""Backend workspace: search, per-habitat ranking and gap map (app/flame_routes.py), and the
difference rows added to the research comparison."""

import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def test_search_ranks_and_filters(client):
    body = client.get("/api/flame/investigations", params={"q": "BASS-II"}).json()
    first = body["investigations"][0]
    assert first["accession"] == "PSI-25" and first["score"] > 0 and body["count"] == len(body["investigations"])
    assert {"acronym", "title", "summary", "kind", "fuelPhase", "topics", "hardware"} <= set(first)
    everything = client.get("/api/flame/investigations").json()
    assert everything["count"] == 24 and everything["investigations"][0]["accession"] == "PSI-10"
    ground = client.get("/api/flame/investigations", params={"kind": "ground"}).json()["investigations"]
    assert len(ground) == 5 and {r["kind"] for r in ground} == {"ground"}
    assert client.get("/api/flame/investigations", params={"fuel_phase": "plasma"}).status_code == 422


def test_one_investigation_comes_with_its_envelopes(client):
    body = client.get("/api/flame/investigations/PSI-25").json()
    assert body["acronym"] == "BASS-II" and body["psiUrl"] and body["publications"]
    assert body["envelopes"] and all(e["accession"] == "PSI-25" for e in body["envelopes"])
    assert client.get("/api/flame/investigations/PSI-9999").status_code == 404


def test_ranking_shows_its_weights_and_parts(client):
    body = client.get("/api/flame/habitats/moon-base/ranking").json()
    assert body["habitat"]["id"] == "moon-base" and body["habitat"]["o2Pct"] == [30, 34]
    assert body["weights"] == {"condition": 0.45, "topic": 0.25, "fuel": 0.2, "flight": 0.1}
    rows = body["investigations"]
    assert len(rows) == 24 and [r["score"] for r in rows] == sorted((r["score"] for r in rows), reverse=True)
    top = rows[0]
    assert set(top["parts"]) == {"condition", "topic", "fuel", "flight"} and top["noConditionData"] is False
    assert top["score"] == pytest.approx(sum(body["weights"][k] * top["parts"][k] for k in top["parts"]), abs=1e-3)


def test_ranking_takes_the_readers_weights(client):
    only_fuel = client.get("/api/flame/habitats/iss/ranking",
                           params={"condition": 0, "topic": 0, "fuel": 1, "flight": 0}).json()
    assert only_fuel["weights"]["fuel"] == 1 and only_fuel["investigations"][0]["score"] == 1     # a solid-fuel study
    assert client.get("/api/flame/habitats/atlantis/ranking").status_code == 404
    assert client.get("/api/flame/habitats/iss/ranking", params={"condition": 3}).status_code == 422


def test_gap_map(client):
    body = client.get("/api/flame/gapmap").json()
    assert {"axes", "rectangles", "unplaced", "habitats", "incidents", "isoPo2", "coverage"} <= set(body)
    assert body["coverage"]["suit"] == 0 and body["coverage"]["iss"] >= 1
    assert [i["id"] for i in body["incidents"]] == ["apollo-1"]
    micro = client.get("/api/flame/gapmap", params={"micro_only": "true"}).json()
    assert {r["gravity"] for r in micro["rectangles"]} == {"micro"}


def test_research_comparison_now_says_what_differs(client):
    body = client.get("/api/research/compare", params={"ids": "PSI-69,PSI-68,PSI-39"}).json()
    assert [r["id"] for r in body["investigations"]] == ["PSI-69", "PSI-68", "PSI-39"] and body["limitations"]
    rows = {r["attribute"]: r for r in body["rows"]}
    assert len(body["rows"]) == 13 and all(len(r["values"]) == 3 for r in body["rows"])
    assert rows["Hardware"]["differs"] is False and rows["Key finding"]["differs"] is True
    assert body["shared_hardware"] == ["CIR", "MDCA"]
    legacy = client.get("/api/research/compare", params={"ids": "bass,flex"}).json()
    assert [r["id"] for r in legacy["investigations"]] == ["bass", "flex"] and len(legacy["rows"][0]["values"]) == 2
