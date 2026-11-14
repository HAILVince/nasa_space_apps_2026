"""The Black Fox MCP server: every tool in blackfox.tools (enabled groups only),
plus the research database as MCP resources.

  build_server()  -> MCPServer instance (used in-process by the harness in dev)
  build_app()     -> ASGI app: Streamable HTTP at /mcp behind a bearer token, /healthz open
  python -m blackfox.mcp_server [--stdio]   run it (HTTP on 127.0.0.1:8087 by default)

Any MCP client (Claude Desktop/Code, Cursor, the harness) can connect with
  URL   https://<site>/mcp     header  Authorization: Bearer <BLACKFOX_MCP_TOKEN>
"""

import hmac
import json

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from ..db import get_store
from ..settings import get_settings
from ..tools import enabled_tools

INSTRUCTIONS = (
    "Black Fox Hackathon research tools. A central database of NASA research on fire and flames "
    "in microgravity / free fall (search_research, get_research, list_research, add_research, "
    "add_research_fact), physics and combustion calculators (free_fall_time, buoyant_flow_velocity, "
    "droplet_burning, fuel_stoichiometry, orbit_info, calculate, ...) and per-visitor long-term "
    "memory (remember, recall, forget). Records with status 'community' are unverified."
)


def build_server() -> MCPServer:
    s = get_settings()
    server = MCPServer("blackfox", title="Black Fox Hackathon research server", instructions=INSTRUCTIONS,
                       version="1.0")
    for spec in enabled_tools(s.tool_groups):
        server.add_tool(spec.fn, name=spec.name, meta={"group": spec.group, "writes": spec.writes},
                        structured_output=False)

    if "research" in s.tool_groups:
        @server.resource("research://index", mime_type="application/json",
                         description="Every record in the research database (slug, title, kind, status)")
        def research_index() -> str:
            return json.dumps(get_store().list(limit=500), ensure_ascii=False)

        @server.resource("research://record/{slug}", mime_type="application/json",
                         description="One research record with facts and sources")
        def research_record(slug: str) -> str:
            return json.dumps(get_store().get(slug) or {"error": "not found"}, ensure_ascii=False)
    return server


class _Guard:
    """ASGI wrapper: /healthz is public, everything else needs the bearer token."""

    def __init__(self, app, token: str):
        self.app, self.token = app, token.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["path"] == "/healthz":
            body = json.dumps({"ok": True, "service": "blackfox-mcp"}).encode()
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"application/json")]})
            return await send({"type": "http.response.body", "body": body})
        auth = dict(scope.get("headers", [])).get(b"authorization", b"")
        given = auth[7:] if auth[:7].lower() == b"bearer " else b""
        if not self.token or not hmac.compare_digest(given, self.token):
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"www-authenticate", b"Bearer")]})
            return await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
        return await self.app(scope, receive, send)


def build_app():
    s = get_settings()
    app = build_server().streamable_http_app(
        stateless_http=True, json_response=True,
        # the bearer token is the protection; nginx serves it under the public domains
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    return _Guard(app, s.mcp_token)
