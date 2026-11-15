# Black Fox — fire-safety lab and design agent · NASA Space Apps Challenge 2026
https://blackfoxhackathon.hu
**Black Fox** helps habitat and spacecraft engineers answer one question before they fly:
*if this material catches fire here, in this gravity and this cabin atmosphere, what happens?*

- **Fire lab** (the home page): pick the environment — Earth orbit (ISS), lunar orbit (Gateway),
  the lunar surface, the Martian surface or an Earth reference — set the cabin pressure, oxygen
  and temperature, choose the material and the place of the fire in the HAB-01 module, the
  ventilation, the alarm response and the extinguisher. The simulator returns the flammability
  limit at that pressure (measured NASA-STD-6001 data), corrected for gravity and air flow, the
  oxygen margin, flame spread, heat release, detection and extinction times, CO against the
  NASA SMAC, and a risk level; the 3D view shows the same fire.
- **Research data**: the knowledge base in `blackfox/db/knowledge/` contains source records
  about the Moon, Mars and 0 g; the hand-checked fire-safety facts in
  `blackfox/db/knowledge/curated/spacecraft_fire_safety.json` were read from NASA Technical Reports Server
  documents and link to them. Biology, health and other non-fire topics are filtered out.
- **3D**: the module, terrains and lunar globe are built and baked in **Blender** from code
  (`blender/`), rendered in the browser with Three.js: physically based materials, baked
  ambient occlusion, bloom, a ray-marched flame whose shape and colour follow the physics,
  smoke carried by the ventilation, X-ray / thermal / airflow modes.
- **AI engineer**: the design agent (chat) sees the open scenario and can re-run it with its
  `simulate_cabin_fire` tool, search the research database and remember the user.

- **Research dashboards** (*Investigations* tab): NASA microgravity combustion experiment families
  including BASS, Saffire, SAME and FLEX, ranked per mission (spacecraft, station, lunar base,
  Mars habitat, rover) and focus (prevention, detection, suppression), with search and a 2–4 way
  comparison table (`app/research.py`, see below).

Live at **blackfoxhackathon.hu** and **blackfoxhackathon.online**. The interface and the agent
are in English.

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://127.0.0.1:8000
```

The agent calls the VPS's OpenAI-compatible AI API (`BLACKFOX_AI_BASE`), which rotates the Groq
keys and falls back between models. `BLACKFOX_AI_KEY` is needed when that API is on another
machine; on the VPS itself (loopback) the key is optional and a rejected key falls back to a
keyless local call. `GET /api/ai/status` shows whether the AI is reachable and accepted.
All settings are listed in `blackfox/settings.py`.

## Explore the project

1. Open the home page and enter the **fire lab** (`/lab.html`). Choose a location, cabin
   atmosphere, material and fire location; start a run to see the calculated results and 3D view.
2. Open the **evidence** page (`/evidence.html`) to compare a cabin atmosphere with reported
   PSI experiment envelopes. The investigations view lets you search, rank and compare studies.
3. Open `/spread.html` for the room-to-room 2D fire-spread simulator and the PSI Variables view.
4. Use the design console to ask the AI about a scenario or use the commands below. The fire lab
   and evidence pages can be explored without an AI key; chat needs a reachable AI service.

## How the pieces fit together

```text
Browser: lab / 3D, evidence and investigation views, 2D spread and CFD
      | HTTP requests and simulation outcomes
      v
FastAPI: app/main.py + app/flame_routes.py + app/research.py
      |                       |                         |
      v                       v                         v
Fire and design models    PSI data and analysis    Agent tools and memory
blackfox/physics/         flame/                   blackfox/harness/ + tools/
blackfox/design/          raw tables + JSON        research store + AI API
```

The browser sends a scenario to the backend. The cabin fire model calculates a result, which the
3D lab displays; the browser also runs its 2D spread and CFD models and can report their outcomes
for the saved run. The evidence views query PSI investigations and envelopes separately. The
agent can use tools to inspect the scenario, run calculations and search research; its answers
should be checked against the cited sources.

| Part | Purpose | Where to look |
|---|---|---|
| Browser interface | Pages, scenario controls, 3D rendering, evidence views and browser-side models; native ES modules, no build step | [frontend/README.md](frontend/README.md), `frontend/js/cfd/` |
| HTTP API | Validates requests, serves the interface, connects models and stores visitor sessions and runs | [app/README.md](app/README.md), [API reference](docs/API.md) |
| Cabin fire model | Estimates flammability, spread, heat, smoke, detection and suppression for a scenario | `blackfox/physics/fire.py`, [materials and sources](docs/MATERIALS.md) |
| PSI evidence | Investigation metadata, experimental envelopes, cleaned test rows, coverage, search and rankings | [flame/README.md](flame/README.md), `app/flame_routes.py` |
| Research dashboard | Mission and focus filters, topic-based ranking and investigation comparison | `app/research.py`, [dashboard plan](docs/DASHBOARD_PLAN.md) |
| Design engine | First-order habitat and spacecraft sizing and typed design commands | [blackfox/design/README.md](blackfox/design/README.md) |
| AI agent | Tool-calling chat, scenario access, research search and visitor memory | [blackfox/README.md](blackfox/README.md), `blackfox/harness/` |
| Research store | JSON records, source PDFs, keyword search and a local semantic index | [blackfox/db/README.md](blackfox/db/README.md) |
| 3D assets | Code-generated and baked habitat, terrain and globe assets | [blender/README.md](blender/README.md) |
| Deployment and tests | Service configuration, updates, health checks and workspace tests | [deploy/README.md](deploy/README.md), `tests/` |

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

Every change re-runs the simulation (`blackfox/design/simulator.py`, first-order sizing):
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

The *Investigations* tab ranks the 24 NASA PSI combustion investigations for five mission scenarios
(spacecraft, station, lunar base, Mars habitat, pressurized rover) and for a prevention, detection or
suppression focus (method `topic-relevance-v2`), with text search and a side-by-side comparison of two to
four investigations. The stateless `/api/research/*` backend works without an AI key.

What it shows is measured, not curated guesswork: for the 19 investigations that have measurement
envelopes in `flame/data` it shows the oxygen, pressure and airflow ranges PSI actually reported (13 give
both an oxygen and a pressure range, 16 an oxygen range; the others give flow or other conditions only, and
any missing number is shown as unknown, never filled in). The other 5 are computational studies with no
experimental envelope, and the tab says so. 13 of the 24 also have raw PSI test tables (1,755 cleaned rows)
behind the *Variables* view on `/spread.html`. The lab's *Gap map* (`GET /api/flame/gapmap`) plots the 15 of
23 envelopes that give both numbers in oxygen against pressure, lists the 8 it cannot place, and shows which
planned cabin atmospheres no experiment covered. For the
lunar and Mars habitat atmospheres (30-34 % O2 at 56.5-70.3 kPa) NASA tested liquid and gas fuels only: no
PSI experiment burned a solid material there.

Relevance is a topic match between an investigation and a mission, not a prediction of fire risk, and the
data is microgravity data: partial-gravity (Moon, Mars) gaps are shown, never hidden. The tool is for
aerospace engineers and researchers, and for professors and students learning spacecraft fire safety. It
supports one decision: which PSI experiments to read first for a mission's cabin atmosphere, and what is
still unknown and needs looking up or testing. It does not replace NASA-STD-6001 material testing.
The original implementation plan, with its current status, is in [docs/DASHBOARD_PLAN.md](docs/DASHBOARD_PLAN.md).

## Semantic source search

The agent can search original NASA PDF passages and curated research using local
MiniLM embeddings, with source filenames and page citations. The background-built SQLite
vector index and model cache live in the data directory. See
[vector database setup](blackfox/db/README.md#local-vector-database) and
`GET /api/research/vector/status`. Collected metadata keeps its keyword index.

## Questions and answers

**What problem does Black Fox address?** It helps users explore cabin fire scenarios and find
which NASA combustion investigations are relevant to a proposed mission. It also makes missing
evidence visible so that users can identify questions requiring further research or testing.

**What is measured, and what is calculated?** PSI investigation records, reported experimental
envelopes and cleaned table rows come from NASA source material. The cabin fire, spread and CFD
views calculate model outcomes for chosen inputs. A model result is an estimate, not a measurement
of the user's scenario. Follow the source links and verification status before relying on a value.

**Does an envelope mean every combination inside it was tested?** No. Reported ranges can
aggregate conditions; their overlap with an atmosphere does not prove that a particular oxygen,
pressure and airflow combination was tested. Use the Variables view and source rows for details.

**How do the rankings work?** The investigations dashboard uses explained topic and mission
bonuses. The habitat ranking separately combines condition proximity, topic, fuel and flight
status with adjustable weights. These are relevance scores for finding research, not fire-risk
probabilities. The two rankings answer different questions.

**Can microgravity results predict fire on the Moon or Mars?** They inform the investigation,
but do not establish partial-gravity fire behavior. Missing conditions and unchecked envelopes
are identified, not silently treated as zero or as proof of safety. The gap map compares
atmospheric ranges; its overlap calculation does not account for gravity.

**Does the simulation certify a material or a habitat?** No. The models are approximations for
exploration and education, not safety certification or a replacement for NASA-STD-6001 testing,
engineering analysis or validation against the original experiments. Fire is analysed inside
pressurized cabins, including cabins located on a planetary surface.

**Why use an AI agent?** It provides a conversational way to inspect scenarios, call the
simulation and search the research database. The calculations and evidence endpoints also work
without it. AI-generated explanations can be wrong; verify their claims and citations.

**Where do the data and citations come from?** The PSI data pipeline and its verification rules
are described in [flame/README.md](flame/README.md); raw tables and their manifest are in
[the PSI intake folder](blackfox/db/knowledge/raw_data/psi_combustion/README.md). The broader
research store includes curated records and original PDFs; see [its README](blackfox/db/README.md).

**How can I verify or contribute?** Install `requirements-dev.txt` and run `pytest` for the full
suite. Workspace-specific tests and interface contracts are in [CONTRIBUTING.md](CONTRIBUTING.md);
performance and visual checks are described in [tests/perf/README.md](tests/perf/README.md).
