# Workspace 4 — Agent

Everything in `blackfox/` except `design/` (that is the simulation workspace).

| Folder | What |
|---|---|
| `harness/` | the agent loop (`agent.py`), system prompt + memory-extraction prompt (`prompts.py`), MCP toolbox |
| `llm/` | LLM provider (the VPS AI API with key rotation and model fallback) |
| `memory/` | chat history + long-term notes (SQLite) |
| `tools/` | the tools the AI can call: design, physics, memory, research DB, calculate |
| `mcp_server/` | publishes the tools over MCP (also usable from Claude Desktop/Code) |
| `db/`, `physics/` | NASA microgravity-combustion research DB and physics formulas behind the tools |
| `settings.py` | every setting, from environment variables |

- Changing the persona or rules: `harness/prompts.py`.
- New tool: a typed function with a docstring and `@tool("group")` in `tools/`; nothing else.
- Design tools must go through `blackfox.design` (never edit design JSON by hand here).

Test: `pytest tests/agent` (uses a scripted fake LLM, no key needed).
