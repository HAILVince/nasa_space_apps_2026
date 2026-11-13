"""Client for the VPS's AI API (ai_api.service on 127.0.0.1:8084).

That service owns the Groq key pool: it rotates keys, parks rate-limited
keys/models and falls back to another model, so this site only sends one
request and gets one answer.

Configured from the environment (/etc/blackfox.env on the VPS):
  BLACKFOX_AI_URL    default http://127.0.0.1:8084/v1/generate
  BLACKFOX_AI_KEY    key from automation/config.json -> ai_api.keys
  BLACKFOX_AI_MODEL  optional; empty = the API's default model
"""

import html
import os
import re

import httpx

AI_URL = os.environ.get("BLACKFOX_AI_URL", "http://127.0.0.1:8084/v1/generate")
AI_KEY = os.environ.get("BLACKFOX_AI_KEY", "")
AI_MODEL = os.environ.get("BLACKFOX_AI_MODEL", "")
TIMEOUT = float(os.environ.get("BLACKFOX_AI_TIMEOUT", "60"))


class AIUnavailable(Exception):
    pass


async def ask(question: str, system: str, max_tokens: int = 900) -> dict:
    if not AI_KEY:
        raise AIUnavailable("BLACKFOX_AI_KEY is not set")
    payload = {"prompt": question, "system": system, "max_tokens": max_tokens,
               "reasoning_effort": "low", "max_wait": 20}
    if AI_MODEL:
        payload["model"] = AI_MODEL
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(AI_URL, json=payload, headers={"X-API-Key": AI_KEY})
    except httpx.HTTPError as e:
        raise AIUnavailable(str(e)) from e
    if r.status_code != 200:
        raise AIUnavailable(f"HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    text = (data.get("text") or "").strip()
    if not text:
        raise AIUnavailable("empty answer")
    return {"text": text, "model": data.get("model", "")}


_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _inline(s: str) -> str:
    s = html.escape(s)
    s = _CODE.sub(r"<code>\1</code>", s)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _LINK.sub(r'<a href="\2" rel="nofollow noopener" target="_blank">\1</a>', s)
    return s


def render_answer(text: str) -> str:
    """Tiny, safe Markdown subset -> HTML: everything is escaped first, then
    paragraphs, bullet lists, **bold**, `code` and http(s) links."""
    out, items = [], []

    def flush_list():
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        para = []
        for ln in lines:
            if _BULLET.match(ln):
                if para:
                    out.append("<p>" + "<br>".join(para) + "</p>")
                    para = []
                items.append(_inline(_BULLET.sub("", ln, count=1)))
            else:
                flush_list()
                heading = ln.lstrip("#").strip() if ln.lstrip().startswith("#") else None
                if heading is not None:
                    out.append(f"<h3>{_inline(heading)}</h3>")
                else:
                    para.append(_inline(ln))
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
        flush_list()
    return "".join(out)
