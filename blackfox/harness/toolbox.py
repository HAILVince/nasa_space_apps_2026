"""Toolbox = the harness's view of the tools. It always speaks MCP, so the same
code works against the separate blackfox-mcp service (transport "http") or an
in-process server (transport "inproc", for development or if the service is down).
Swap in any other MCP server by pointing BLACKFOX_MCP_URL somewhere else.
"""

import json
from contextlib import AsyncExitStack
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from ..settings import get_settings
from ..tools import CONTEXT_PARAMS
from ..tools.registry import CATEGORIES, REGISTRY, load_all

MAX_RESULT_CHARS = 6000
OPEN_TOOL = "open_tool_category"
QUICK_TOOLS = {"calculate", "calculate_batch", "convert_units", "show_on_page"}


class MCPToolbox:
    def __init__(self, context: dict[str, Any] | None = None, transport: str | None = None):
        self.s = get_settings()
        self.transport = transport or self.s.tool_transport
        self.context = context or {}
        self._stack: AsyncExitStack | None = None
        self._client: Client | None = None
        self._tools: list = []
        self.opened: set[str] = set()      # categories whose tools the model can see

    async def __aenter__(self) -> "MCPToolbox":
        self._stack = AsyncExitStack()
        if self.transport == "http":
            http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {self.s.mcp_token}"},
                                      timeout=httpx2.Timeout(30, read=60))
            await self._stack.enter_async_context(http)
            target = streamable_http_client(self.s.mcp_url, http_client=http)
        else:
            from ..mcp_server import build_server
            target = build_server()
        self._client = await self._stack.enter_async_context(Client(target))
        self._tools = (await self._client.list_tools()).tools
        return self

    async def __aexit__(self, *exc) -> None:
        if self._stack:
            await self._stack.aclose()

    def category_of(self, name: str) -> str:
        load_all()
        spec = REGISTRY.get(name)
        return spec.group if spec else "other"

    def _categories(self) -> dict[str, list]:
        cats: dict[str, list] = {}
        for t in self._tools:
            cats.setdefault(self.category_of(t.name), []).append(t)
        return cats

    def _open_tool_schema(self) -> dict:
        cats = self._categories()
        lines = "; ".join(f"{c}: {CATEGORIES.get(c, 'other tools')}" for c in cats)
        return {"type": "function", "function": {
            "name": OPEN_TOOL,
            "description": "Tools are grouped in categories and hidden until you open one. Call this with the "
                           "category you need, then use its tools on your next step. Categories - " + lines,
            "parameters": {"type": "object", "properties": {
                "category": {"type": "string", "enum": list(cats)}}, "required": ["category"]}}}

    def openai_tools(self) -> list[dict]:
        """The open_tool_category tool plus the tools of categories opened so far, in OpenAI
        function-calling format, with context params hidden. Call again after every step."""
        out = [self._open_tool_schema()]
        for t in self._tools:
            if t.name not in QUICK_TOOLS and self.category_of(t.name) not in self.opened:
                continue
            schema = json.loads(json.dumps(getattr(t, "input_schema", None) or getattr(t, "inputSchema", {})))
            props = schema.get("properties", {})
            for p in CONTEXT_PARAMS:
                props.pop(p, None)
            if "required" in schema:
                schema["required"] = [r for r in schema["required"] if r not in CONTEXT_PARAMS]
            schema.pop("title", None)
            for v in props.values():
                v.pop("title", None)
            out.append({"type": "function", "function": {
                "name": t.name, "description": (t.description or "")[:900], "parameters": schema}})
        return out

    def has(self, name: str) -> bool:
        return any(t.name == name for t in self._tools)

    def _accepts(self, name: str, param: str) -> bool:
        for t in self._tools:
            if t.name == name:
                schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", {})
                return param in schema.get("properties", {})
        return False

    def _open(self, category: str) -> tuple[str, bool]:
        tools = self._categories().get(category)
        if not tools:
            return json.dumps({"error": f"unknown category '{category}'",
                               "categories": list(self._categories())}), True
        self.opened.add(category)
        return json.dumps({"opened": category, "tools": {
            t.name: (t.description or "").strip().split("\n")[0][:160] for t in tools}}), False

    async def call(self, name: str, args: dict[str, Any]) -> tuple[str, bool]:
        """-> (result text, is_error)"""
        if name == OPEN_TOOL:
            return self._open(str(args.get("category", "")))
        if not self.has(name):
            return json.dumps({"error": f"unknown tool '{name}'"}), True
        if name not in QUICK_TOOLS:
            self.opened.add(self.category_of(name))  # named tools open their category
        args = {k: v for k, v in args.items() if k not in CONTEXT_PARAMS}
        for p, val in self.context.items():
            if p in CONTEXT_PARAMS and self._accepts(name, p):
                args[p] = val
        try:
            res = await self._client.call_tool(name, args)
        except Exception as e:  # transport/validation errors go back to the model as text
            return json.dumps({"error": f"{type(e).__name__}: {e}"[:500]}), True
        text = "\n".join(getattr(c, "text", "") for c in res.content if getattr(c, "type", "") == "text")
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "\n...[truncated]"
        return text or "{}", bool(getattr(res, "is_error", False))

