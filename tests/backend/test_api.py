"""Backend workspace (app/): the HTTP contract in docs/API.md. The AI agent is faked."""

import json

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
    assert r.status_code == 200 and "./js/site.js" in r.text and "./lab.html" in r.text
    lab = client.get("/lab.html")
    assert lab.status_code == 200 and "<textarea" in lab.text and "./js/lab.js" in lab.text


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


def test_chat_failure_says_why_and_ai_status_reports_it(client, monkeypatch):
    async def no_answer(msg, conversation_id, visitor_id, lang="en", profile=None, extra_trace=None):
        return AgentResult(text="", error="big: HTTP 401 bad key", reason="auth")
    monkeypatch.setattr(client.fake, "run", no_answer)
    r = client.post("/api/chat", json={"message": "hello there"})
    assert r.status_code == 503 and r.json() == {"error": "unavailable", "reason": "auth"}

    class FakeLLM:
        async def status(self):
            return {"loopback": True, "key_set": True, "reachable": True, "authorized": False, "keyless": False,
                    "model": "", "problem": "auth"}
    monkeypatch.setattr(main, "get_llm", lambda: FakeLLM())
    monkeypatch.setattr(main, "_ai_status", (0.0, {}))
    body = client.get("/api/ai/status").json()
    assert body["ok"] is False and body["problem"] == "auth" and "key" not in {k for k in body if k != "key_set"}


def test_how_it_works_opens_the_main_simulators_fire_spread_view(client, monkeypatch, tmp_path):
    assert 'href="./lab.html?view=2d" data-i18n="cta_how"' in client.get("/").text
    r = client.get("/fire-sim")                                             # the teammate's spacecraft 2D section
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    page = main.FIRE_SIM.read_text(encoding="utf-8")
    assert "const MODE2D=true" in page and main.FIRE_SIM_BAR in r.text
    assert r.text.replace("\n" + main.FIRE_SIM_BAR, "", 1) == page        # the page itself is unchanged
    e = client.get("/fire-sim?embed=1")                                     # the lab's 2D tab shows it in a frame
    assert e.headers["content-security-policy"] == "frame-ancestors 'self'" and main.FIRE_SIM_BAR not in e.text
    monkeypatch.setattr(main, "FIRE_SIM", tmp_path / "missing.html")
    r = client.get("/fire-sim", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "./spread.html"


def test_chat_returns_the_scenario_only_when_the_ai_changed_it(client, monkeypatch):
    from blackfox.physics import scenario as sc
    ctx = {"environment": "leo", "location": "galley", "o2_pct": 22.0}
    r = client.post("/api/chat", json={"message": "why does it burn?", "context": ctx})
    assert r.status_code == 200 and "scenario" not in r.json()                # nothing changed: no payload
    vid = client.cookies.get("bfx_vid")
    assert sc.get_store().get(vid)["location"] == "galley"                    # the open scenario is remembered

    orig = client.fake.run

    async def ai_sets_the_lab(msg, conversation_id, visitor_id, lang="en", profile=None, extra_trace=None):
        new, _ = sc.merge(sc.get_store().get(visitor_id), {"environment": "moon", "o2_pct": 30})
        sc.get_store().put(visitor_id, new)
        return await orig(msg, conversation_id, visitor_id, lang, profile, extra_trace)
    monkeypatch.setattr(client.fake, "run", ai_sets_the_lab)
    r = client.post("/api/chat", json={"message": "put it on the Moon at 30 % oxygen", "context": ctx})
    got = r.json()["scenario"]
    assert got["environment"] == "moon" and got["o2_pct"] == 30 and got["location"] == "galley"
    assert set(got) == set(sc.FIELDS)                                         # exactly what the lab page keeps



START = {"scenario": {"environment": "moon", "location": "galley", "o2_pct": 30.0, "vent_cm_s": 0.0},
         "lining": "nomex", "device": {"tier": "low", "cores": 4, "memory_gb": 2, "mobile": True, "gpu": "Mali-G52", "cpu_ms": 410}}


def test_start_runs_the_cabin_model_and_saves_the_run_for_the_session(client):
    r = client.post("/api/sim/start", json=START)
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] >= 1 and body["result"]["inputs"]["environment"] == "moon" and body["result"]["series"]
    runs = client.get("/api/sim/runs").json()["runs"]
    assert len(runs) == 1 and runs[0]["run_id"] == body["run_id"]
    s = runs[0]["settings"]
    assert s["environment"] == "moon" and s["o2_pct"] == 30 and s["pressure_kpa"] == 56.5      # defaults filled in
    assert s["lining"] == "nomex" and s["material"] == "polyethylene" and s["vent_cm_s"] == 0
    assert runs[0]["cabin_3d"]["risk"] and "oxygen_margin_pct" in runs[0]["cabin_3d"]
    assert runs[0]["device"]["tier"] == "low" and runs[0]["spread_2d"] is None


def test_the_2d_outcome_joins_its_run_and_only_its_owner_can_send_it(client):
    rid = client.post("/api/sim/start", json=START).json()["run_id"]
    outcome = {"run_id": rid, "status": "burnt_out", "sim_time_s": 412.3, "rooms_reached": 3, "first_alarm_s": 41.0,
               "area_burned_cm2": 5075, "hottest_gas_c": 512, "lowest_o2_pct": 22.4, "vent_off_s": 41.0,
               "rooms": [{"room": "gal", "fire_s": 0, "smoke_s": 41, "max_gas_c": 512, "min_o2_pct": 22.4}], "junk": 1}
    assert client.post("/api/sim/spread", json=outcome).status_code == 200
    run = client.get("/api/sim/runs").json()["runs"][0]
    assert run["spread_2d"]["status"] == "burnt_out" and run["spread_2d"]["rooms"][0]["room"] == "gal" and "junk" not in run["spread_2d"]
    other = TestClient(main.app)                                           # another visitor (no cookies)
    assert other.post("/api/sim/spread", json=outcome).status_code == 404
    assert client.post("/api/sim/spread", json={**outcome, "status": "exploded"}).status_code == 422


def test_start_refuses_bad_input_and_forget_clears_the_runs(client):
    assert client.post("/api/sim/start", json={**START, "lining": "wood"}).status_code == 422
    assert client.post("/api/sim/start", json={"scenario": {"o2_pct": 80}}).status_code == 422
    assert client.post("/api/sim/start", json={"scenario": {"material": "wood"}}).status_code == 400
    client.post("/api/sim/start", json=START)
    assert client.get("/api/sim/runs").json()["runs"]
    client.post("/api/memory/forget")
    assert client.get("/api/sim/runs").json()["runs"] == []



def test_cfd_outcome_is_saved_with_its_grid_per_model(client):
    rid = client.post("/api/sim/start", json=START).json()["run_id"]
    out = {"run_id": rid, "model": "cfd_spacecraft", "status": "went_out", "sim_time_s": 95.5, "tier": "medium",
           "grid": {"dim": 3, "h": 0.25, "nx": 48, "ny": 19, "nz": 19}, "ignition": "N4", "peak_hrr_kw": 3.2,
           "rooms": [{"room": "node", "fire_s": 0, "smoke_s": 12.5, "max_gas_c": 410, "min_o2_pct": 31.2, "min_visibility_m": 2.4}]}
    assert client.post("/api/sim/outcome", json=out).status_code == 200
    assert client.post("/api/sim/outcome", json={**out, "model": "cfd_habitat", "grid": {"dim": 2, "h": 0.1}}).status_code == 200
    cfd = client.get("/api/sim/runs").json()["runs"][0]["cfd"]
    assert set(cfd) == {"cfd_spacecraft", "cfd_habitat"} and cfd["cfd_spacecraft"]["grid"]["h"] == 0.25
    assert cfd["cfd_spacecraft"]["rooms"][0]["min_visibility_m"] == 2.4
    assert TestClient(main.app).post("/api/sim/outcome", json=out).status_code == 404       # not this visitor's run
    assert client.post("/api/sim/outcome", json={**out, "model": "cfd_mars_base"}).status_code == 422


def test_chat_reply_carries_the_last_show_on_page_action(client, monkeypatch):
    from blackfox.harness.agent import ToolStep
    from blackfox.tools.ui_tools import show_on_page

    def step(target, err=False):
        return ToolStep("show_on_page", {"target": target}, json.dumps(show_on_page(target, note="here")), err, 1)

    async def run(msg, conversation_id, visitor_id, lang="en", profile=None, extra_trace=None):
        steps = [step("oxygen"), ToolStep("calculate", {}, "{}", False, 1), step("gap_map"), step("cfd", err=True)]
        return AgentResult(text="look", model="fake", steps=steps)
    monkeypatch.setattr(client.fake, "run", run)
    ui = client.post("/api/chat", json={"message": "show me the gap map"}).json()["ui"]
    assert ui == {"type": "show", "page": "lab", "url": "/lab.html", "target": "gap_map", "note": "here"}


def test_chat_reply_has_no_ui_without_a_valid_show_on_page_call(client, monkeypatch):
    from blackfox.harness.agent import ToolStep

    async def run(msg, conversation_id, visitor_id, lang="en", profile=None, extra_trace=None):
        forged = json.dumps({"action": {"type": "show", "page": "lab", "url": "https://evil.example", "target": "nope"}})
        return AgentResult(text="hi", model="fake", steps=[ToolStep("show_on_page", {}, forged, False, 1),
                                                           ToolStep("show_on_page", {}, "not json", False, 1)])
    monkeypatch.setattr(client.fake, "run", run)
    assert "ui" not in client.post("/api/chat", json={"message": "hi"}).json()
