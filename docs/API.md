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

Response 200: `{"message": Message, "notes": [{"id": 1, "text": "..."}], "scenario": FireScenario}`
(`notes` only for AI answers). `scenario` is present only when the AI changed the lab with its
`set_fire_scenario` tool during this answer (every field of the scenario, `null` = "the environment's
default"); the page applies it exactly as if the user had clicked those controls. The server stores
the `context` it receives as the visitor's current scenario, so the AI always edits what the user sees.

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
Counts summarize filtered results by primary focus; `focuses` lists every applicable safety
category and focus filters match any of them. Fundamental-only studies are grouped by fuel
phase as indirect evidence. Each row describes one PSI accession, including title, topics,
fuel, hardware, summary, source URL, focus categories, ranking reasons and conditions_note.
`oxygen_percent`, `pressure_kpa`, and `airflow_m_s` are `[min, max]` ranges or null if
unknown. Ranges span all reported envelopes and do not establish tested combinations.
`measurements_available` indicates an envelope exists, not that every field or a raw table
is available. Modeling studies without an envelope are identified explicitly.
Method `topic-relevance-v2` awards 50 baseline points, 30 for a selected matching focus,
and 20 for the scenario-specific criterion stated in the row. Sort by score then ID;
scores are topic relevance, not fire risk.

### `GET /api/research/compare`

Query: `ids` (comma-separated catalog IDs, maximum 200 characters). Returns
`{investigations, limitations}` in requested order without ranking fields. Duplicate IDs
are deduplicated. Choose 2–4 distinct IDs (422 otherwise); unknown IDs return 404.
The legacy IDs `bass`, `saffire`, `same`, `flex`, `bre`, and `cfi_g` resolve to
representative PSI investigations and retain the requested ID in the response.

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

`{"envelopes": [...], "habitats": [...], "incidents": [...], "investigationCount": 24,
"investigations": [...], "insights": {"moon-base": [...], ...}}` from `flame/data`: the oxygen / pressure / flow ranges the PSI combustion experiments covered (each
with its accession, acronym, finding and a `verified` flag), the planned habitat atmospheres
and historic cabin fire incidents. The lab draws them on the flammability map and says
whether the current atmosphere has been tested in microgravity. `investigations` is a compact list
(`accession`, `acronym`, `title`, `fuelPhase`, `earthBenefits`, `psiUrl`); `earthBenefits` is NASA's own
"potential Earth benefits" text from PSI, unmodified, which the lab shows under each covering experiment.
`insights` groups the cached, cited interpretation text by habitat ID.

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

### `GET /api/flame/sweep`

Query: `accession` (an investigation in `flame/data/investigations.json`; 404 if unknown, 422 if missing).
"How did tests from the same investigation differ, and how were they the same?" Groups the
cleaned PSI table rows of that investigation by configuration (`flame.sweep`). Returns `rows`,
`tables` and `configurations`: per configuration `config` (null when the table gives none), `rows`,
`o2_pct`, `pressure_kpa` and `flow_mps` as `[min, max]` (null when no row gives it), `unreported`
(rows that lack each value), `ignited` / `not_ignited` / `ignition_unreported`, `kinds` (`test`,
`test_day` summaries, planned `matrix` rows) and `sources`: raw table file with `row_ranges`. Row N
is CSV line N + 1. An investigation with no rows returns `configurations: []` and a `gap`
(`reason`, `reason_code`, `detail`, `raw_table`) instead of an empty table. `without_rows` lists all
11 such investigations (7 have a raw CSV with no usable test conditions, 4 are modeling or
data-analysis studies with no table), `with_rows` the 13 that have rows. The fire-spread page shows it.

### `GET /api/flame/tests`

Query: `o2_pct`, `pressure_kpa`, optional `fuel_phase` (`solid` | `liquid` | `gas` | `aerosol`),
`limit` (1–25, default 5). The individual test runs of the PSI experiment tables closest to this
atmosphere, at most two per investigation: `accession`, `experiment`, `test_id`, `fuel`, `o2_pct`,
`pressure_kpa`, `flow_mps`, `ignited`, `outcome`, `burn_time_s`, `spread_rate_mm_s`, gaps,
`pressure_known` and `source` (raw table file and row). Built from
`blackfox/db/knowledge/raw_data/psi_combustion/` by `python -m flame.ingest clean`.


