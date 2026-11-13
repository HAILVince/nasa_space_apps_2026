"""Black Fox Hackathon - server-side rendered website (FastAPI + Jinja2).

Run locally:  uvicorn app.main:app --reload
On the VPS it runs as blackfox.service behind nginx and is redeployed
automatically whenever this repository changes (see README.md).
"""

import os
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

from . import ai
from .i18n import LANGS, TEXT, pick_lang

BASE = Path(__file__).resolve().parent
MAX_QUESTION = 600
ASKS_PER_MINUTE = int(os.environ.get("BLACKFOX_ASKS_PER_MINUTE", "6"))
REPO_URL = "https://github.com/HAILVince/nasa_space_apps_2026"


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
_recent_asks: dict[str, deque] = defaultdict(deque)


def _ctx(request: Request, **extra) -> dict:
    lang = pick_lang(request.headers.get("host", ""), request.query_params.get("lang"),
                     request.cookies.get("lang"))
    return {"request": request, "lang": lang, "t": TEXT[lang], "repo_url": REPO_URL,
            "commit": COMMIT, "year": time.strftime("%Y"), **extra}


def _render(name: str, ctx: dict, status: int = 200) -> HTMLResponse:
    resp = templates.TemplateResponse(ctx["request"], name, ctx, status_code=status)
    q = ctx["request"].query_params.get("lang")
    if q in LANGS:
        resp.set_cookie("lang", q, max_age=365 * 86400, samesite="lax", secure=False, httponly=True)
    return resp


def _rate_limited(ip: str) -> bool:
    now, q = time.monotonic(), _recent_asks[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= ASKS_PER_MINUTE:
        return True
    q.append(now)
    return False


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _render("index.html", _ctx(request, page="home"))


@app.get("/ask", response_class=HTMLResponse)
async def ask_form(request: Request):
    return _render("ask.html", _ctx(request, page="ask", question="", answer=None, error=None))


@app.post("/ask", response_class=HTMLResponse)
async def ask_post(request: Request, question: str = Form("")):
    ctx = _ctx(request, page="ask", question=question, answer=None, error=None, model="")
    t = ctx["t"]
    q = question.strip()
    ip = request.client.host if request.client else "?"
    if not q:
        ctx["error"] = t["ask_empty"]
    elif len(q) > MAX_QUESTION:
        ctx["error"] = t["ask_too_long"].format(n=MAX_QUESTION)
    elif _rate_limited(ip):
        return _render("ask.html", {**ctx, "error": t["ask_rate"]}, status=429)
    else:
        try:
            res = await ai.ask(q, t["ai_system"])
            ctx["answer"] = Markup(ai.render_answer(res["text"]))
            ctx["model"] = res["model"]
        except ai.AIUnavailable:
            ctx["error"] = t["ask_unavailable"]
    return _render("ask.html", ctx)


@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True, "site": "blackfoxhackathon", "commit": COMMIT})


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
