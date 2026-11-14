# HTTP API — the contract between **frontend** and **backend**

Owned jointly by the frontend and backend workspaces: change this file, `app/main.py` and
`frontend/index.html` in the **same pull request**. `tests/frontend` fails if the page calls
an endpoint that is not listed here.

All endpoints are JSON. Two cookies identify the visitor and are set automatically
(`bfx_vid` = visitor, long-term memory and design; `bfx_cid` = current conversation).

## `POST /api/chat`

Request: `{"message": "text (max 1200 chars)", "lang": "en" | "hu"}`

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
