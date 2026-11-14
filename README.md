# Black Fox — fire-safety lab and design agent · NASA Space Apps Challenge 2026

**Black Fox** helps habitat and spacecraft engineers answer one question before they fly:
*if this material catches fire here, in this gravity and this cabin atmosphere, what happens?*

- **Fire lab** (the home page): pick the environment — Earth orbit (ISS), lunar orbit (Gateway),
  the lunar surface, the Martian surface or an Earth reference — set the cabin pressure, oxygen
  and temperature, choose the material and the place of the fire in the HAB-01 module, the
  ventilation, the alarm response and the extinguisher. The simulator returns the flammability
  limit at that pressure (measured NASA-STD-6001 data), corrected for gravity and air flow, the
  oxygen margin, flame spread, heat release, detection and extinction times, CO against the
  NASA SMAC, and a risk level; the 3D view shows the same fire.
- **Real data**: every key number comes from the knowledge base in `blackfox/db/knowledge/`
  (Moon / Mars / 0 g records); the hand-checked fire-safety facts in
  `knowledge/curated/spacecraft_fire_safety.json` were read from NASA Technical Reports Server
  documents and link to them. Biology, health and other non-fire topics are filtered out.
- **3D**: the module, terrains and lunar globe are built and baked in **Blender** from code
  (`blender/`), rendered in the browser with Three.js: physically based materials, baked
  ambient occlusion, bloom, a ray-marched flame whose shape and colour follow the physics,
  smoke carried by the ventilation, X-ray / thermal / airflow modes.
- **AI engineer**: the design agent (chat) sees the open scenario and can re-run it with its
  `simulate_cabin_fire` tool, search the research database and remember the user.

- **Research dashboards** (*Investigations* tab): NASA microgravity combustion experiment families
  (BASS, Saffire, SAME, FLEX, BRE, CFI-G) ranked per mission (spacecraft, station, lunar base,
  Mars habitat, rover) and focus (prevention, detection, suppression), with search and a 2–4 way
  comparison table (`app/research.py`, see below).

Live at **blackfoxhackathon.hu** and **blackfoxhackathon.online**. The interface follows the
domain (Hungarian on `.hu`) and has a HU/EN switch; agent replies default to English and the
reply language selector in the AI console switches them to Hungarian.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://127.0.0.1:8000
```

The agent needs `BLACKFOX_AI_KEY` (and optionally `BLACKFOX_AI_BASE`); it calls the VPS's
OpenAI-compatible AI API, which rotates the Groq keys and falls back between models.
All settings are listed in `blackfox/settings.py`.

## The fire model in one paragraph

`blackfox/physics/fire.py`: the NASA-STD-6001 maximum oxygen concentration of the material is
interpolated at the cabin pressure; it is lowered by up to 3 % O2 as gravity goes to zero
(0 g limits were measured up to 4 % below 1 g) and raised steeply when the air is nearly still
(radiative quenching). Opposed and concurrent flame-spread correlations from NASA drop-tower
tests give the spread rate, a burning-rate model gives the heat release, Thornton's rule the
oxygen use, product yields the CO and smoke, a two-zone cabin model the transport to the smoke
detector. Ventilation shutdown slows the flame but does not put it out at once (Saffire V).
Details and sources are in the module docstring and in `docs/API.md`.

## Using the design console

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
| 1 | Frontend (fire lab, 3D) | `frontend/`, 3D assets in `blender/` |
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

The *Investigations* tab offers mission dashboards for spacecraft, stations, lunar bases,
Mars habitats and pressurized rovers. Filter by prevention, detection or suppression,
search investigations, and compare two to four experiment families. The stateless
`/api/research/*` backend works without an AI key. It currently uses curated NASA
challenge metadata, with explained topic rankings and explicit unknown conditions;
it does not contain PSI measurements or predict fire risk. Implementation steps and the
next data milestone are in [docs/DASHBOARD_PLAN.md](docs/DASHBOARD_PLAN.md).
