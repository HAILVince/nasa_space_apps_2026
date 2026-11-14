"""Simulation workspace: the habitat/spacecraft design engine.

  simulator.py  design JSON -> simulate() -> checks / totals / per-part results; report() text
  store.py      per-visitor current design (SQLite)
  commands.py   typed commands (show, select, set, add, remove, new, help)

Public interface (used by the backend and the agent tools - keep these stable):
  new_design, add_part, set_value, simulate, report, PART_TYPES, LOCATIONS, MATERIALS,
  get_store, load_or_new, run_command
"""

from .commands import run_command  # noqa: F401
from .simulator import (LOCATIONS, MATERIALS, PART_TYPES, add_part, new_design, report,  # noqa: F401
                        set_value, simulate)
from .store import DesignStore, get_store, load_or_new  # noqa: F401
