"""Black Fox Hackathon - server-side rendered website (FastAPI + Jinja2).

Pages: /  /ask (AI agent)  /research  /research/{slug}  /mars  /healthz
The website is only the front end: the research database, memory, MCP tools and
agent harness live in the `blackfox` package and are swappable via settings.

Run locally:  uvicorn app.main:app --reload
"""

import secrets
import subprocess
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from starlette.exceptions import HTTPException as StarletteHTTPException

from blackfox.db import KINDS, get_store
from blackfox.harness import get_agent
from blackfox.memory import get_memory

from .i18n import LANGS, TEXT, pick_lang
from .render import render_answer

BASE = Path(__file__).resolve().parent
MAX_QUESTION = 1200
ASKS_PER_MINUTE = 6
REPO_URL = "https://github.com/HAILVince/nasa_space_apps_2026"
VID, CID = "bfx_vid", "bfx_cid"
COOKIE_AGE = 60 * 86400


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE.parent,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


COMMIT = _commit()
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.filters["md"] = lambda s: Markup(render_answer(s or ""))
_recent_asks: dict[str, deque] = defaultdict(deque)


@app.on_event("startup")
def _warm() -> None:
    get_store()   # create + seed the database
    get_memory()


def _ids(request: Request) -> tuple[str, str, bool]:
    vid, cid = request.cookies.get(VID, ""), request.cookies.get(CID, "")
    fresh = False
    if len(vid) < 16:
        vid, fresh = secrets.token_urlsafe(18), True
    if len(cid) < 16:
        cid, fresh = secrets.token_urlsafe(18), True
    return vid, cid, fresh


def _set_ids(resp, vid: str, cid: str) -> None:
    for k, v in ((VID, vid), (CID, cid)):
        resp.set_cookie(k, v, max_age=COOKIE_AGE, samesite="lax", httponly=True)


def _ctx(request: Request, **extra) -> dict:
    lang = pick_lang(request.headers.get("host", ""), request.query_params.get("lang"),
                     request.cookies.get("lang"))
    return {"request": request, "lang": lang, "t": TEXT[lang], "repo_url": REPO_URL,
            "commit": COMMIT, "year": time.strftime("%Y"), **extra}


def _render(name: str, ctx: dict, status: int = 200) -> HTMLResponse:
    resp = templates.TemplateResponse(ctx["request"], name, ctx, status_code=status)
    q = ctx["request"].query_params.get("lang")
    if q in LANGS:
        resp.set_cookie("lang", q, max_age=365 * 86400, samesite="lax", httponly=True)
    return resp


def _rate_limited(ip: str) -> bool:
    now, q = time.monotonic(), _recent_asks[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= ASKS_PER_MINUTE:
        return True
    q.append(now)
    return False


# ---- pages ------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    store = get_store()
    featured = [r for r in (store.get(s) for s in ("cool-flames", "saffire", "zero-gravity-research-facility"))
                if r]
    return _render("index.html", _ctx(request, page="home", stats=store.stats(), featured=featured))


@app.get("/mars", response_class=HTMLResponse)
async def mars(request: Request):
    return _render("mars.html", _ctx(request, page="mars"))


@app.get("/research", response_class=HTMLResponse)
async def research(request: Request, q: str = "", kind: str = ""):
    store = get_store()
    kind = kind if kind in KINDS else ""
    rows = store.search(q[:200], kind=kind or None, limit=25) if q.strip() else store.list(kind=kind or None)
    return _render("research.html", _ctx(request, page="research", rows=rows, q=q, kind=kind, kinds=KINDS,
                                         stats=store.stats()))


@app.get("/research/{slug}", response_class=HTMLResponse)
async def research_record(request: Request, slug: str):
    rec = get_store().get(slug)
    if not rec:
        raise StarletteHTTPException(404)
    return _render("record.html", _ctx(request, page="research", rec=rec))


# ---- the agent --------------------------------------------------------------
@app.get("/ask", response_class=HTMLResponse)
async def ask_page(request: Request, err: str = "", q: str = ""):
    vid, cid, fresh = _ids(request)
    ctx = _ctx(request, page="ask", history=get_memory().history(cid, limit=40),
               notes=get_memory().recall(vid, limit=50), prefill=q[:300], error="")
    t = ctx["t"]
    ctx["error"] = {"rate": t["ask_rate"], "unavailable": t["ask_unavailable"], "empty": t["ask_empty"],
                    "long": t["ask_too_long"].format(n=MAX_QUESTION)}.get(err, "")
    resp = _render("ask.html", ctx)
    if fresh:
        _set_ids(resp, vid, cid)
    return resp


@app.post("/ask")
async def ask_post(request: Request, question: str = Form("")):
    vid, cid, _ = _ids(request)
    lang = _ctx(request)["lang"]
    q = question.strip()
    ip = request.client.host if request.client else "?"
    err = ""
    if not q:
        err = "empty"
    elif len(q) > MAX_QUESTION:
        err = "long"
    elif _rate_limited(ip):
        err = "rate"
    else:
        res = await get_agent().run(q, conversation_id=cid, visitor_id=vid, lang=lang)
        if not res.text:
            err = "unavailable"
    resp = RedirectResponse(f"/ask?err={err}#latest" if err else "/ask#latest", status_code=303)
    _set_ids(resp, vid, cid)
    return resp


@app.post("/ask/new")
async def ask_new(request: Request):
    vid, _, _ = _ids(request)
    resp = RedirectResponse("/ask", status_code=303)
    _set_ids(resp, vid, secrets.token_urlsafe(18))
    return resp


@app.post("/ask/forget")
async def ask_forget(request: Request):
    vid, cid, _ = _ids(request)
    get_memory().forget(vid)
    get_memory().clear_conversation(cid)
    resp = RedirectResponse("/ask", status_code=303)
    _set_ids(resp, vid, secrets.token_urlsafe(18))
    return resp


# ---- misc -------------------------------------------------------------------
@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True, "site": "blackfoxhackathon", "commit": COMMIT,
                         "records": get_store().stats()["records"]})


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    return HTMLResponse("User-agent: *\nDisallow: /ask\n", media_type="text/plain")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse("/static/fox.svg", status_code=301)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return _render("404.html", _ctx(request, page=""), status=404)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
