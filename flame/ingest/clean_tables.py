"""Clean the raw PSI experiment tables into calculator rows.

Input (never edited): blackfox/db/knowledge/raw_data/psi_combustion/tables/*.csv, bytes as
downloaded from psi.nasa.gov. Output:

- flame/data/psi_tests.json      one validated PsiTest per usable table row (what calc.py reads)
- flame/data/clean/psi_tests.csv the same rows as a flat table for people and pandas
- flame/data/clean/psi_conditions.csv one line per investigation/configuration: how many rows,
                                      the O2 / pressure / flow ranges actually in the tables
- flame/data/envelopes.json      O2, pressure and flow ranges replaced by the raw-table ranges
                                  where the table has them (provenance says so)

Each table has its own small adapter because every table has its own columns and spelling.
Unit rules: mole fractions -> % O2, atm / bar / mmHg -> kPa, cm/s -> m/s. Values that are
clearly transcription errors are kept out of the ranges and written into `notes`.

Run: python -m flame.ingest clean
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from .. import data
from ..models import Envelope, PsiTest

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "blackfox" / "db" / "knowledge" / "raw_data" / "psi_combustion" / "tables"
CLEAN = data.DATA / "clean"
KPA_PER_ATM, KPA_PER_BAR, KPA_PER_MMHG = 101.325, 100.0, 0.133322
NUM = re.compile(r"-?\d+(?:\.\d+)?")


# ---- parsing helpers ---------------------------------------------------------------------
def nums(cell: str | None) -> list[float]:
    """All numbers in a cell: '~ 22.1' -> [22.1]; '21.5 - 21.7' -> [21.5, 21.7]; '0.17; 0.21' -> 2."""
    text = re.sub(r"[A-Za-z]\d+", " ", (cell or "").replace(",", "."))   # O2, CO2, C2H4 are not numbers
    return [float(x) for x in NUM.findall(text)]


def num(cell: str | None) -> float | None:
    found = nums(cell)
    return found[0] if found else None


def rng(values, scale: float = 1.0, digits: int = 3):
    vals = [round(v * scale, digits) for v in values if v is not None]
    return [min(vals), max(vals)] if vals else None


def pct(fraction_or_pct: float | None) -> float | None:
    """0.21 -> 21.0; 21 -> 21.0 (tables mix mole fractions and percent); '3400%' -> 34.0
    (a mole fraction 0.34 that a spreadsheet formatted as percent twice)."""
    if fraction_or_pct is None:
        return None
    if fraction_or_pct > 100:
        return round(fraction_or_pct / 100, 3)
    return round(fraction_or_pct * 100, 3) if fraction_or_pct <= 1 else round(fraction_or_pct, 3)


def yes_no(cell: str | None) -> bool | None:
    c = (cell or "").strip().lower()
    return True if c in ("yes", "y", "flash") else False if c in ("no", "n") else None


def read(name: str) -> list[dict]:
    raw = (RAW / name).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:          # PSI-69 FLEX is Windows-1252 (en dash in a header)
        text = raw.decode("cp1252")
    rows = list(csv.DictReader(text.splitlines()))
    squash = lambda x: re.sub(r"\s+", " ", x or "").strip()     # '2 cm   wide' -> '2 cm wide'
    return [{squash(k): squash(v) for k, v in r.items()} for r in rows]


def col(row: dict, *starts: str) -> str:
    """Value of the first column whose (stripped) name starts with one of `starts`."""
    for s in starts:
        for k, v in row.items():
            if k.lower().startswith(s.lower()):
                return v
    return ""


# ---- one adapter per table ----------------------------------------------------------------
def _saffire(name: str, accession: str, experiment: str) -> list[dict]:
    out, material = [], ""
    for i, r in enumerate(read(name), 1):
        sample = col(r, "Sample Number")
        if not re.match(r"^(S\d+|2-\d+)$", sample):
            continue                                   # flow-visualisation and note rows
        material = col(r, "Material") or material      # SAFFIRE-II leaves repeats blank
        o2 = nums(col(r, "Percent O2"))
        flow = num(col(r, "Air Flow"))
        burn = col(r, "Burn Time")
        base = dict(accession=accession, experiment=experiment, table=name, source_row=i, test_id=sample,
                    kind="test", config=col(r, "Flow Direction", "Direction").lower() or None,
                    fuel=material, fuel_phase="solid", flow_mps=rng([flow], 0.01) if flow else None)
        notes = []
        if "insignificant" in burn.lower():
            notes.append("burn time 'Insignificant'")
        micro = dict(base, gravity="micro", o2_pct=rng(o2), pressure_kpa=None,
                     burn_time_s=None if not nums(burn) else nums(burn)[0])
        spread = col(r, "?-g Spread")
        if spread and "mm/s" in spread:
            micro["spread_rate_mm_s"] = num(spread)
        length = col(r, "?-g Burn Length")
        if length:
            micro["ignited"] = not length.replace(" ", "").startswith("~0")
            notes.append(f"0 g burn length: {length}")
        micro["notes"] = "; ".join(notes + ["pressure not in the table (Cygnus cabin)"])
        out.append(micro)
        one_g = col(r, "1-g Burn Length")
        if one_g:                                      # the same sample burned on the ground
            rate = col(r, "1-g Spread Rate")
            out.append(dict(base, gravity="earth", test_id=sample + "-1g", flow_mps=None,
                            ignited=not one_g.replace(" ", "").startswith("~0"),
                            outcome="acceleratory spread" if "accel" in rate.lower() else None,
                            spread_rate_mm_s=num(rate) if "mm/s" in rate else None,
                            notes=f"1 g burn length: {one_g}; oxygen and pressure not in the table (ground air)"))
    return out


def saffire_1(): return _saffire("PSI-98_saffire-1.csv", "PSI-98", "SAFFIRE-I")
def saffire_2(): return _saffire("PSI-99_saffire-2.csv", "PSI-99", "SAFFIRE-II")
def saffire_3(): return _saffire("PSI-100_saffire-3.csv", "PSI-100", "SAFFIRE-III")


def bass_ii():
    out = []
    for i, r in enumerate(read("PSI-25_bass-ii.csv"), 1):
        o2_in, o2_out = num(col(r, "Calibrated  initial O2", "Calibrated initial O2")), num(col(r, "Calibrated final O2"))
        if o2_in is None:
            continue
        notes = []
        if o2_out is not None and abs(o2_out - o2_in) > 5:
            notes.append(f"final O2 {o2_out} looks like a transcription error; left out of the range")
            o2_out = None
        out.append(dict(accession="PSI-25", experiment="BASS-II", table="PSI-25_bass-ii.csv", source_row=i,
                        test_id=col(r, "Test #"), kind="test", fuel=col(r, "Fuel Sample Material"),
                        fuel_phase="solid", gravity="micro", o2_pct=rng([o2_in, o2_out]), diluent="N2",
                        notes="; ".join(notes + ["flow given as fan setting only; pressure not in the table"])))
    return out


def _flow_only(name, accession, experiment, phase, fuel_col, flow_col, id_col, extra=None):
    out = []
    for i, r in enumerate(read(name), 1):
        flow = num(col(r, flow_col))
        if flow is None:
            continue
        row = dict(accession=accession, experiment=experiment, table=name, source_row=i,
                   test_id=col(r, id_col) or str(i), kind="test", fuel=col(r, fuel_col),
                   fuel_phase=phase, gravity="micro", flow_mps=rng([flow], 0.01, 4) if flow >= 0 else None)
        row |= extra(r) if extra else {}
        if flow < 0:
            row["notes"] = f"negative flow {flow} cm/s in the table; left out. " + row.get("notes", "")
        out.append(row)
    return out


def same():
    return _flow_only("PSI-102_same.csv", "PSI-102", "SAME", "aerosol", "Sample Material", "Air Flow", "Sample #",
                      lambda r: {"notes": f"weight loss rate {col(r, 'Weight loss')} mg/min"})


def same_r():
    return _flow_only("PSI-101_same-r.csv", "PSI-101", "SAME-R", "aerosol", "Sample Type", "Inlet velocity",
                      "SAME Test #", lambda r: {"notes": col(r, "Description")})


def spice():
    return _flow_only("PSI-107_spice.csv", "PSI-107", "SPICE", "gas", "Fuel", "Air Rate", "GMT ignition",
                      lambda r: {"config": "coflow jet", "notes": f"fuel rate {col(r, 'Fuel Rate (mg/s)')} mg/s"})


def flex():
    out = []
    for i, r in enumerate(read("PSI-69_flex.csv"), 1):
        p, o2 = num(col(r, "Ambient pressure")), num(col(r, "O initial", "O2 initial"))
        if o2 is None:
            continue
        notes, kpa = [], None
        if p is not None and p > 10:
            kpa = rng([p], KPA_PER_MMHG, 2)
        elif p is not None:
            notes.append(f"pressure {p} mmHg is not a physical cabin value; left out")
        co2, he = num(col(r, "CO initial", "CO2 initial")) or 0, num(col(r, "He initial")) or 0
        end = col(r, "Test end").lower()
        out.append(dict(accession="PSI-69", experiment="FLEX", table="PSI-69_flex.csv", source_row=i,
                        test_id=col(r, "FLEX Identifier") or col(r, "FLEX Test"), kind="test", fuel=col(r, "Fuel"),
                        fuel_phase="liquid", gravity="micro", o2_pct=rng([pct(o2)]), pressure_kpa=kpa,
                        diluent="N2" + ("+CO2" if co2 else "") + ("+He" if he else ""), ignited=True,
                        outcome=end or None, burn_time_s=num(col(r, "Burn time")),
                        notes="; ".join(notes + [f"droplet {col(r, 'Droplet initial')} mm, extinction diameter "
                                                 f"{col(r, 'Visible flame')} mm"])))
    return out


def flex_2():
    out = []
    for i, r in enumerate(read("PSI-68_flex2.csv"), 1):
        o2 = [pct(v) for v in nums(col(r, "Oxygen Mole"))]
        if not o2:
            continue
        flow = nums(col(r, "Flow Velocity"))
        out.append(dict(accession="PSI-68", experiment="FLEX-2", table="PSI-68_flex2.csv", source_row=i,
                        test_id=col(r, "Sample"), kind="matrix", fuel=col(r, "Sample"), fuel_phase="liquid",
                        gravity="micro", o2_pct=rng(o2), pressure_kpa=rng(nums(col(r, "Ambient Pressure")), KPA_PER_ATM, 2),
                        flow_mps=rng(flow, 0.01, 4), diluent=col(r, "Ambient Gas") or None,
                        notes="planned test matrix, not individual runs"))
    return out


def cfi():
    out = []
    for i, r in enumerate(read("PSI-39_cfi.csv"), 1):
        o2 = num(col(r, "Oxygen"))
        if o2 is None:
            continue
        he = num(col(r, "Helium")) or 0
        out.append(dict(accession="PSI-39", experiment="CFI", table="PSI-39_cfi.csv", source_row=i,
                        test_id=col(r, "Flex Number"), kind="test", fuel=col(r, "Fuel"), fuel_phase="liquid",
                        gravity="micro", o2_pct=rng([pct(o2)]), pressure_kpa=rng([num(col(r, "Pressure"))], KPA_PER_ATM, 2),
                        diluent="N2" + ("+He" if he else ""), config="tethered" if yes_no(col(r, "Fiber")) else "free",
                        notes=""))
    return out


def flame_design():
    out = []
    for name, config in (("PSI-10_flame-design-normal-flame.csv", "normal"), ("PSI-10_flame-design-inverse-flame.csv", "inverse")):
        for i, r in enumerate(read(name), 1):
            o2 = [pct(num(col(r, "XO2 (init)", "XO2"))), pct(num(col(r, "XO2 (final)")))]
            p = num(col(r, "pmean")) or num(col(r, "pinit"))
            text = col(r, "XO2 (init)", "XO2")
            if o2[0] is None and not text:
                continue
            out.append(dict(accession="PSI-10", experiment="ACME Flame Design", table=name, source_row=i,
                            test_id=col(r, "Test"), kind="test", config=config,
                            fuel=col(r, "Fuel") or "C2H4", fuel_phase="gas", gravity="micro", o2_pct=rng(o2),
                            pressure_kpa=rng([p], KPA_PER_ATM, 2) if p else None, diluent="N2", ignited=True,
                            notes="; ".join(x for x in ("flow ramped during the test" if "RAMPED" in r.values() else "",
                                                        f"O2 given as '{text}'" if o2[0] is None else "") if x)))
    return out


def cfi_g():
    out = []
    for name, config in (("PSI-159_cfi-g-normal-flames.csv", "normal"), ("PSI-159_cfi-g-inverse-flames.csv", "inverse")):
        for i, r in enumerate(read(name), 1):
            o2 = [pct(num(col(r, "XO2 before", "XO2"))), pct(num(col(r, "XO2  after", "XO2 after")))]
            if o2[0] is None:
                continue
            ext = col(r, "Self-ext", "Self -ext").upper()
            out.append(dict(accession="PSI-159", experiment="ACME CFI-G", table=name, source_row=i,
                            test_id=col(r, "Test"), kind="test", config=config, fuel=col(r, "Fuel"),
                            fuel_phase="gas", gravity="micro", o2_pct=rng(o2),
                            pressure_kpa=rng([num(col(r, "approx p"))], KPA_PER_BAR, 2), diluent="N2",
                            ignited=yes_no(col(r, "Hot ignition")),
                            outcome={"SE": "self_extinguished", "FT": "flow_terminated"}.get(ext),
                            burn_time_s=num(col(r, "burn time")),
                            notes="; ".join(x for x in ("cool flame" if yes_no(col(r, "Cool flame")) else "",
                                                        col(r, "Comments")) if x)))
    return out


def bre():
    out = []
    for i, r in enumerate(read("PSI-20_acme-bre.csv"), 1):
        o2 = [pct(v) for v in nums(col(r, "Oxygen Conc"))]
        if not o2:
            continue
        day = f"{col(r, 'Year')}-{col(r, 'Month')}-{col(r, 'Date')}"
        out.append(dict(accession="PSI-20", experiment="ACME BRE", table="PSI-20_acme-bre.csv", source_row=i,
                        test_id=day, kind="test_day", fuel=col(r, "Fuel Bottle"), fuel_phase="gas",
                        gravity="micro", o2_pct=rng(o2), diluent="N2", ignited=True,
                        notes=f"{col(r, 'Flames Ignited')} flames ignited that day at these O2 levels; "
                              f"burner {col(r, 'Burner Size')} mm; pressure varied but not listed"))
    return out


ADAPTERS = (saffire_1, saffire_2, saffire_3, bass_ii, same, same_r, spice, flex, flex_2, cfi, flame_design, cfi_g, bre)
NO_CONDITIONS = {"PSI-26": "material and test number only", "PSI-21": "flames ignited per day only",
                 "PSI-22": "flames ignited per day only", "PSI-23": "atmosphere as text (~21 / ~30 % O2)",
                 "PSI-106": "fuel type only", "PSI-47": "sensor calibration", "PSI-142": "links to figures"}


def build() -> list[PsiTest]:
    rows = [PsiTest.model_validate(r) for adapter in ADAPTERS for r in adapter()]
    return sorted(rows, key=lambda t: (int(t.accession[4:]), t.table, t.source_row, t.test_id))


# ---- summaries and envelope ranges ---------------------------------------------------------
def _group(t: PsiTest) -> tuple[str, str, str]:
    return t.accession, t.gravity, t.config if t.config in ("normal", "inverse") else ""


def summarise(tests) -> list[dict]:
    groups = defaultdict(list)
    for t in tests:
        groups[_group(t)].append(t)
    out = []
    for (acc, grav, config), ts in sorted(groups.items(), key=lambda kv: (int(kv[0][0][4:]), kv[0][1:])):
        span = lambda attr: rng([v for t in ts if (r := getattr(t, attr)) for v in r])
        out.append({"accession": acc, "experiment": ts[0].experiment, "gravity": grav, "config": config,
                    "rows": len(ts), "kinds": ",".join(sorted({t.kind for t in ts})),
                    "o2_pct": span("o2_pct"), "pressure_kpa": span("pressure_kpa"), "flow_mps": span("flow_mps"),
                    "fuels": "; ".join(sorted({t.fuel for t in ts if t.fuel}))[:300],
                    "tables": ", ".join(sorted({t.table for t in ts}))})
    return out


def _envelope_key(e: Envelope) -> tuple[str, str, str]:
    label = e.label.lower()
    config = "inverse" if "inverse" in label else "normal" if "normal" in label else ""
    return e.accession, "earth" if e.gravity == "earth" else "micro", config


def apply_raw_ranges(envelopes, summary) -> list[Envelope]:
    """Replace an envelope's O2 / pressure / flow range with the range in its raw table, field by
    field, when the table has that field. Values from papers stay where the table is silent."""
    by_key = {(s["accession"], s["gravity"], s["config"]): s for s in summary}
    out = []
    for e in envelopes:
        s = by_key.get(_envelope_key(e)) or by_key.get(_envelope_key(e)[:2] + ("",))
        if not s:
            out.append(e)
            continue
        row = e.model_dump(by_alias=True)
        changed = []
        for field, alias in (("o2_pct", "o2Pct"), ("pressure_kpa", "pressureKPa"), ("flow_mps", "flowMps")):
            if s[field]:
                row[alias] = s[field]
                changed.append(f"{field} {s[field][0]:g}-{s[field][1]:g}")
        if changed:
            tag = f"PSI raw table: {s['tables']}"
            row["provenance"] = [p for p in row["provenance"] if not p["source"].startswith("PSI raw table")]
            row["provenance"].append({"source": tag, "quote": f"{s['rows']} cleaned rows (flame/data/clean/psi_tests.csv): "
                                                              + "; ".join(changed)})
        out.append(Envelope.model_validate(row))
    return out


# ---- writing -------------------------------------------------------------------------------
FLAT = ["accession", "experiment", "table", "source_row", "test_id", "kind", "config", "fuel", "fuel_phase",
        "gravity", "o2_pct_min", "o2_pct_max", "pressure_kpa_min", "pressure_kpa_max", "flow_mps_min",
        "flow_mps_max", "diluent", "ignited", "outcome", "burn_time_s", "spread_rate_mm_s", "notes"]


def _flat(t: PsiTest) -> dict:
    d = t.model_dump()
    for f in ("o2_pct", "pressure_kpa", "flow_mps"):
        r = d.pop(f)
        d[f + "_min"], d[f + "_max"] = (r if r else ("", ""))
    return {k: "" if d[k] is None else d[k] for k in FLAT}


def write(tests, summary, envelopes) -> None:
    CLEAN.mkdir(exist_ok=True)
    lines = [json.dumps(t.model_dump(by_alias=True, exclude_none=True, exclude_defaults=True) | {"kind": t.kind},
                        ensure_ascii=False) for t in tests]       # one row per line: readable diffs
    (data.DATA / "psi_tests.json").write_text("[\n" + ",\n".join(lines) + "\n]\n", encoding="utf-8")
    with open(CLEAN / "psi_tests.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FLAT)
        w.writeheader()
        w.writerows(_flat(t) for t in tests)
    cols = ["accession", "experiment", "gravity", "config", "rows", "kinds", "o2_pct_min", "o2_pct_max",
            "pressure_kpa_min", "pressure_kpa_max", "flow_mps_min", "flow_mps_max", "fuels", "tables"]
    with open(CLEAN / "psi_conditions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        for s in summary:
            row = {k: s[k] for k in cols if k in s}
            for fld in ("o2_pct", "pressure_kpa", "flow_mps"):
                row[fld + "_min"], row[fld + "_max"] = s[fld] if s[fld] else ("", "")
            w.writerow(row)
        for acc, why in NO_CONDITIONS.items():
            w.writerow({"accession": acc, "rows": 0, "fuels": f"no numeric conditions in the table ({why})"})
    (data.DATA / "envelopes.json").write_text(
        json.dumps([e.model_dump(by_alias=True) for e in envelopes], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")


def main() -> int:
    tests = build()
    summary = summarise(tests)
    envelopes = apply_raw_ranges(data.get_envelopes(), summary)
    write(tests, summary, envelopes)
    for s in summary:
        print(f"{s['accession']:8} {s['gravity']:5} {s['config'] or '-':8} {s['rows']:5} rows  "
              f"O2 {s['o2_pct']}  p {s['pressure_kpa']}  flow {s['flow_mps']}")
    print(f"{len(tests)} rows -> flame/data/psi_tests.json, flame/data/clean/")
    return 0
