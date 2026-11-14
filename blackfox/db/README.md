# Research database (the information the AI can use)

The agent's knowledge base is a folder of plain **JSON text files**: `blackfox/db/knowledge/`.
The metadata stays in JSON; original source PDFs are kept separately under `pdf-s/`.
Generated search databases live in the runtime data directory. The metadata covers three gravity
environments:

| Folder | Environment | Gravity |
|---|---|---|
| `moon/` | the Moon | 1.62 m/s² (0.165 g) |
| `mars/` | Mars | 3.71 m/s² (0.378 g) |
| `zero_g/` | 0 g: microgravity / weightlessness (orbit, free fall) | about 0 |

## How it is sorted

```
knowledge/
  index.json                         table of contents: counts per gravity and topic, file list, field descriptions
  curated/*.json                     hand-written, checked records with numeric facts (edit these by hand)
  moon/<topic>-001.json, -002 ...    collected records, one file series per topic
  mars/<topic>-001.json ...
  zero_g/<topic>-001.json ...
```

Sorted by **gravity → topic → year (newest first) → title**. A record that is about several
environments is stored once, in the folder of its strongest match, and lists all of them in
its `gravity` field. Topics are things like `habitats_structures`, `isru_regolith_dust`,
`life_support`, `combustion_fire`, `fluids_heat_transfer`, `human_health`, `radiation`,
`power_thermal`, `propulsion_landing_mobility` (full list with counts: `index.json`).

Every file is ordinary JSON, written with **one record per line**, and no file is larger than
about 10 MB:

```json
{"format": "blackfox-knowledge/1", "gravity": "moon", "topic": "habitats_structures", "count": 2, "records": [
{"id": "ntrs-20240008927", "title": "Seismic Assessment of a Long-Term Lunar Habitat", "kind": "report", "year": 2024, "gravity": ["moon"], "topic": "habitats_structures", "summary": "...", "keywords": ["..."], "authors": ["..."], "org": "Marshall Space Flight Center", "source": "NASA Technical Reports Server", "url": "https://ntrs.nasa.gov/citations/20240008927"},
{"id": "...", "title": "..."}
]}
```

## Where the records come from

`python -m blackfox.collect` (code in `blackfox/collect/`) downloads text from public sources
and keeps only what is clearly about the Moon, Mars or 0 g:

| Source | What |
|---|---|
| NASA Technical Reports Server | NASA reports and conference papers (abstracts) |
| Europe PMC (includes PubMed) | journal articles (abstracts) |
| arXiv | preprints (abstracts) |
| NASA TechPort | NASA technology projects (description, benefits, readiness level) |
| NASA Open Science Data Repository | space-biology studies |
| Wikipedia | overview articles (intro text, CC BY-SA 4.0) |

Each record keeps its `source` and `url`, so the agent can say where a statement comes from.

```bash
python -m blackfox.collect harvest      # download raw records (can be interrupted and continued)
python -m blackfox.collect build        # classify, remove duplicates, sort, write knowledge/
python -m blackfox.collect all          # both
```

`--max-gb` (default 30) is the hard size limit: if the database would grow past it, the least
relevant records are left out.

## Full texts (optional, on the server)

The files in git hold summaries. The complete report and article texts are much bigger, so they
are not in git; download them on the server into the data folder:

```bash
python -m blackfox.collect --max-gb 30 fulltext
```

It stops when database + full texts reach `--max-gb`, and continues where it stopped if run
again. Texts are stored as JSON too (`<data dir>/fulltext/<gravity>/text-0001.json`).

## How the AI reads it

The agent never loads whole files. It calls tools (`blackfox/tools/research.py`):

| Tool | Does |
|---|---|
| `research_stats` | what the database holds: counts per gravity, topic, kind, source |
| `search_research(query, gravity, topic, kind)` | finds the best matching records, returns short summaries |
| `get_research(slug)` | one full record: summary, keywords, authors, year, url, facts |
| `read_research_text(slug, page, find)` | reads a stored full text page by page, or jumps to a phrase |
| `list_research(gravity, topic, kind)` | browses a topic, newest first |
| `add_research`, `add_research_fact` | adds an unverified "community" record or fact |

To answer a search in milliseconds, `blackfox/db/json_store.py` keeps a **search index** in the
data folder (`knowledge_index.sqlite`). It only stores the words and where each record sits
(file + byte position); the record itself is always read from the JSON file. The index is built
automatically on first start and again whenever the JSON files change. It is safe to delete.

Records the AI or users add at runtime go to `<data dir>/community.json` and are marked
`community` (unverified); files in git are never changed by the running site.

## Changing the data

- Fix or add a checked fact: edit a file in `knowledge/curated/` and push.
- Refresh the collected records: run `python -m blackfox.collect all` and commit `knowledge/`.
- Tests: `pytest tests/agent/test_research.py`.

## Local vector database

Original NASA PDFs now live under `knowledge/pdf-s/` (with provenance in `SOURCES.md`).
They are inputs, separate from the JSON metadata. The service builds a local dense-vector
index for those PDFs and `curated/*.json`, using FastEmbed's
`sentence-transformers/all-MiniLM-L6-v2` ONNX model and normalized cosine similarity.
The larger collected metadata catalog continues to use SQLite FTS search.

- PDF pages are split into 1,200-character passages with 200-character overlap. Results retain
  source filename and 1-based PDF page; curated summaries retain their record ID.
- `<data dir>/research_vectors.sqlite` holds passage metadata, text and float32 vectors.
  `<data dir>/embedding_models/` caches the downloaded model. Neither is committed.
- The first build downloads a public model; subsequent cached runs need no embedding API or key.
  The app builds in a background thread, and SHA-256 source fingerprints avoid unnecessary builds.
  Unchanged passage embeddings are reused when documents are added or edited.
  Atomic replacement and a process lock preserve a complete index during rebuilds.
- `search_research` includes a separate `passages` ranking when ready; the agent can call
  `search_research_semantic` explicitly without gravity filters to find original PDF passages.
  We do not infer a paper's gravity from its filename. PDF passages have unknown gravity,
  so an explicit gravity filter excludes them. Kind filters stay in keyword search.
- Set `BLACKFOX_VECTOR_ENABLED=false` to disable this feature. Keyword search stays available.
  Check `/api/research/vector/status`; 503 from vector search means it is not available yet.
- This model is English-focused. For Hungarian questions, the agent should formulate its
  research query in English and provide the final explanation in the selected reply language.
- Image-only PDF pages need future OCR and are reported in `empty_pages`. Parser-limit
  failures are listed separately in `extraction_errors` with source filename and page. Similarity is not
  a scientific confidence score; source passages still need interpretation and validation.

```bash
python -m blackfox.db.vector_store build
python -m blackfox.db.vector_store status
python -m blackfox.db.vector_store search "carbon dioxide extinguishing liquid fuel flames"
```

The systemd web service has a 1 GB memory cap to accommodate ONNX inference and PDF parsing.
Tests inject embeddings to check persistence, cosine ranking, filters, page citations,
rebuild invalidation and failure recovery without model downloads.
