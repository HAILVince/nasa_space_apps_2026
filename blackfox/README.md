# Workspace 4 — Agent

Everything in `blackfox/` except `design/` (that is the simulation workspace).

| Folder | What |
|---|---|
| `harness/` | the agent loop (`agent.py`), system prompt + memory-extraction prompt (`prompts.py`), MCP toolbox |
| `llm/` | LLM provider (the VPS AI API with key rotation and model fallback) |
| `memory/` | chat history + long-term notes (SQLite) |
| `tools/` | the tools the AI can call: design, physics, memory, research DB, calculate |
| `mcp_server/` | publishes the tools over MCP (also usable from Claude Desktop/Code) |
| `db/` | the research database the AI reads: JSON files sorted by gravity (Moon, Mars, 0 g) and topic, see `db/README.md` |
| `collect/` | downloads and sorts the research database (`python -m blackfox.collect`) |
| `physics/` | physics formulas behind the tools |
| `settings.py` | every setting, from environment variables |

- Changing the persona or rules: `harness/prompts.py`.
- New tool: a typed function with a docstring and `@tool("group")` in `tools/`; nothing else.
- Fire-lab scenario: `tools/scenario_tools.py` (`fire_scenario_options`, `get_fire_scenario`, `set_fire_scenario`) lets the
  AI change the scenario the user has open; the rules and the per-visitor store are in `physics/scenario.py`, the chat
  answer returns the new scenario and `frontend/js/lab.js` applies it. `simulate_cabin_fire` is the what-if that leaves the lab alone.
- Page guide: `tools/ui_tools.py` (`show_on_page`, group `ui`, always on and always visible) lets the AI scroll the
  user's browser to a part of the site and make it pulse once; the chat answer carries the action as `ui` and
  `frontend/js/guide.js` runs it. A new target = a `data-guide="<name>"` element plus an entry in `TARGETS`.
- Design tools must go through `blackfox.design` (never edit design JSON by hand here).

Test: `pytest tests/agent` (uses a scripted fake LLM, no key needed).
