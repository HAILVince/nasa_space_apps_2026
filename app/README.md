# Workspace 2 — Backend (HTTP API)

`main.py` is the web entry point: JSON endpoints under `/api/*`, `/healthz`, and it serves
`frontend/` as static files. `render.py` turns the agent's Markdown into safe HTML.

- The contract with the page is `docs/API.md`; keep it in sync.
- It routes each chat message: typed commands -> simulation workspace
  (`blackfox.design.run_command`), everything else -> agent workspace (`get_agent().run`).
- Rate limit: 6 AI messages per minute per IP (`BLACKFOX_ASKS_PER_MINUTE`; commands are not limited).
- `/api/ai/status` reports whether the AI API is reachable and accepts the site; a failed chat
  answers 503 with a `reason` and logs the cause.
- The deploy workspace runs this as `uvicorn app.main:app` and checks `/healthz`.

Test: `pytest tests/backend` (the AI is faked, no key needed).

`research.py` exposes stateless scenario dashboards, explained relevance ranking, and
investigation comparison from curated challenge metadata. It needs no AI key.
