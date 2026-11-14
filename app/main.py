"""Black Fox - backend HTTP layer (FastAPI).

This file is the *contract* between the two halves of the project:

  frontend/   static HTML/CSS/JS, owned by design. Served as-is at "/".
  app/ + blackfox/   the JSON API under /api/*, owned by backend.

The JSON shapes are documented in docs/API.md - change both together.

Run locally:  uvicorn app.main:app --reload     -> http://127.0.0.1:8000
"""

import secrets
import subprocess
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from blackfox.design import get_store as get_designs
from blackfox.design import load_or_new, report, run_command
from blackfox.db import get_store as get_research_store
from blackfox.harness import get_agent
from blackfox.memory import get_memory
from blackfox.physics import fire

from .render import render_answer
from .research import router as research_router

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
MAX_MESSAGE = 1200
ASKS_PER_MINUTE = 6
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
_recent: dict[str, deque] = defaultdict(deque)


@app.on_event("startup")
def _warm() -> None:
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


def _error(code: str, status: int, vid: str, cid: str) -> JSONResponse:
    return _with_ids(JSONResponse({"error": code}, status_code=status), vid, cid)


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
    location: Literal["avionics_rack", "cable_standoff", "crew_quarters", "galley", "stowage", "glovebox"] = "avionics_rack"
    pressure_kpa: float | None = Field(None, ge=20, le=110)
    o2_pct: float | None = Field(None, ge=15, le=50)
    temp_c: float | None = Field(None, ge=5, le=45)
    vent_cm_s: float = Field(12.0, ge=0, le=40)
    auto_vent_shutdown: bool = True
    suppression: Literal["none", "co2", "water_mist"] = "co2"
    response_s: float = Field(60.0, ge=0, le=300)


class ChatIn(BaseModel):
    message: str = Field("", max_length=MAX_MESSAGE * 2)
    lang: Literal["hu", "en"] = "en"
    context: FireIn | None = None          # the scenario open in the fire lab, if any


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "blackfox", "commit": COMMIT}


@app.get("/api/session")
async def session(request: Request):
    vid, cid = _ids(request)
    mem = get_memory()
    body = {"messages": [_message(m) for m in mem.history(cid, limit=40)],
            "notes": [{"id": n["id"], "text": n["text"]} for n in mem.recall(vid, limit=50)],
            "max_message": MAX_MESSAGE}
    return _with_ids(JSONResponse(body), vid, cid)


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
    if body.context is not None:
        profile["fire_scenario"] = _fire_summary(body.context)
    res = await get_agent().run(msg, conversation_id=cid, visitor_id=vid, lang=body.lang,
                                profile=profile, extra_trace=snapshot)
    if not res.text:
        return _error("unavailable", 503, vid, cid)
    saved = mem.history(cid, limit=1)
    answer = _message(saved[-1]) if saved and saved[-1]["role"] == "assistant" else \
        _message({"role": "assistant", "content": res.text, "model": res.model, "trace": []})
    notes = [{"id": n["id"], "text": n["text"]} for n in get_memory().recall(vid, limit=50)]
    return _with_ids(JSONResponse({"message": answer, "notes": notes}), vid, cid)


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
    get_memory().forget(vid)
    get_memory().clear_conversation(cid)
    return _with_ids(JSONResponse({"ok": True}), vid, secrets.token_urlsafe(18))


# ---- fire-safety lab --------------------------------------------------------------
@app.get("/api/fire/catalog")
async def fire_catalog():
    return fire.catalog()


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
    from flame.data import get_envelopes, get_habitats, get_incidents, get_investigations
    names = {i.accession: i.acronym for i in get_investigations()}
    dump = lambda rows: [r.model_dump(by_alias=True) for r in rows]
    envelopes = dump(get_envelopes())
    for e in envelopes:
        e["acronym"] = names.get(e["accession"], e["accession"])
    return {"envelopes": envelopes, "habitats": dump(get_habitats()), "incidents": dump(get_incidents()),
            "investigations": len(names)}


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


# ---- the frontend (everything that isn't /api) -------------------------------------
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
