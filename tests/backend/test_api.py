"""Backend workspace (app/): the HTTP contract in docs/API.md. The AI agent is faked."""

import pytest
from fastapi.testclient import TestClient

import app.main as main
from blackfox.harness.agent import AgentResult


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def run(self, msg, conversation_id, visitor_id, lang="en", profile=None, extra_trace=None):
        self.calls.append({"msg": msg, "lang": lang, "profile": profile})
        res = AgentResult(text="fake answer", model="fake")
        main.get_memory().append(conversation_id, visitor_id, "user", msg)
        main.get_memory().append(conversation_id, visitor_id, "assistant", res.text, model="fake",
                                 trace=extra_trace(res) if extra_trace else [])
        return res


@pytest.fixture
def client(monkeypatch):
    fake = FakeAgent()
    monkeypatch.setattr(main, "get_agent", lambda: fake)
    main._recent.clear()
    with TestClient(main.app) as c:
        c.fake = fake
        yield c


def test_health(client):
    assert client.get("/healthz").json()["ok"] is True
    assert client.get("/api/health").json()["service"] == "blackfox"


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<textarea" in r.text and "./js/app.js" in r.text


def test_chat_goes_to_agent_with_design(client):
    r = client.post("/api/chat", json={"message": "hello", "lang": "hu"})
    assert r.status_code == 200
    m = r.json()["message"]
    assert m["role"] == "assistant" and m["text"] == "fake answer" and "html" in m
    call = client.fake.calls[-1]
    assert call["lang"] == "hu" and "DESIGN:" in call["profile"]["design"]


def test_command_is_instant_and_has_snapshot(client):
    r = client.post("/api/chat", json={"message": "set environment.crew = 7"})
    m = r.json()["message"]
    assert "crew 7" in m["snapshot"] and not client.fake.calls


def test_errors(client):
    assert client.post("/api/chat", json={"message": "   "}).json()["error"] == "empty"
    assert client.post("/api/chat", json={"message": "x" * 1500}).json()["error"] == "too_long"


def test_session_history_and_cookies(client):
    client.post("/api/chat", json={"message": "show"})
    j = client.get("/api/session").json()
    assert [m["role"] for m in j["messages"]][-2:] == ["user", "assistant"]
    assert j["messages"][-1]["snapshot"]
    assert "bfx_vid" in client.cookies and "bfx_cid" in client.cookies


def test_design_endpoint(client):
    assert client.get("/api/design").json()["snapshot"].startswith("DESIGN:")


def test_forget_clears_everything(client):
    client.post("/api/chat", json={"message": "set environment.crew = 9"})
    assert client.post("/api/memory/forget").json()["ok"]
    assert "crew 9" not in client.get("/api/design").json()["snapshot"]


def test_fire_catalog_simulate_and_evidence(client):
    cat = client.get("/api/fire/catalog").json()
    assert {"leo", "lunar_orbit", "moon", "mars", "earth"} <= set(cat["environments"])
    r = client.post("/api/fire/simulate", json={"environment": "moon", "location": "galley", "o2_pct": 34}).json()
    assert r["inputs"]["material"] == "polyethylene" and r["flammability"]["flammable"]
    assert client.post("/api/fire/simulate", json={"environment": "moon", "o2_pct": 80}).status_code == 422
    assert client.post("/api/fire/simulate", json={"material": "unobtainium"}).status_code == 400
    ev = client.get("/api/fire/evidence", params={"environment": "leo", "material": "nomex"}).json()["records"]
    assert ev and ev[0]["status"] == "curated"


def test_chat_passes_the_fire_scenario_to_the_agent(client):
    r = client.post("/api/chat", json={"message": "why does it burn?", "lang": "en",
                                       "context": {"environment": "mars", "location": "galley"}})
    assert r.status_code == 200
    assert "environment=mars" in client.fake.calls[-1]["profile"]["fire_scenario"]
