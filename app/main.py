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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from blackfox.design import get_store as get_designs
from blackfox.design import load_or_new, report, run_command
from blackfox.harness import get_agent
from blackfox.memory import get_memory

from .render import render_answer

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
_recent: dict[str, deque] = defaultdict(deque)


@app.on_event("startup")
def _warm() -> None:
    get_memory()


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
class ChatIn(BaseModel):
    message: str = Field("", max_length=MAX_MESSAGE * 2)
    lang: Literal["hu", "en"] = "en"


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

    res = await get_agent().run(msg, conversation_id=cid, visitor_id=vid, lang=body.lang,
                                profile={"design": report(load_or_new(vid))}, extra_trace=snapshot)
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


@app.get("/healthz", include_in_schema=False)   # used by the VPS deploy script
async def healthz():
    return {"ok": True, "site": "blackfox", "commit": COMMIT}


# ---- the frontend (everything that isn't /api) -------------------------------------
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
