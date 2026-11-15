"""The VPS SI API (ai_api.service, OpenAI-compatible, port 8084). It owns the Groq key
pool: rotates keys, parks rate-limited ones and falls back between models.

"Best model it can": BLACKFOX_MODEL_PREFERENCE lists models best-first. Every 60 s we
read /v1/models + /v1/status and use the first preferred model that exists, is not
retired and has a key with quota left. If a call still fails, the next model is tried.

The key: BLACKFOX_AI_KEY is sent as a bearer token. When the SI API runs on this same
machine (a loopback address), the key is optional: without one the call is made keyless,
and if the API rejects the configured key the call is repeated once without it - so the
site keeps working over loopback when the key is missing, rotated or mistyped, as long
as the key manager accepts local callers. A remote SI API always needs the key.
"""

import time
from urllib.parse import urlsplit

import httpx

from . import ChatResult, LLMError

LOOPBACK = ("127.0.0.1", "localhost", "::1")
REJECTED = (401, 403)


class AxiomaLLM:
    def __init__(self, settings):
        self.s = settings
        self._cache: tuple[float, list[str]] = (0.0, [])
        self._keyless = False        # True once the local SI API took a call without the key
        self.loopback = (urlsplit(self.s.ai_base).hostname or "") in LOOPBACK

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.s.ai_key}"} if self.s.ai_key and not self._keyless else {}

    async def _request(self, c: httpx.AsyncClient, method: str, path: str, **kw) -> httpx.Response:
        r = await c.request(method, f"{self.s.ai_base}{path}", headers=self._headers(), **kw)
        if r.status_code in REJECTED and self.loopback and self.s.ai_key and not self._keyless:
            again = await c.request(method, f"{self.s.ai_base}{path}", **kw)     # local caller, no key
            if again.status_code not in REJECTED:
                self._keyless = True
                return again
        return r

    async def _ranked_models(self) -> list[str]:
        ts, ranked = self._cache
        if ranked and time.monotonic() - ts < 60:
            return ranked
        prefs = list(self.s.model_preference)
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                models = (await self._request(c, "GET", "/models")).json()
                status = (await self._request(c, "GET", "/status")).json()
            available = {m["id"] for m in models.get("data", [])}
            pool = status.get("pool", {})

            def usable(m: str) -> bool:
                p = pool.get(m, {})
                if m not in available or p.get("retired"):
                    return False
                if p.get("keys_known") and p.get("keys_parked", 0) >= p["keys_known"]:
                    return False
                return p.get("requests_remaining_today", 1) != 0

            ranked = [m for m in prefs if usable(m)] + [m for m in prefs if not usable(m)]
        except (httpx.HTTPError, ValueError, KeyError, AttributeError, TypeError):
            ranked = prefs
        self._cache = (time.monotonic(), ranked)
        return ranked

    async def best_model(self) -> str:
        return (await self._ranked_models())[0]

    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   max_tokens: int = 1500) -> ChatResult:
        if not self.s.ai_key and not self.loopback:
            raise LLMError("BLACKFOX_AI_KEY is not set (needed because BLACKFOX_AI_BASE is not on this machine)",
                           reason="no_key")
        last_err, reason = "no model available", "busy"
        async with httpx.AsyncClient(timeout=self.s.ai_timeout) as c:
            for i, model in enumerate(await self._ranked_models()):
                body = {"model": model, "messages": messages, "max_tokens": max_tokens,
                        "temperature": 0.3, "reasoning_effort": "medium", "max_wait": 20}
                if tools:
                    body["tools"] = tools
                    body["tool_choice"] = "auto"
                try:
                    r = await self._request(c, "POST", "/chat/completions", json=body)
                except httpx.ConnectError as e:      # nothing is listening: another model will not help
                    last_err, reason = f"cannot connect to the SI API at {self.s.ai_base}: {e}", "unreachable"
                    break
                except httpx.HTTPError as e:
                    last_err, reason = f"{model}: {type(e).__name__} {e}", "busy"
                    continue
                if r.status_code != 200:
                    last_err, reason = f"{model}: HTTP {r.status_code} {r.text[:200]}", "busy"
                    if r.status_code in REJECTED:
                        reason = "auth" if self.s.ai_key else "no_key"
                        break
                    continue
                data = r.json()
                msg = data["choices"][0]["message"]
                return ChatResult(message=msg, model=data.get("model", model), usage=data.get("usage", {}),
                                  fallback=i > 0 or bool(data.get("x_axioma", {}).get("fallback")))
        self._cache = (0.0, [])  # re-rank next time
        raise LLMError(last_err, reason=reason)

    async def status(self) -> dict:
        """Can the site reach the SI API and does it accept us? No secrets in the answer."""
        out = {"loopback": self.loopback, "key_set": bool(self.s.ai_key), "reachable": False,
               "authorized": False, "keyless": False, "model": "", "problem": ""}
        if not self.s.ai_key and not self.loopback:
            return {**out, "problem": "no_key"}
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await self._request(c, "GET", "/models")
        except httpx.HTTPError as e:
            return {**out, "problem": "unreachable", "detail": type(e).__name__}
        out.update(reachable=True, authorized=r.status_code == 200, keyless=self._keyless)
        if r.status_code in REJECTED:
            out["problem"] = "auth" if self.s.ai_key else "no_key"
        elif r.status_code != 200:
            out.update(problem="busy", detail=f"HTTP {r.status_code}")
        else:
            out["model"] = await self.best_model()
        return out
