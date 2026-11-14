# Workspace 2 — Backend (HTTP API)

`main.py` is the only web layer: JSON endpoints under `/api/*`, `/healthz`, and it serves
`frontend/` as static files. `render.py` turns the agent's Markdown into safe HTML.

- The contract with the page is `docs/API.md`; keep it in sync.
- It routes each chat message: typed commands -> simulation workspace
  (`blackfox.design.run_command`), everything else -> agent workspace (`get_agent().run`).
- Rate limit: 6 AI messages per minute per IP (commands are not limited).
- The deploy workspace runs this as `uvicorn app.main:app` and checks `/healthz`.

Test: `pytest tests/backend` (the AI is faked, no key needed).
