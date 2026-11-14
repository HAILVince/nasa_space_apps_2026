"""Rows for comparing 2-4 investigations side by side.

One row per attribute, one value per investigation, and a flag saying whether the values
differ so the page can highlight them. An investigation with several envelopes gets its
values joined with "; " in envelope order, so the nth oxygen range belongs to the nth fuel.
A range is written "21–40", a single value "101.3", anything unknown "—".
"""

from .models import Envelope, Investigation

BLANK = "—"
OBJECTIVE_MAX = 300
ATTRIBUTES = ("Objective", "Fuel phase", "Fuel / geometry", "O₂ %", "Pressure (kPa)", "Flow (m/s)", "Diluent",
              "Gravity", "Hardware", "Sensors", "Measured", "Key finding", "Flight / ground")


def _range(r: tuple[float, float] | None) -> str:
    if r is None:
        return BLANK
    return f"{r[0]:g}" if r[0] == r[1] else f"{r[0]:g}–{r[1]:g}"


def _join(values: list[str]) -> str:
    """Keep the order, write a repeated value once ("micro; micro" tells the reader nothing)."""
    seen = list(dict.fromkeys(values))
    return "; ".join(values if len(seen) > 1 else seen) or BLANK


def _listed(groups: list[list[str]]) -> str:
    return ", ".join(dict.fromkeys(x for group in groups for x in group)) or BLANK


def _short(text: str) -> str:
    if len(text) <= OBJECTIVE_MAX:
        return text or BLANK
    return text[:OBJECTIVE_MAX].rsplit(" ", 1)[0] + "…"


def _column(inv: Investigation, envs: list[Envelope]) -> list[str]:
    return [
        _short(inv.objectives),
        inv.fuel_phase,
        _join([f"{e.fuel}, {e.geometry}" for e in envs]),
        _join([_range(e.o2_pct) for e in envs]),
        _join([_range(e.pressure_kpa) for e in envs]),
        _join([_range(e.flow_mps) for e in envs]),
        _join([e.diluent or BLANK for e in envs]),
        _join([e.gravity for e in envs]),
        ", ".join(sorted(inv.hardware)) or BLANK,      # sorted: PSI lists the same rig in different orders
        _listed([e.sensors for e in envs]),
        _listed([e.measured for e in envs]),
        _join([e.key_finding for e in envs]),
        inv.kind,
    ]


def compare_rows(investigations: list[Investigation], envelopes) -> list[dict]:
    columns = [_column(inv, [e for e in envelopes if e.accession == inv.accession]) for inv in investigations]
    rows = []
    for n, attribute in enumerate(ATTRIBUTES):
        values = [column[n] for column in columns]
        rows.append({"attribute": attribute, "values": values, "differs": len(set(values)) > 1})
    return rows


def shared_hardware(investigations: list[Investigation]) -> list[str]:
    """Hardware every selected investigation used, e.g. CIR and MDCA for FLEX, FLEX-2 and CFI."""
    common = set.intersection(*(set(i.hardware) for i in investigations)) if investigations else set()
    return sorted(common)
