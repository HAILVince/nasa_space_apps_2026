"""Black Fox - backend HTTP layer (FastAPI).

This file is the *contract* between the two halves of the project:

  frontend/   static HTML/CSS/JS, owned by design. Served as-is at "/".
  app/ + blackfox/   the JSON API under /api/*, owned by backend.

The JSON shapes are documented in docs/API.md - change both together.

Run locally:  uvicorn app.main:app --reload     -> http://127.0.0.1:8000
"""

import json
import logging
import secrets
import subprocess
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from blackfox.design import get_store as get_designs
from blackfox.design import load_or_new, report, run_command
from blackfox.db import get_store as get_research_store
from blackfox.harness import get_agent
from blackfox.llm import get_llm
from blackfox.memory import get_memory
from blackfox.physics import fire
from blackfox.physics import scenario as fire_scenario
from blackfox.physics.runs import get_runs
from blackfox.tools.ui_tools import TARGETS as UI_TARGETS
from flame import calc as flame_calc
from flame import sweep as flame_sweep
from blackfox.settings import get_settings

from .render import render_answer
from .static import CompressedStaticFiles
from .flame_routes import router as flame_router
from .research import router as research_router

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
FRONTEND_FILES = CompressedStaticFiles(directory=FRONTEND, html=True)   # gzip once, revalidate with ETag
MAX_MESSAGE = 1200
ASKS_PER_MINUTE = get_settings().asks_per_minute     # AI messages per minute per IP (BLACKFOX_ASKS_PER_MINUTE)
log = logging.getLogger("uvicorn.error")                # ends up in journalctl -u blackfox
VID, CID = "bfx_vid", "bfx_cid"          # visitor id (long-term memory), conversation id
COOKIE_AGE = 60 * 86400


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


COMMIT = _commit()
app = FastAPI(title="Black Fox API", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(research_router)
app.include_router(flame_router)
_recent: dict[str, deque] = defaultdict(deque)


@app.on_event("startup")
def _warm() -> None:
    # compress the frontend's text files and the 3D model once, off the request path
    threading.Thread(target=FRONTEND_FILES.warm, name="gzip-warm", daemon=True).start()
    get_memory()
    from blackfox.db.vector_store import warm_vectors
    warm_vectors()


# ---- helpers ----------------------------------------------------------------
def _ids(request: Request) -> tuple[str, str]:
    vid, cid = request.cookies.get(VID, ""), request.cookies.get(CID, "")
    if len(vid) < 16:
        vid = secrets.token_urlsafe(18)
    if len(cid) < 16:
        cid = secrets.token_urlsafe(18)
    return vid, cid


def _with_ids(resp: JSONResponse, vid: str, cid: str) -> JSONResponse:
    for k, v in ((VID, vid), (CID, cid)):
        resp.set_cookie(k, v, max_age=COOKIE_AGE, samesite="lax", httponly=True)
    return resp


def _error(code: str, status: int, vid: str, cid: str, **extra) -> JSONResponse:
    return _with_ids(JSONResponse({"error": code, **extra}, status_code=status), vid, cid)


def _rate_limited(ip: str) -> bool:
    now, q = time.monotonic(), _recent[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= ASKS_PER_MINUTE:
        return True
    q.append(now)
    return False


def _message(m: dict) -> dict:
    """One chat message as the frontend sees it: text, html and (if the design changed in
    that turn) the plain-text simulation snapshot."""
    out = {"role": m["role"], "text": m["content"]}
    if m["role"] == "assistant":
        trace = m.get("trace") or []
        snap = next((s.get("text", "") for s in trace if s.get("name") == SNAPSHOT), "")
        out["html"] = render_answer(m["content"]) if m["content"] else ""
        out["snapshot"] = snap
        out["model"] = m.get("model") or ""
        out["tools"] = [{"name": s.get("name", ""), "ms": s.get("ms", 0), "error": bool(s.get("is_error"))}
                        for s in trace if s.get("name") != SNAPSHOT]
    return out


SNAPSHOT = "_snapshot"


# ---- API ----------------------------------------------------------------------
class FireIn(BaseModel):
    """one fire-safety scenario; omitted atmosphere values use the environment's defaults"""
    model_config = ConfigDict(extra="forbid")
    environment: Literal["leo", "lunar_orbit", "moon", "mars", "earth"] = "leo"
    material: str | None = Field(None, max_length=40)
    location: Literal["avionics_rack", "crew_quarters", "galley", "glovebox"] = "avionics_rack"
    pressure_kpa: float | None = Field(None, ge=20, le=110)
    o2_pct: float | None = Field(None, ge=15, le=50)
    temp_c: float | None = Field(None, ge=5, le=45)
    vent_cm_s: float = Field(12.0, ge=0, le=40)
    auto_vent_shutdown: bool = True
    suppression: Literal["none", "co2", "water_mist", "k_aerosol", "clean_agent", "inert_n2"] = "co2"
    response_s: float = Field(60.0, ge=0, le=300)


class DeviceIn(BaseModel):
    """what the browser reported about the machine a run was made on (all optional, size-capped)"""
    model_config = ConfigDict(extra="ignore")
    tier: Literal["low", "medium", "high"] = "medium"
    chosen: Literal["auto", "low", "medium", "high"] = "auto"
    cores: int | None = Field(None, ge=0, le=1024)
    memory_gb: float | None = Field(None, ge=0, le=4096)
    mobile: bool = False
    gpu: str = Field("", max_length=80)
    dpr: float | None = Field(None, ge=0, le=10)
    cpu_ms: float | None = Field(None, ge=0, le=1e6)
    view3d: bool = False


class StartIn(BaseModel):
    """the main simulator's Start: the scenario both models run, the 2D wall lining, the device"""
    model_config = ConfigDict(extra="forbid")
    scenario: FireIn
    lining: Literal["sibal", "pmma", "paper", "nomex"] = "sibal"
    device: DeviceIn = Field(default_factory=DeviceIn)


class RoomOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    room: str = Field(max_length=16)
    fire_s: float | None = Field(None, ge=0, le=1e5)
    smoke_s: float | None = Field(None, ge=0, le=1e5)
    max_gas_c: float | None = Field(None, ge=-300, le=5000)
    min_o2_pct: float | None = Field(None, ge=0, le=100)


class SpreadIn(BaseModel):
    """the 2D fire-spread model's outcome, reported by the browser that ran it"""
    model_config = ConfigDict(extra="ignore")
    run_id: int = Field(ge=1)
    status: Literal["running", "burnt_out", "went_out", "did_not_ignite", "time_limit", "not_started"]
    sim_time_s: float = Field(ge=0, le=1e5)
    extinction_cause: Literal["oxygen", "quenching", "blowoff"] | None = None
    lining: str = Field("", max_length=16)
    rooms_reached: int = Field(0, ge=0, le=32)
    first_alarm_s: float | None = Field(None, ge=0, le=1e5)
    area_burning_cm2: float = Field(0, ge=0, le=1e8)
    area_burned_cm2: float = Field(0, ge=0, le=1e8)
    hottest_gas_c: float | None = Field(None, ge=-300, le=5000)
    lowest_o2_pct: float | None = Field(None, ge=0, le=100)
    vent_off_s: float | None = Field(None, ge=0, le=1e5)
    ignitions: int = Field(0, ge=0, le=10000)
    doors_closed: list[str] = Field(default_factory=list, max_length=16)
    rooms: list[RoomOut] = Field(default_factory=list, max_length=16)


class CfdRoom(BaseModel):
    model_config = ConfigDict(extra="ignore")
    room: str = Field(max_length=16)
    fire_s: float | None = Field(None, ge=0, le=1e5)
    smoke_s: float | None = Field(None, ge=0, le=1e5)
    max_gas_c: float | None = Field(None, ge=-300, le=5000)
    min_o2_pct: float | None = Field(None, ge=0, le=100)
    min_visibility_m: float | None = Field(None, ge=0, le=1000)


class CfdGrid(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dim: int = Field(3, ge=2, le=3)
    h: float = Field(gt=0, le=5)
    nx: int | None = Field(None, ge=1, le=10000)
    ny: int | None = Field(None, ge=1, le=10000)
    nz: int | None = Field(None, ge=1, le=10000)


class OutcomeIn(BaseModel):
    """a CFD model's result for a run, reported by the browser that ran it (the grid is part of it:
    a finer grid gives more accurate numbers)"""
    model_config = ConfigDict(extra="ignore")
    run_id: int = Field(ge=1)
    model: Literal["cfd_habitat", "cfd_spacecraft", "cfd_living"]
    status: Literal["running", "burnt_out", "went_out", "did_not_ignite", "time_limit"]
    sim_time_s: float = Field(ge=0, le=1e5)
    grid: CfdGrid
    tier: Literal["low", "medium", "high"] = "medium"
    ignition: str | None = Field(None, max_length=60)
    extinction_cause: str | None = Field(None, max_length=24)
    vent_off_s: float | None = Field(None, ge=0, le=1e5)
    peak_hrr_kw: float | None = Field(None, ge=0, le=1e7)
    rooms: list[CfdRoom] = Field(default_factory=list, max_length=24)


class ChatIn(BaseModel):
    message: str = Field("", max_length=MAX_MESSAGE * 2)
    lang: Literal["hu", "en"] = "en"
    context: FireIn | None = None          # the scenario open in the fire lab, if any


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "blackfox", "commit": COMMIT}


_ai_status: tuple[float, dict] = (0.0, {})


@app.get("/api/ai/status")
async def ai_status():
    """Is the AI behind the chat working? Checked at most every 15 s; never shows the key."""
    global _ai_status
    at, cached = _ai_status
    if cached and time.monotonic() - at < 15:
        return cached
    check = getattr(get_llm(), "status", None)
    body = await check() if check else {"problem": ""}
    body = {"ok": not body.get("problem"), **body}
    _ai_status = (time.monotonic(), body)
    return body


@app.get("/api/session")
async def session(request: Request):
    vid, cid = _ids(request)
    mem = get_memory()
    body = {"messages": [_message(m) for m in mem.history(cid, limit=40)],
            "notes": [{"id": n["id"], "text": n["text"]} for n in mem.recall(vid, limit=50)],
            "max_message": MAX_MESSAGE}
    return _with_ids(JSONResponse(body), vid, cid)


def _ui_action(steps) -> dict | None:
    """The last successful show_on_page call of an answer, as the action the browser carries out."""
    for step in reversed(steps or []):
        if step.name != "show_on_page" or step.is_error:
            continue
        try:
            action = json.loads(step.result).get("action")
        except (ValueError, AttributeError):
            continue
        if isinstance(action, dict) and action.get("target") in UI_TARGETS:
            return {k: action[k] for k in ("type", "page", "url", "target", "note") if k in action}
    return None


@app.post("/api/chat")
async def chat(request: Request, body: ChatIn):
    vid, cid = _ids(request)
    msg = body.message.strip()
    if not msg:
        return _error("empty", 400, vid, cid)
    if len(msg) > MAX_MESSAGE:
        return _error("too_long", 400, vid, cid)
    mem = get_memory()
    snap = run_command(vid, msg)              # typed commands: instant, no LLM, no rate limit
    if snap is not None:
        mem.append(cid, vid, "user", msg)
        note = snap if snap.startswith("error:") else f"(command applied: {msg})"
        trace = [] if snap.startswith("error:") else [{"name": SNAPSHOT, "text": snap}]
        mem.append(cid, vid, "assistant", note, trace=trace, model="command")
        answer = _message({"role": "assistant", "content": note, "model": "command", "trace": trace})
        return _with_ids(JSONResponse({"message": answer}), vid, cid)
    if _rate_limited(request.client.host if request.client else "?"):
        return _error("rate_limited", 429, vid, cid)
    load_or_new(vid)
    _, before = get_designs().get(vid)

    def snapshot(_res) -> list[dict]:
        d, after = get_designs().get(vid)
        return [{"name": SNAPSHOT, "text": report(d)}] if d is not None and after != before else []

    profile = {"design": report(load_or_new(vid))}
    scenarios = fire_scenario.get_store()
    if body.context is not None:
        profile["fire_scenario"] = _fire_summary(body.context)
        scenarios.put(vid, body.context.model_dump())     # what the user has open is what the AI's tools edit
    scenario_before = scenarios.get(vid)
    res = await get_agent().run(msg, conversation_id=cid, visitor_id=vid, lang=body.lang,
                                profile=profile, extra_trace=snapshot)
    if not res.text:
        log.warning("AI answer failed (%s): %s", res.reason or "empty answer", res.error or "-")
        return _error("unavailable", 503, vid, cid, reason=res.reason or "busy")
    saved = mem.history(cid, limit=1)
    answer = _message(saved[-1]) if saved and saved[-1]["role"] == "assistant" else \
        _message({"role": "assistant", "content": res.text, "model": res.model, "trace": []})
    notes = [{"id": n["id"], "text": n["text"]} for n in get_memory().recall(vid, limit=50)]
    reply = {"message": answer, "notes": notes}
    scenario_after = scenarios.get(vid)
    if scenario_after != scenario_before:                  # the AI changed the lab: the page shows it
        reply["scenario"] = scenario_after
    ui = _ui_action(res.steps)
    if ui:                                                 # the AI pointed at a part of the page: the browser shows it
        reply["ui"] = ui
    return _with_ids(JSONResponse(reply), vid, cid)


@app.post("/api/session/new")
async def session_new(request: Request):
    vid, _ = _ids(request)
    return _with_ids(JSONResponse({"ok": True}), vid, secrets.token_urlsafe(18))


@app.get("/api/design")
async def design(request: Request):
    vid, cid = _ids(request)
    return _with_ids(JSONResponse({"snapshot": report(load_or_new(vid))}), vid, cid)


@app.post("/api/memory/forget")
async def memory_forget(request: Request):
    vid, cid = _ids(request)
    get_designs().delete(vid)
    get_runs().delete(vid)
    fire_scenario.get_store().delete(vid)
    get_memory().forget(vid)
    get_memory().clear_conversation(cid)
    return _with_ids(JSONResponse({"ok": True}), vid, secrets.token_urlsafe(18))


# ---- fire-safety lab --------------------------------------------------------------
@app.get("/api/fire/catalog")
async def fire_catalog():
    return fire.catalog()


# ---- the main simulator: Start, the 2D outcome, the visitor's runs -------------------------
@app.post("/api/sim/start")
async def sim_start(request: Request, body: StartIn):
    """Runs the cabin model and saves the run's starting parameters for this visitor's session."""
    vid, cid = _ids(request)
    sc = body.scenario.model_dump()
    if sc["material"] is not None and sc["material"] not in fire.MATERIALS:
        raise HTTPException(400, "unknown material")
    try:
        result = fire.simulate(**sc)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    settings = {**fire_scenario.effective(sc), "lining": body.lining}
    run_id = get_runs().add(vid, settings, fire_scenario.brief(result), body.device.model_dump())
    fire_scenario.get_store().put(vid, sc)            # the AI's scenario tools see what was started
    return _with_ids(JSONResponse({"run_id": run_id, "result": result}), vid, cid)


@app.post("/api/sim/spread")
async def sim_spread(request: Request, body: SpreadIn):
    vid, cid = _ids(request)
    data = body.model_dump()
    run_id = data.pop("run_id")
    if not get_runs().set_spread(vid, run_id, data):
        raise HTTPException(404, "no such run for this visitor")
    return _with_ids(JSONResponse({"ok": True}), vid, cid)


@app.post("/api/sim/outcome")
async def sim_outcome(request: Request, body: OutcomeIn):
    vid, cid = _ids(request)
    data = body.model_dump()
    run_id, model = data.pop("run_id"), data.pop("model")
    if not get_runs().set_outcome(vid, run_id, model, data):
        raise HTTPException(404, "no such run for this visitor")
    return _with_ids(JSONResponse({"ok": True}), vid, cid)


@app.get("/api/sim/runs")
async def sim_runs(request: Request, limit: int = 5):
    vid, cid = _ids(request)
    return _with_ids(JSONResponse({"runs": get_runs().latest(vid, limit)}), vid, cid)


@app.post("/api/fire/simulate")
async def fire_simulate(body: FireIn):
    if body.material is not None and body.material not in fire.MATERIALS:
        raise HTTPException(400, "unknown material")
    try:
        return fire.simulate(**body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/fire/evidence")
async def fire_evidence(environment: str = "leo", material: str = "nomex"):
    return {"records": fire.evidence(environment, material, get_research_store())}


def _fire_summary(ctx: FireIn) -> str:
    try:
        r = fire.simulate(**ctx.model_dump())
    except ValueError:
        return ""
    f, tl = r["flammability"], r["timeline"]
    i = r["inputs"]
    return (f"environment={i['environment']} location={i['location']} material={i['material']} "
            f"P={i['pressure_kpa']:.1f} kPa O2={i['o2_pct']:.1f}% T={i['temp_c']:.0f} C vent={i['vent_cm_s']:.0f} cm/s; "
            f"MOC_1g={f['moc_1g']:.1f}% MOC_eff={f['moc_eff']:.1f}% margin={f['margin_pct']:+.1f}% "
            f"spread={r['flame']['spread_cm_s']:.2f} cm/s peak HRR={r['peaks']['hrr_kw']:.2f} kW "
            f"alarm={tl['alarm_s']} s extinguished={tl['extinguished_s']} s risk={r['verdict']['level']}")


@app.get("/api/flame/context")
async def flame_context():
    """The Flame in Freefall dataset (flame/data): which atmospheres NASA's PSI combustion
    experiments covered, the planned habitats and the historic cabin incidents."""
    from flame.data import get_envelopes, get_habitats, get_incidents, get_investigations, get_insights
    invs = get_investigations()
    names = {i.accession: i.acronym for i in invs}
    dump = lambda rows: [r.model_dump(by_alias=True) for r in rows]
    envelopes = dump(get_envelopes())
    for e in envelopes:
        e["acronym"] = names.get(e["accession"], e["accession"])
    habitats = get_habitats()
    insights = {h.id: dump(get_insights(h.id)) for h in habitats}
    return {"envelopes": envelopes, "habitats": dump(habitats), "incidents": dump(get_incidents()), "insights": insights,
            "investigationCount": len(invs),
            # NASA's own "Earth benefits" text per PSI investigation, passed through unmodified
            "investigations": [i.model_dump(by_alias=True, include={"accession", "acronym", "title", "fuel_phase", "earth_benefits", "psi_url"})
                               for i in invs]}


_GRAVITIES = Literal["micro", "lunar", "martian", "earth"]


@app.get("/api/flame/materials")
async def flame_materials():
    """Materials with measured limits in flame/data/material_limits.json."""
    return {"materials": flame_calc.known_materials()}


@app.get("/api/flame/check")
async def flame_check(material_id: str, o2_pct: float = Query(ge=0, le=100),
                      pressure_kpa: float = Query(gt=0, le=200), gravity: _GRAVITIES = "earth"):
    """Cabin atmosphere vs the measured limit of one material (flame.calc.material_check)."""
    if material_id not in flame_calc.known_materials():
        raise HTTPException(404, "unknown material")
    return flame_calc.material_check(material_id, o2_pct, pressure_kpa, gravity)


@app.get("/api/flame/coverage")
async def flame_coverage(o2_pct: float = Query(ge=0, le=100), pressure_kpa: float = Query(gt=0, le=200),
                         fuel_phase: str | None = None):
    """Which PSI experiment envelopes cover this atmosphere (flame.calc.coverage)."""
    return flame_calc.coverage(o2_pct, pressure_kpa, fuel_phase)


@app.get("/api/flame/tests")
async def flame_tests(o2_pct: float = Query(ge=0, le=100), pressure_kpa: float = Query(gt=0, le=600),
                      fuel_phase: Literal["solid", "liquid", "gas", "aerosol"] | None = None,
                      limit: int = Query(5, ge=1, le=25)):
    """Real PSI test runs closest to this atmosphere (flame.calc.nearest_tests)."""
    return flame_calc.nearest_tests(o2_pct, pressure_kpa, fuel_phase, None, limit)


@app.get("/api/flame/sweep")
async def flame_sweep_route(accession: str = Query(max_length=16)):
    """Every configuration one PSI investigation tested (flame.sweep.sweep), grouped from the cleaned tables."""
    out = flame_sweep.sweep(accession)
    if out is None:
        raise HTTPException(404, "unknown investigation")
    return out


# ---- research records (the evidence drawer) ---------------------------------------------
@app.get("/api/research")
async def research_index(gravity: str | None = None, topic: str | None = None):
    return {"records": get_research_store().list(gravity=gravity, topic=topic, limit=100)}


@app.get("/api/research/{slug}")
async def research_record(slug: str):
    record = get_research_store().get(slug)
    if record is None or "error" in record:
        raise HTTPException(404, "Unknown research record")
    return record


@app.get("/healthz", include_in_schema=False)   # used by the VPS deploy script
async def healthz():
    return {"ok": True, "site": "blackfox", "commit": COMMIT}


# ---- the 2D fire simulator: the teammate's Spacecraft Cabin Fire, 2D section ---------------
# A teammate maintains this page and uploads it on GitHub into the knowledge folder; it is
# served from there unchanged (only a "back to the simulator" bar is put above it), so each new
# upload is live after the next deploy. The simulator's "2D" tab and "How it works" open it.
# If the file is missing (renamed or being replaced), the site's own fire-spread page is shown.
FIRE_SIM = ROOT / "blackfox" / "db" / "knowledge" / "spacecraft_fire" / "fire_sim_ship" / "spacecraft_cabin_fire_2d.html"
FIRE_SIM_BAR = ('<nav style="font:600 13px/1 system-ui,sans-serif;padding:10px 16px;background:#0b0e12;'
                'border-bottom:1px solid #222a33"><a href="./lab.html" style="color:#e9ecef;text-decoration:none">'
                '&larr; Black Fox simulator</a></nav>')


# ?embed=1 is the simulator's "2D" tab: the page inside the lab, without the bar and its own title.
FIRE_SIM_EMBED = "<style>.wrap>header{display:none}.wrap{padding-top:8px}</style>"
FIRE_SIM_EMBED_JS = '\n<script src="./js/sim2d_embed.js"></script>\n'
# nginx sends X-Frame-Options: DENY for the whole site; a CSP frame-ancestors directive takes
# precedence over it in browsers, so this one page may be shown inside the site's own pages.
FIRE_SIM_HEADERS = {"Content-Security-Policy": "frame-ancestors 'self'"}


@app.get("/fire-sim", include_in_schema=False)
async def fire_sim(embed: int = 0):
    if not FIRE_SIM.is_file():
        return RedirectResponse("./spread.html", status_code=307)
    page = FIRE_SIM.read_text(encoding="utf-8")
    cut = page.find("</style>")                 # the page has no <body> tag: put the bar after its styles
    cut = cut + len("</style>") if cut >= 0 else 0
    if not embed:
        return HTMLResponse(page[:cut] + "\n" + FIRE_SIM_BAR + page[cut:], headers=FIRE_SIM_HEADERS)
    # in the tab: fire starts by itself at one spot, no manual ignition (frontend/js/sim2d_embed.js)
    return HTMLResponse(page[:cut] + "\n" + FIRE_SIM_EMBED + page[cut:] + FIRE_SIM_EMBED_JS, headers=FIRE_SIM_HEADERS)


# ---- the frontend (everything that isn't /api) -------------------------------------
app.mount("/", FRONTEND_FILES, name="frontend")

