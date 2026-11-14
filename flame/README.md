# Flame in Freefall

Our entry for the Space Apps challenge of the same name. It takes the 24 combustion
investigations in NASA's PSI database and answers, for one cabin atmosphere at a time:
which experiments apply, what they found, and where nobody has tested yet.

This folder is the Python side: the dataset and everything computed from it. The pages
live in `frontend/flame/`, the HTTP routes in `app/flame_routes.py`.

| Path | What |
|---|---|
| `models.py` | the data contract: investigations, envelopes, habitats, incidents (pydantic) |
| `data/` | the JSON dataset, committed |
| `ingest/` | offline scripts that build `data/` from PSI and NTRS |
| `assistant/` | the fire-safety AI: tools, prompt, cached answers |
| `sim/` | the cabin-fire Monte Carlo |

Only `models.py` exists so far. The rest lands step by step, see `docs/flame/FABLE_PROMPT.md`.

Three rules hold everywhere:

- Pressure is stored in kPa. The pages show kPa and psi.
- An envelope nobody has checked against its source is shown as "not yet checked". It is never hidden.
- Fire is only analysed inside pressurized cabins. Nothing burns on the lunar surface.

Test: `pytest tests/flame`
