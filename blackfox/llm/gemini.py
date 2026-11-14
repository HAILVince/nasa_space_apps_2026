"""Google Gemini through its OpenAI-compatible endpoint, so messages, tool schemas and
tool calls keep the same shape as every other backend. The key is read from
BLACKFOX_GEMINI_KEY (never commit it); models are tried in BLACKFOX_GEMINI_MODELS order."""

import httpx

from . import ChatResult, LLMError


class GeminiLLM:
    def __init__(self, settings):
        self.s = settings

    async def best_model(self) -> str:
        return self.s.gemini_models[0]

    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   max_tokens: int = 1500) -> ChatResult:
        if not self.s.gemini_key:
            raise LLMError("BLACKFOX_GEMINI_KEY is not set")
        headers = {"Authorization": f"Bearer {self.s.gemini_key}"}
        last_err = "no model available"
        async with httpx.AsyncClient(timeout=self.s.gemini_timeout) as c:
            for i, model in enumerate(self.s.gemini_models):
                body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.3}
                if tools:
                    body["tools"] = tools
                    body["tool_choice"] = "auto"
                try:
                    r = await c.post(f"{self.s.gemini_base}/chat/completions", json=body, headers=headers)
                except httpx.HTTPError as e:
                    last_err = f"{model}: {type(e).__name__} {e}"
                    continue
                if r.status_code != 200:
                    last_err = f"{model}: HTTP {r.status_code} {r.text[:200]}"
                    if r.status_code in (401, 403):
                        break
                    continue
                data = r.json()
                try:
                    msg = data["choices"][0]["message"]
                except (KeyError, IndexError, TypeError):
                    last_err = f"{model}: unexpected reply {str(data)[:200]}"
                    continue
                return ChatResult(message=msg, model=data.get("model", model),
                                  usage=data.get("usage", {}), fallback=i > 0)
        raise LLMError(last_err)
