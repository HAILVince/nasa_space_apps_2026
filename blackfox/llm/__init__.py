"""LLM providers. The harness only talks to the LLM interface below; add a
provider (Anthropic, OpenAI, a local model...) by implementing it and registering
it in BACKENDS, then set BLACKFOX_LLM_BACKEND."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..settings import get_settings


@dataclass
class ChatResult:
    message: dict[str, Any]          # OpenAI-style assistant message (content and/or tool_calls)
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    fallback: bool = False


class LLMError(Exception):
    """reason says why, so the site can tell the user something useful:
    no_key | auth (key rejected) | unreachable (AI API down) | busy (rate limits, model errors)."""

    def __init__(self, message: str, reason: str = "busy"):
        super().__init__(message)
        self.reason = reason


class LLM(Protocol):
    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   max_tokens: int = 1500) -> ChatResult: ...
    async def best_model(self) -> str: ...


def _axioma():
    from .axioma import AxiomaLLM
    return AxiomaLLM(get_settings())


BACKENDS = {"axioma": _axioma}
_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = BACKENDS[get_settings().llm_backend]()
    return _llm
