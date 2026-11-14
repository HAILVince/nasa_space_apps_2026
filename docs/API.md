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
A 503 also carries `"reason"`: `no_key`, `auth` (the AI API rejected the site's key), `unreachable`
(the AI API is not running) or `busy` (rate limits, model errors). The page shows a different
message for each.

## `GET /api/ai/status`

`{"ok": true, "loopback": true, "key_set": true, "reachable": true, "authorized": true, "keyless": false,
"model": "...", "problem": ""}` — whether the AI behind the chat works right now, without sending a
chat message. `problem` is empty or one of the reasons above; `keyless` is true when the local AI API
is being called without the key. The key itself is never returned. Cached for 15 seconds.

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

(The fixed paths `scenarios`, `dashboard` and `compare` below are matched first; any other
slug is a knowledge-base record.)

Research records for the evidence drawer: `?gravity=&topic=` lists up to 100 records; a slug
returns one full record (summary, details, facts, sources). 404 for an unknown slug.

## Research dashboards

Research endpoints are stateless and require no AI key or visitor cookies.

### `GET /api/research/scenarios`

Returns `scenarios: [{id, label}]` and `focuses`. Scenario IDs: `spacecraft`, `station`,
`lunar_base`, `mars_habitat`, `rover`. Focus IDs: `all`, `prevention`, `detection`, `suppression`.

### `GET /api/research/dashboard`

Query: `scenario` (default `spacecraft`), `focus` (default `all`), `q` (case-insensitive
substring search, maximum 200 characters). Invalid values return 422.
Returns `{scenario, focus, investigations, total, counts, method, limitations, source_url}`.
Counts summarize the filtered results by prevention, detection and suppression.
Each investigation includes `id`, `title`, `focus`, `fuel`, `hardware`, `summary`, `gravity`,
`source_url`, `evidence_type`, `measurements_available`, `oxygen_percent`, `pressure_kpa`,
`airflow_m_s`, `relevance_score` and `ranking_reasons`. Unknown conditions are JSON null.
Method `topic-relevance-v1`: 50 for direct fire-safety relevance, 30 for an explicitly
selected focus, and 20 for scenario matching as explained in each row. Sort descending by
score, then ascending by ID. Scores are topic relevance, not estimated fire risk.
The catalog groups experiment families and summarizes the supplied NASA challenge brief;
it does not claim PSI measurement ingestion or AI-generated interpretation.

### `GET /api/research/compare`

Query: `ids` (comma-separated catalog IDs, maximum 200 characters). Returns
`{investigations, limitations}` in requested order without ranking fields. Duplicate IDs
are deduplicated. Choose 2–4 distinct IDs (422 otherwise); unknown IDs return 404.

## `GET /api/research/vector/status`

Returns `enabled`, `ready`, `building`, `model`, `error`, and `scope`. A built index also
reports `passages`, `documents`, `empty_pages`, `extraction_errors` (source/page/type),
and its source-content `signature`.
The index covers original PDFs and curated summaries; collected JSON metadata retains
keyword search. Ready means a complete index for this model exists; `building` may indicate
that a replacement is being generated. An old complete index remains readable on rebuild failure.

## `GET /api/research/vector/search`

Query: `q` (1–2000 characters), `limit` (1–25, default 6). Returns `{count, results}`.
Each result has `id`, `title`, `text`, `source` (repository-relative to the knowledge folder),
`page` (1-based PDF page or null for curated summaries), `evidence_type`, `gravity`, `topic`,
and cosine `similarity`. Curated results also include `slug`. Similarity is retrieval relevance,
not confidence in a scientific claim. Blank/unextractable PDF pages are counted, not OCRed.
503 with `error` when disabled, not yet built, or model loading fails; 422 for invalid inputs.

## Flame in Freefall dataset

### `GET /api/flame/context`

`{"envelopes": [...], "habitats": [...], "incidents": [...], "investigations": 24}` from
`flame/data`: the oxygen / pressure / flow ranges the PSI combustion experiments covered (each
with its accession, acronym, finding and a `verified` flag), the planned habitat atmospheres
and historic cabin fire incidents. The lab draws them on the flammability map and says
whether the current atmosphere has been tested in microgravity.

### `GET /api/flame/materials`

`{"materials": ["mylar_g", "nomex_ht90_40", "pmma", "ultem_1000"]}`: materials with measured
limits (Olson & Ferkul 2012 Table I; PMMA from LUCI). The fire-spread page (`frontend/spread.html`)
uses the two endpoints below for its "Calculator check".

### `GET /api/flame/check`

Query: `material_id`, `o2_pct` (0–100), `pressure_kpa` (0–200), `gravity` (`micro` | `lunar` |
`martian` | `earth`). Returns `measured_limit_pct`, `limit_basis`, `margin_pct`,
`margin_range_pct` (the low end includes the low-pressure correction), `pressure_may_change_verdict`,
`verdict` (`above_measured_limit` | `near_measured_limit` | `below_measured_limit`), `caveats`
and `sources`. 404 for a material without measured limits; 422 for invalid values.

### `GET /api/flame/coverage`

Query: `o2_pct`, `pressure_kpa`, optional `fuel_phase` (`solid` | `liquid` | `gas`). Returns
`counts` by status (`inside`, `near`, `partial_overlap`, `partial_near`, `outside`, `no_numbers`),
`envelopes` (PSI investigation, gravity, O2 and pressure ranges, status, gaps),
`solid_fuel_covered`, `max_solid_o2_tested_pct` and `note`.
