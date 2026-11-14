"""The agent harness: one user message in, one answer out.

  1. load memory: long-term notes (into the system prompt) + recent conversation turns
  2. loop up to max_steps: ask the LLM with the MCP tool list; run every tool call it
     makes through the toolbox (context such as visitor_id injected by the harness);
     feed results back; stop when it answers without tool calls
  3. if the step budget runs out, force a final answer without tools
  4. save the user message and the answer (+ tool trace) to conversation memory

Every dependency (llm, toolbox factory, memory, prompt builder) is injectable, so a
different approach can be swapped in without editing this file.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..llm import LLM, LLMError, get_llm
from ..memory import MemoryStore, get_memory
from ..settings import get_settings
from . import prompts
from .toolbox import MCPToolbox


@dataclass
class ToolStep:
    name: str
    arguments: dict[str, Any]
    result: str
    is_error: bool
    ms: int


@dataclass
class AgentResult:
    text: str
    model: str = ""
    steps: list[ToolStep] = field(default_factory=list)
    error: str = ""
    reason: str = ""          # why the AI gave no answer: no_key | auth | unreachable | busy


class Agent:
    def __init__(self, llm: LLM | None = None, memory: MemoryStore | None = None,
                 toolbox_factory: Callable[[dict], Any] | None = None,
                 system_prompt: Callable[..., str] = prompts.system_prompt):
        self.s = get_settings()
        self.llm = llm or get_llm()
        self.memory = memory or get_memory()
        self.toolbox_factory = toolbox_factory or self._default_toolbox
        self.system_prompt = system_prompt
        self._sem = asyncio.Semaphore(self.s.agent_concurrency)
        self._bg: set[asyncio.Task] = set()

    async def _auto_remember(self, visitor_id: str, user_message: str) -> None:
        """Background: pull durable facts the user stated about themselves / their project
        into long-term memory, so memory works even when the model forgets to call remember."""
        known = [n["text"] for n in self.memory.recall(visitor_id, limit=30)]
        ask = [{"role": "system", "content": prompts.EXTRACT},
               {"role": "user", "content": json.dumps({"already_known": known, "message": user_message},
                                                      ensure_ascii=False)}]
        try:
            res = await self.llm.chat(ask, tools=None, max_tokens=400)
            raw = (res.message.get("content") or "").strip()
            raw = raw[raw.find("["): raw.rfind("]") + 1]
            facts = json.loads(raw) if raw else []
        except Exception:
            return
        for f in facts[:5] if isinstance(facts, list) else []:
            if isinstance(f, str) and 3 < len(f) < 300:
                try:
                    self.memory.remember(visitor_id, f)
                except ValueError:
                    pass

    def _default_toolbox(self, context: dict):
        return MCPToolbox(context=context)

    async def _open_toolbox(self, context: dict):
        """Preferred transport first; if the MCP service is unreachable fall back to in-process."""
        tb = self.toolbox_factory(context)
        try:
            return await tb.__aenter__()
        except Exception:
            if getattr(tb, "transport", "") == "http":
                tb = MCPToolbox(context=context, transport="inproc")
                return await tb.__aenter__()
            raise

    def _messages(self, conversation_id: str, visitor_id: str, lang: str, user_message: str,
                  profile: dict | None = None) -> list[dict]:
        notes = self.memory.recall(visitor_id, user_message, limit=12)
        msgs = [{"role": "system", "content": self.system_prompt(lang, notes, profile)}]
        for m in self.memory.history(conversation_id, limit=self.s.agent_history_turns * 2):
            msgs.append({"role": m["role"], "content": m["content"]})
        msgs.append({"role": "user", "content": user_message})
        return msgs

    async def run(self, user_message: str, conversation_id: str, visitor_id: str, lang: str = "en",
                  profile: dict | None = None,
                  extra_trace: Callable[["AgentResult"], list[dict]] | None = None) -> AgentResult:
        """profile: optional page fields - see prompts.system_prompt.
        extra_trace(result): extra entries saved with the answer's trace (e.g. a simulation snapshot)."""
        async with self._sem:
            result = await self._run(user_message, conversation_id, visitor_id, lang, profile)
        self.memory.append(conversation_id, visitor_id, "user", user_message)
        if result.text and not any(st.name == "remember" for st in result.steps):
            task = asyncio.create_task(self._auto_remember(visitor_id, user_message))
            self._bg.add(task)
            task.add_done_callback(self._bg.discard)
        if result.text:
            trace = [s.__dict__ for s in result.steps] + (extra_trace(result) if extra_trace else [])
            self.memory.append(conversation_id, visitor_id, "assistant", result.text,
                               trace=trace, model=result.model)
        return result

    async def _run(self, user_message: str, conversation_id: str, visitor_id: str, lang: str,
                   profile: dict | None = None) -> AgentResult:
        messages = self._messages(conversation_id, visitor_id, lang, user_message, profile)
        steps: list[ToolStep] = []
        model = ""
        try:
            toolbox = await self._open_toolbox({"visitor_id": visitor_id})
        except Exception as e:
            return AgentResult(text="", error=f"tools unavailable: {e}")
        try:
            tools = toolbox.openai_tools()
            for _ in range(self.s.agent_max_steps):
                res = await self.llm.chat(messages, tools=tools, max_tokens=self.s.agent_max_tokens)
                model = res.model
                calls = res.message.get("tool_calls") or []
                if not calls:
                    text = (res.message.get("content") or "").strip()
                    if text:
                        return AgentResult(text=text, model=model, steps=steps)
                    break
                messages.append({"role": "assistant", "content": res.message.get("content") or "",
                                 "tool_calls": calls})
                for call in calls:
                    fn = call.get("function", {})
                    name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                        if not isinstance(args, dict):
                            raise ValueError("arguments must be an object")
                    except ValueError as e:
                        out, err, args = json.dumps({"error": f"bad JSON arguments: {e}"}), True, {}
                        ms = 0
                    else:
                        t0 = time.monotonic()
                        out, err = await toolbox.call(name, args)
                        ms = int((time.monotonic() - t0) * 1000)
                    steps.append(ToolStep(name, args, out, err, ms))
                    messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": out})
            # out of steps (or empty answer): one last call without tools
            messages.append({"role": "user", "content": "Now give your final answer to my question, "
                                                        "using the tool results above. Do not call tools."})
            res = await self.llm.chat(messages, tools=None, max_tokens=self.s.agent_max_tokens)
            return AgentResult(text=(res.message.get("content") or "").strip(), model=res.model, steps=steps)
        except LLMError as e:
            return AgentResult(text="", model=model, steps=steps, error=str(e), reason=getattr(e, "reason", "busy"))
        finally:
            await toolbox.__aexit__(None, None, None)


_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent
