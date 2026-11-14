"""Variables: how did tests from the same investigation differ, and how were they the same?

sweep(accession) groups the cleaned rows of one PSI investigation (flame/data/psi_tests.json) by
configuration and gives, per configuration, the oxygen / pressure / flow ranges, the row count and
how many rows ignited, with the raw table file and row numbers each group came from.

The route (app/main.py GET /api/flame/sweep) and any agent tool call this; nothing here re-reads the
raw CSVs or re-runs the ingestion. An investigation with no rows is not an empty table: its gap says
why (gaps()). Reasons come from the cleaning step's own list (flame.ingest.clean_tables.NO_CONDITIONS).
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from . import data
from .ingest.clean_tables import NO_CONDITIONS, RAW

NOTE = ("Rows of the PSI experiment tables as downloaded, cleaned by flame/ingest/clean_tables.py (blank and "
        "non-test lines dropped). Row numbers count data rows under the header: row N is line N + 1 of the "
        "CSV. A range is the lowest and highest value any row gives; unreported counts the rows whose table "
        "does not give that value. Microgravity rows say nothing direct about lunar or Martian gravity.")


def _range(ranges: list) -> list[float] | None:
    vals = [x for r in ranges if r for x in r]
    return [round(min(vals), 3), round(max(vals), 3)] if vals else None


def _spans(rows: list[int]) -> list[list[int]]:
    """[1, 2, 3, 7, 8] -> [[1, 3], [7, 8]]"""
    out: list[list[int]] = []
    for n in sorted(rows):
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return out


def _group(config: str | None, rows: list) -> dict:
    by_table = defaultdict(list)
    for t in rows:
        by_table[t.table].append(t.source_row)
    kinds: dict[str, int] = defaultdict(int)
    for t in rows:
        kinds[t.kind] += 1
    return {
        "config": config, "rows": len(rows),
        "o2_pct": _range([t.o2_pct for t in rows]),
        "pressure_kpa": _range([t.pressure_kpa for t in rows]),
        "flow_mps": _range([t.flow_mps for t in rows]),
        "unreported": {"o2_pct": sum(t.o2_pct is None for t in rows),
                       "pressure_kpa": sum(t.pressure_kpa is None for t in rows),
                       "flow_mps": sum(t.flow_mps is None for t in rows)},
        "ignited": sum(t.ignited is True for t in rows),
        "not_ignited": sum(t.ignited is False for t in rows),
        "ignition_unreported": sum(t.ignited is None for t in rows),
        "kinds": dict(kinds),
        "sources": [{"table": tb, "row_ranges": _spans(nums), "rows": len(nums)} for tb, nums in sorted(by_table.items())],
    }


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _gap(acc: str) -> dict:
    """Why an investigation has no grouped rows."""
    inv = data.get_investigation(acc)
    table = next(iter(sorted(RAW.glob(f"{acc}_*.csv"))), None) if RAW.is_dir() else None
    detail = NO_CONDITIONS.get(acc)
    if detail:
        code, reason = "no_conditions", f"The raw table gives no test conditions to group: {detail}"
    elif inv and inv.kind == "ground":
        code, reason = "modeling_study", "Modeling or data-analysis study, no experiment table"
    else:
        code, reason = "no_table", "No experiment table in the PSI download"
    return {"accession": acc, "acronym": inv.acronym if inv else acc, "reason": reason, "reason_code": code,
            "detail": detail, "detail_code": _slug(detail) if detail else None,
            "raw_table": table.name if table else None}


def gaps() -> list[dict]:
    """Every investigation without grouped rows, with its reason."""
    have = {t.accession for t in data.get_psi_tests()}
    return [_gap(i.accession) for i in data.get_investigations() if i.accession not in have]


def sweep(accession: str) -> dict | None:
    """All configurations one investigation tested, or None for an accession not in investigations.json."""
    inv = data.get_investigation(accession)
    if inv is None:
        return None
    rows = list(data.get_psi_tests(accession))
    by_config = defaultdict(list)
    for t in rows:
        by_config[t.config].append(t)
    configs = [_group(c, by_config[c]) for c in sorted(by_config, key=lambda c: (c is None, c or ""))]
    return {"accession": accession, "acronym": inv.acronym, "title": inv.title, "psi_url": inv.psi_url,
            "rows": len(rows), "tables": sorted({t.table for t in rows}), "configurations": configs,
            "gap": None if rows else _gap(accession),
            "with_rows": sorted({t.accession for t in data.get_psi_tests()}, key=lambda a: int(a[4:])),
            "without_rows": gaps(), "note": NOTE}
