# Workspace 3 — Simulation (design engine)

| File | What |
|---|---|
| `simulator.py` | part types, locations, materials, `simulate()` and the text `report()` |
| `store.py` | each visitor's current design in SQLite (`designs.db`) |
| `commands.py` | typed commands: show, select, set, add, remove, new, help |

Pure Python, no SI, no web: you can work on it with only `pytest tests/simulation`.

## Design format (contract — the agent tools and backend rely on it)

```json
{"name": "Lunar base", "kind": "habitat | spacecraft",
 "environment": {"location": "moon_south_pole", "crew": 6, "mission_days": 300, "cabin_pressure_kpa": 70.3},
 "parts": {"hab": {"type": "pressurized_module", "radius_m": 2.0, "...": "..."}},
 "selected": "hab"}
```

`simulate(design)` returns `{"parts": {name: results}, "totals": {...}, "checks": [{"check", "status": OK|WARN|FAIL, "detail"}]}`.

## Adding things

- **New part type:** add it to `PART_TYPES` (about + defaults) and a branch in `simulate()`;
  add a test. The agent sees it automatically through `design_catalog`.
- **New location / material:** add a row to `LOCATIONS` / `MATERIALS`.
- **New check:** add a `check(...)` call in `simulate()`.

Keep the exported names in `__init__.py` stable; renaming one breaks the backend and agent.
