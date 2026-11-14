# HTTP API — the contract between **frontend** and **backend**

Owned jointly by the frontend and backend workspaces: change this file, `app/main.py` and
`frontend/index.html` in the **same pull request**. `tests/frontend` fails if the page calls
an endpoint that is not listed here.

All endpoints are JSON. Two cookies identify the visitor and are set automatically
(`bfx_vid` = visitor, long-term memory and design; `bfx_cid` = current conversation).

## `POST /api/chat`

Request: `{"message": "text (max 1200 chars)", "lang": "en" | "hu", "context": FireScenario | null}`

`context` is optional: the scenario open in the fire lab. The server re-runs it and gives the
agent a one-line summary (limits, margin, spread, alarm, risk), so answers refer to what the
user is looking at.

Response 200: `{"message": Message, "notes": [{"id": 1, "text": "..."}]}` (`notes` only for AI answers)

Typed commands (`show`, `select …`, `set a.b = c`, `add …`, `remove …`, `new …`, `help`) are
answered instantly by the simulation workspace, without the AI and without the rate limit.

Errors: `{"error": code}` with 400 `empty` / `too_long`, 429 `rate_limited`, 503 `unavailable`.

## `GET /api/session`

`{"messages": [Message, ...], "notes": [...], "max_message": 1200}` — the current conversation (last 40).

## `GET /api/design`

`{"snapshot": "plain text"}` — the visitor's current design simulation.

## `POST /api/session/new`

Starts a new conversation (design and long-term notes are kept). `{"ok": true}`

## `POST /api/memory/forget`

Deletes the visitor's notes, design and current conversation. `{"ok": true}`

## `GET /healthz`, `GET /api/health`

`{"ok": true, "commit": "abc1234", ...}` — used by the deploy script.

## Message

```json
{"role": "user" | "assistant",
 "text": "raw text (Markdown for the assistant)",
 "html": "assistant only: safe, escaped HTML rendering of text",
 "snapshot": "assistant only: plain-text simulation snapshot if the design changed, else \"\"",
 "model": "assistant only", "tools": [{"name": "set_design_value", "ms": 3, "error": false}]}
```

## Fire-safety lab

All numbers come from `blackfox/physics/fire.py`, which reads the curated NASA records in
`blackfox/db/knowledge/curated/` (each with its NTRS source).

### `GET /api/fire/catalog`

Environments (`leo`, `lunar_orbit`, `moon`, `mars`, `earth`: label in hu/en, gravity, default
cabin atmosphere, reference facts), materials (label, form, measured NASA-STD-6001 MOC points,
heat of combustion, toxic products, colour), locations in the HAB-01 module (label, 3D anchor in
metres, enclosure, default material), ventilation layout, input limits and reference values
(CO SMAC, nominal ventilation band, smoke alarm threshold).

### `POST /api/fire/simulate`

Request `FireScenario` (every field optional):

```json
{"environment": "leo", "location": "avionics_rack", "material": "ultem",
 "pressure_kpa": 101.4, "o2_pct": 21, "temp_c": 22, "vent_cm_s": 12,
 "auto_vent_shutdown": true, "suppression": "none" | "co2" | "water_mist", "response_s": 60}
```

Omitted atmosphere values use the environment's defaults; an omitted material uses the
location's typical material. 422 for values out of range, 400 for an unknown material.

Response: `inputs`, `atmosphere`, `flammability` (MOC at 1 g, gravity/flow/temperature
corrections, effective limit, oxygen margin, buoyant/forced/effective flow), `flame` (spread
rates, temperature, soot index, elongation for the 3D flame), `timeline` (alarm, response,
extinction, CO SMAC times and an `events` list), `peaks`, `series` (every 2 s: heat release,
burning front, flame strength, cabin O2, CO, smoke at source and detector, pressure rise,
ventilation state, margin), `map` (oxygen-pressure curves for the chart), `verdict`
(`low` | `elevated` | `high` | `critical`), `knowledge` (curated record ids used) and
`assumptions`.

### `GET /api/fire/evidence`

Query: `environment`, `material` (e.g. `?environment=leo&material=nomex`).


`{"records": [...]}`: curated records first, then matching records of the research database,
filtered to fire-relevant topics (combustion, habitats, life support, materials, fluids);
biology, health, radiation and propulsion records are left out.

### `GET /api/research`, `GET /api/research/{slug}`

Research records for the evidence drawer: `?gravity=&topic=` lists up to 100 records; a slug
returns one full record (summary, details, facts, sources). 404 for an unknown slug.
