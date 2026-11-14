# Working on Black Fox — 5 workspaces

The project is split into five workspaces so several people can work at the same time
without stepping on each other. Each one has its own folder, README, owner and tests.

| # | Workspace | Folder | Does | Tests |
|---|---|---|---|---|
| 1 | **Frontend** | `frontend/` | the web page (plain HTML, no styles) | `tests/frontend` |
| 2 | **Backend** | `app/` | the HTTP API between page and agent | `tests/backend` |
| 3 | **Simulation** | `blackfox/design/` | the habitat/spacecraft physics + design memory | `tests/simulation` |
| 4 | **Agent** | `blackfox/` (everything except `design/`) | AI loop, prompt, LLM, memory, tools, MCP server | `tests/agent` |
| 5 | **Deploy** | `deploy/` | VPS: systemd, nginx, auto-update, HTTPS | `tests/deploy` |

## The contracts between workspaces

Workspaces only talk through these interfaces. Changing one means changing both sides in
the same pull request and telling the other owner:

- Frontend <-> Backend: **`docs/API.md`** (endpoints and JSON shapes)
- Backend / Agent -> Simulation: the functions exported by **`blackfox/design/__init__.py`**
  and the design JSON format described in `blackfox/design/README.md`
- Backend -> Agent: `get_agent().run(...)` in `blackfox/harness/agent.py`
- Deploy -> Backend: `uvicorn app.main:app` on port 8086, `/healthz` returning the commit

## Workflow

```bash
git switch main && git pull
git switch -c frontend/better-history        # <workspace>/<what>: frontend/, backend/, sim/, agent/, deploy/
# ... work only inside your workspace folder (+ its tests) ...
pip install -r requirements-dev.txt
pytest                                        # all workspaces; or: pytest tests/simulation
git push -u origin frontend/better-history    # then open a pull request into main
```

- One branch per person per task; keep pull requests small and inside one workspace.
- GitHub runs every workspace's tests on each push and pull request (`.github/workflows/ci.yml`).
  Merge only when it is green.
- **Merging to `main` deploys to the live site within a minute.** If the new version does not start,
  the server rolls back by itself. If it starts but is wrong, undo it with
  `git revert <commit>` + `git push` (or the Revert button on the pull request).
- Never edit files on the server: `/opt/blackfox/site` is reset to GitHub every minute.

## Run everything locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
BLACKFOX_AI_KEY=... uvicorn app.main:app --reload     # http://127.0.0.1:8000
```

Without an AI key the page, typed commands and the simulation still work; only AI answers fail.
