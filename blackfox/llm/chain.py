"""Try the primary LLM (Gemini); on ANY failure use the fallback (Groq) and mark the result."""

import logging

from . import ChatResult, LLMError

log = logging.getLogger("blackfox.llm")


class ChainLLM:
    def __init__(self, primary, fallback):
        self.primary, self.fallback = primary, fallback

    async def best_model(self) -> str:
        try:
            return await self.primary.best_model()
        except Exception:
            return await self.fallback.best_model()

    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   max_tokens: int = 1500) -> ChatResult:
        try:
            return await self.primary.chat(messages, tools, max_tokens)
        except Exception as e:      # not only LLMError: a bad reply or network error must fall back too
            log.warning("primary LLM failed (%s: %s); using fallback", type(e).__name__, e)
        try:
            result = await self.fallback.chat(messages, tools, max_tokens)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"fallback: {type(e).__name__}: {e}") from e
        result.fallback = True
        return result

    async def status(self) -> dict:
        """Healthy when either side works (the fallback's own check decides when Gemini is down)."""
        check = getattr(self.fallback, "status", None)
        return await check() if check else {"problem": ""}
