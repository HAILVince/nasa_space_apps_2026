"""The VPS AI API (ai_api.service, OpenAI-compatible, port 8084). It owns the Groq key
pool: rotates keys, parks rate-limited ones and falls back between models.

"Best model it can": BLACKFOX_MODEL_PREFERENCE lists models best-first. Every 60 s we
read /v1/models + /v1/status and use the first preferred model that exists, is not
retired and has a key with quota left. If a call still fails, the next model is tried.
"""

import time

import httpx

from . import ChatResult, LLMError


class AxiomaLLM:
    def __init__(self, settings):
        self.s = settings
        self._cache: tuple[float, list[str]] = (0.0, [])

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.s.ai_key}"}

    async def _ranked_models(self) -> list[str]:
        ts, ranked = self._cache
        if ranked and time.monotonic() - ts < 60:
            return ranked
        prefs = list(self.s.model_preference)
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                models = (await c.get(f"{self.s.ai_base}/models", headers=self._headers())).json()
                status = (await c.get(f"{self.s.ai_base}/status", headers=self._headers())).json()
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
        except (httpx.HTTPError, ValueError, KeyError):
            ranked = prefs
        self._cache = (time.monotonic(), ranked)
        return ranked

    async def best_model(self) -> str:
        return (await self._ranked_models())[0]

    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   max_tokens: int = 1500) -> ChatResult:
        if not self.s.ai_key:
            raise LLMError("BLACKFOX_AI_KEY is not set")
        last_err = "no model available"
        async with httpx.AsyncClient(timeout=self.s.ai_timeout) as c:
            for i, model in enumerate(await self._ranked_models()):
                body = {"model": model, "messages": messages, "max_tokens": max_tokens,
                        "temperature": 0.3, "reasoning_effort": "medium", "max_wait": 20}
                if tools:
                    body["tools"] = tools
                    body["tool_choice"] = "auto"
                try:
                    r = await c.post(f"{self.s.ai_base}/chat/completions", json=body, headers=self._headers())
                except httpx.HTTPError as e:
                    last_err = f"{model}: {e}"
                    continue
                if r.status_code != 200:
                    last_err = f"{model}: HTTP {r.status_code} {r.text[:200]}"
                    if r.status_code in (401, 403):
                        break
                    continue
                data = r.json()
                msg = data["choices"][0]["message"]
                return ChatResult(message=msg, model=data.get("model", model), usage=data.get("usage", {}),
                                  fallback=i > 0 or bool(data.get("x_axioma", {}).get("fallback")))
        self._cache = (0.0, [])  # re-rank next time
        raise LLMError(last_err)
