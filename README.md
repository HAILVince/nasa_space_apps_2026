# Black Fox design agent — NASA Space Apps Challenge 2026

An AI agent for NASA habitat and spacecraft designers and engineers. Describe a habitat or
spacecraft and its scenario (location, crew, mission length), change any value, and the agent
re-simulates the design and explains what passes, what fails and how to fix it. It remembers
the user and their design between visits.

Live at **blackfoxhackathon.hu** (answers in Hungarian) and **blackfoxhackathon.online** (English).
The page is deliberately bare: one HTML file, no CSS, a chat box (Enter sends, Shift+Enter = new line).

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://127.0.0.1:8000
```

The agent needs `BLACKFOX_AI_KEY` (and optionally `BLACKFOX_AI_BASE`); it calls the VPS's
OpenAI-compatible AI API, which rotates the Groq keys and falls back between models.
All settings are listed in `blackfox/settings.py`.

## Using it

Talk normally ("6 crew on the lunar south pole for 300 days, 4 m wide module") or type
instant commands that skip the AI:

| Command | Does |
|---|---|
| `show` | full simulation snapshot |
| `select <part>` | that part's inputs and computed results |
| `set <part>.<property> = <value>` | e.g. `set hab.radius_m = 3`, `set environment.crew = 6` |
| `add <type> <name>` / `remove <part>` | e.g. `add fission_reactor kp1` |
| `new habitat` / `new spacecraft` | start over |
| `help` | this list |

Every change re-runs the simulation (`blackfox/physics/spacecraft.py`, first-order sizing):
hull hoop stress and safety factor, pressurized/habitable volume per crew, mass breakdown,
solar/fission power vs load, battery coverage of night/eclipse, radiator heat rejection,
life-support consumables with recycling, and delta-v.

## Research database

The agent can look things up in a research database of plain JSON text files (no pictures) about three
gravity environments: the Moon, Mars and 0 g. It is sorted by gravity, then topic, then year, and is
collected from NASA and open research sources with `python -m blackfox.collect`.
Format, sources and how the AI reads it: [blackfox/db/README.md](blackfox/db/README.md).

## Workspaces (how the team splits the work)

| # | Workspace | Folder |
|---|---|---|
| 1 | Frontend | `frontend/` |
| 2 | Backend (HTTP API) | `app/` |
| 3 | Simulation (design engine) | `blackfox/design/` |
| 4 | Agent (AI loop, memory, tools) | `blackfox/` except `design/` |
| 5 | Deploy (VPS) | `deploy/` |

Each folder has its own README; the contracts between them, the branch workflow and how
to run the tests are in **[CONTRIBUTING.md](CONTRIBUTING.md)**. The API is in [docs/API.md](docs/API.md).

## Deployment (automatic)

Push to the default branch (`main`) and the VPS is live within about a minute:

- `blackfox-update.timer` runs `/usr/local/sbin/blackfox-update` every minute. If the
  GitHub commit **or** the checked-out branch differs (or the deploy tree was modified),
  it hard-resets `/opt/blackfox/site` to `origin/<branch>`, installs `requirements.txt`
  if it changed, restarts `blackfox.service` and checks `/healthz`.
- If the new commit does not come up healthy it rolls back to the previous one and
  skips the broken commit until a newer one is pushed.
- Branch: `BLACKFOX_BRANCH` in `/etc/blackfox.env` (`auto` = the repo's GitHub default branch).
- Logs: `journalctl -u blackfox-update -u blackfox`.

nginx proxies both domains to `127.0.0.1:8086`; `blackfox-golive.timer` issues the
Let's Encrypt certificates once the DNS records point at the VPS.

## Fire safety research dashboards

The home page also offers mission dashboards for spacecraft, stations, lunar bases,
Mars habitats and pressurized rovers. Filter by prevention, detection or suppression,
search investigations, and compare two to four experiment families. The stateless
`/api/research/*` backend works without an AI key. It currently uses curated NASA
challenge metadata, with explained topic rankings and explicit unknown conditions;
it does not contain PSI measurements or predict fire risk. Implementation steps and the
next data milestone are in [docs/DASHBOARD_PLAN.md](docs/DASHBOARD_PLAN.md).
