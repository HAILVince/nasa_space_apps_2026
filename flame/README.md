# Flame in Freefall

Our entry for the Space Apps challenge of the same name. It takes the 24 combustion
investigations in NASA's PSI database and answers, for one cabin atmosphere at a time:
which experiments apply, what they found, and where nobody has tested yet.

This folder is the Python side: the dataset and everything computed from it. The pages
live in `frontend/spread.html` and `frontend/js/spread.js`; the HTTP routes are in
`app/main.py` under `/api/flame/*`.

| Path | What |
|---|---|
| `models.py` | the data contract: investigations, envelopes, habitats, incidents (pydantic) |
| `calc.py`, `data.py`, `units.py` | calculations, dataset access and unit conversions |
| `rank.py`, `search.py`, `sweep.py` | investigation ranking, search and test sweeps |
| `data/` | the JSON dataset, committed |
| `ingest/` | offline scripts that build `data/` from PSI and NTRS |

Three rules hold everywhere:

- Pressure is stored in kPa. The pages show kPa and psi.
- An envelope nobody has checked against its source is shown as "not yet checked". It is never hidden.
  `python -m flame.ingest verify` does the check: every O2 / pressure / flow range must equal its PSI
  table or carry a quoted NASA document (NTRS); a value no source gives is left empty and listed in
  `notReported` with the reason (shown as "not reported" in the lab). Run it after `clean` or `extract`.
- Fire is only analysed inside pressurized cabins. Nothing burns on the lunar surface.

## Raw PSI tables -> clean rows

`python -m flame.ingest clean` reads the experiment tables exactly as downloaded from PSI
(`blackfox/db/knowledge/raw_data/psi_combustion/tables/`, never edited) and writes:

- `data/psi_tests.json`: one validated `PsiTest` per usable table row (1,755 rows from 13 investigations),
  each pointing back to its file and row; `calc.nearest_tests()` and `GET /api/flame/tests` read it;
- `data/clean/psi_tests.csv`: the same rows as a flat table;
- `data/clean/psi_conditions.csv`: per investigation and configuration, the O2 / pressure / flow
  ranges actually in the tables (and which tables have no numeric conditions);
- `data/envelopes.json`: envelope ranges replaced by these raw-table ranges where the table has them.

Units: mole fraction -> % O2, atm / bar / mmHg -> kPa, cm/s -> m/s. Obvious transcription errors
(final O2 of 1.6 %, negative flow, 0 mmHg) are left out of the ranges and written into `notes`.
Re-run it after `extract`: the LLM step writes ranges from papers, the raw tables win where they have numbers.

Test: `pytest tests/flame`
