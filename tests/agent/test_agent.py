"""Agent workspace (blackfox/ harness, llm, memory, tools, mcp_server): the loop with a fake LLM."""

import asyncio
import json

from blackfox.design import get_store
from blackfox.harness.agent import Agent
from blackfox.harness.prompts import system_prompt
from blackfox.llm import ChatResult
from blackfox.tools import CONTEXT_PARAMS, load_all


class ScriptedLLM:
    """Answers with a tool call first, then plain text; facts extraction gets a JSON list."""

    def __init__(self):
        self.seen = []

    async def best_model(self):
        return "scripted"

    async def chat(self, messages, tools=None, max_tokens=1500):
        self.seen.append(messages)
        if messages[0]["content"].startswith("You maintain long-term memory"):
            return ChatResult({"content": '["User is Test Engineer"]'}, "scripted")
        if tools and not any(m["role"] == "tool" for m in messages):
            call = {"id": "c1", "type": "function", "function": {
                "name": "set_design_value",
                "arguments": json.dumps({"target": "hab", "property": "radius_m", "value": "3"})}}
            return ChatResult({"content": "", "tool_calls": [call]}, "scripted")
        return ChatResult({"content": "Radius is now 3 m."}, "scripted")


def test_every_tool_has_a_docstring_and_hides_context():
    tools = load_all()
    assert {"set_design_value", "get_design", "remember"} <= set(tools)
    for t in tools.values():
        assert (t.fn.__doc__ or "").strip(), t.name
    assert "visitor_id" in CONTEXT_PARAMS


def test_agent_applies_tool_and_remembers():
    llm = ScriptedLLM()
    agent = Agent(llm=llm)

    async def go():
        res = await agent.run("make the hab 6 m wide", conversation_id="c" * 20, visitor_id="v" * 20)
        await asyncio.gather(*agent._bg)
        return res
    res = asyncio.run(go())
    assert res.text == "Radius is now 3 m."
    assert [s.name for s in res.steps] == ["set_design_value"] and not res.steps[0].is_error
    design, _ = get_store().get("v" * 20)
    assert design["parts"]["hab"]["radius_m"] == 3
    assert any("Test Engineer" in n["text"] for n in agent.memory.recall("v" * 20))
    # the model never sees visitor_id in tool schemas
    tools_shown = json.dumps(llm.seen)
    assert "visitor_id" not in tools_shown


def test_prompt_includes_design_and_notes():
    p = system_prompt("hu", [{"id": 1, "text": "User is Anna"}], {"design": "DESIGN: x"})
    assert "magyarul" in p and "DESIGN: x" in p and "[1] User is Anna" in p
