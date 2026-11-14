"""AI_agency.py straight, in-process: the same api_manager the VPS AI API wraps
(Groq key pool, key/model failover), imported from BLACKFOX_AGENCY_DIR. No HTTP
and no AI API key; needs read access to that folder's config.json and the `groq`
package (run with /home/debian/automation/venv/bin/python, or pip install groq).

Building the manager probes every Groq key once (a 2-token request per key and
model), so it is built lazily on the first call and then reused.
"""

import asyncio
import importlib
import sys
import threading

from . import ChatResult, LLMError


def importable(agency_dir: str) -> bool:
    import importlib.util
    from pathlib import Path
    return bool(agency_dir) and (Path(agency_dir) / "AI_agency.py").is_file() \
        and importlib.util.find_spec("groq") is not None


class AgencyLLM:
    def __init__(self, settings):
        self.s = settings
        self._mod = None
        self._manager = None
        self._lock = threading.Lock()

    def _get(self):
        with self._lock:
            if self._manager is None:
                if not self.s.agency_dir:
                    raise LLMError("BLACKFOX_AGENCY_DIR is not set")
                if self.s.agency_dir not in sys.path:
                    sys.path.insert(0, self.s.agency_dir)
                try:
                    self._mod = importlib.import_module("AI_agency")
                    self._manager = self._mod.api_manager()
                except Exception as e:  # noqa: BLE001 - missing groq, unreadable config.json...
                    raise LLMError(f"AI_agency unavailable: {type(e).__name__}: {e}") from e
            return self._mod, self._manager

    async def best_model(self) -> str:
        return self.s.model_preference[0]

    def _call(self, model, messages, tools, max_tokens):
        mod, mgr = self._get()
        reply = mgr.run_automated_task(
            None, None, target_model=mod.RETIRED_MODELS.get(model, model) if hasattr(mod, "RETIRED_MODELS") else model,
            max_tokens=max_tokens, reasoning_effort="medium", temperature=0.3, max_wait=20,
            messages=messages, tool_schemas=tools or None, return_message=True)
        used, usage = mgr.last_call()
        msg = {"role": "assistant", "content": getattr(reply, "content", None)}
        calls = [{"id": c.id, "type": "function",
                  "function": {"name": c.function.name, "arguments": c.function.arguments}}
                 for c in (getattr(reply, "tool_calls", None) or [])]
        if calls:
            msg["tool_calls"] = calls
        usage = usage.model_dump() if hasattr(usage, "model_dump") else (usage or {})
        return ChatResult(message=msg, model=used or model, usage=usage, fallback=bool(used) and used != model)

    async def chat(self, messages: list[dict], tools: list[dict] | None = None,
                   max_tokens: int = 1500) -> ChatResult:
        model = self.s.model_preference[0]
        try:
            return await asyncio.to_thread(self._call, model, messages, tools, max_tokens)
        except LLMError:
            raise
        except Exception as e:  # noqa: BLE001 - QuotaExhausted, Groq errors
            raise LLMError(f"AI_agency: {type(e).__name__}: {e}") from e
