"""Try the primary LLM; on any LLMError use the fallback and mark the result."""

import logging

from . import ChatResult, LLMError

log = logging.getLogger("blackfox.llm")


class ChainLLM:
    def __init__(self, primary, fallback):
        self.primary, self.fallback = primary, fallback

    async def best_model(self) -> str:
        return await self.primary.best_model()

    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   max_tokens: int = 1500) -> ChatResult:
        try:
            return await self.primary.chat(messages, tools, max_tokens)
        except LLMError as e:
            log.warning("primary LLM failed (%s); using fallback", e)
        result = await self.fallback.chat(messages, tools, max_tokens)
        result.fallback = True
        return result
