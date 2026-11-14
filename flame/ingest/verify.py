"""Check every test envelope against its sources: `python -m flame.ingest verify`.

1. PSI tables. An O2 / pressure / flow range that the PSI experiment table has must equal the
   range re-derived from the cleaned table rows (flame/data/psi_tests.json). A mismatch fails.
2. NASA documents. A range the table does not give is taken from SOURCES below: each value
   names its document (NTRS record or the PSI table itself) and quotes the sentence it is read
   from. A table value is never replaced by a paper value.
3. What neither gives stays empty and goes into notReported with the reason, so the pages can
   say "not reported" instead of guessing.

An envelope is verified when every range it shows passed 1 or 2. The quotes were checked
against the PDFs in blackfox/db/knowledge/pdf-s, the raw PSI tables and the NTRS records.
"""
from __future__ import annotations

import json

from .. import data
from ..models import Envelope
from .clean_tables import _envelope_key, summarise

ATM = 101.3                       # 1 atm in kPa, rounded as everywhere else in flame/data
FIELDS = (("o2_pct", "o2Pct"), ("pressure_kpa", "pressureKPa"), ("flow_mps", "flowMps"))

ISS_AIR = ("NASA Moon to Mars Exploration Atmosphere, NTRS 20240003211",
           "the sea level atmosphere of 14.7 psia, 21% oxygen (O2) found on the International Space Station")
MSG_WV = ("MSG facility overview, NTRS 20090017703",
          "maintain the WV pressure lower than the cabin pressure ... the WV will maintain a pressure differential of at least 1.3 mbar between the WV and the outside")
ACME_2014 = "Gaseous Non-Premixed Flame Research Planned for the ISS, NTRS 20140009169"

# key: (accession, label prefix) -> field -> (value, [(source, quote), ...]) or ("not reported", reason)
SOURCES: dict[tuple[str, str], dict[str, tuple]] = {
    ("PSI-26", "Thin and thick solids"): {
        "o2Pct": ([17.0, 21.5], [("Ferkul et al. 2013 (BASS), NTRS 20140011099", "Ambient oxygen atmospheres 17% to 21.5%")]),
        "pressureKPa": ([ATM, ATM], [("Ferkul et al. 2013 (BASS), NTRS 20140011099", "Atmosphere: 17% O2/N2; 1 atm")]),
        "flowMps": ([0.0, 0.4], [("PSI-26 Approach", "airflow speeds reaching as high as 40 cm/s")]),
    },
    ("PSI-25", "Solids with oxygen lowered"): {
        "pressureKPa": ([ATM, ATM], [("BASS-II Summary Report, NASA/TM-20210011385",
                                      "The tests were conducted in ambient O2 molar fraction of 16 to 21 percent. Ambient pressure was 1 atm.")]),
        "flowMps": ([0.0, 0.4], [("PSI-25 Approach", "could impose airflow speeds up to 40 cm/s")]),
    },
    ("PSI-25", "1 g companion"): {
        "o2Pct": ([14.0, 18.0], [("Marcum et al. 2016, NTRS 20160012691",
                                  "burned at oxygen concentrations ranging from 14 to 18% by volume")]),
        "pressureKPa": ("not reported", "ground laboratory tests; the NTRS record does not state the pressure"),
        "flowMps": ("not reported", "the blowoff flow speed differs per rod and is plotted, not tabulated"),
    },
    ("PSI-98", ""): {
        "pressureKPa": ("not reported", "Cygnus cabin pressure is not in the PSI table; Saffire-II on the same "
                                        "vehicle type burned at 100 kPa (NTRS 20200000557)"),
    },
    ("PSI-99", "Nine"): {
        "pressureKPa": ([100.0, 100.0], [("Thomsen et al. 2018, NTRS 20200000557",
                                          "Microgravity experiments were conducted during NASA's Spacecraft Fire Experiment "
                                          "(Saffire II), on board the Cygnus spacecraft at 100 kPa")]),
    },
    ("PSI-99", "Same samples burned in 1 g"): {
        "o2Pct": ("not reported", "the PSI table gives the 1 g burn length and spread rate only"),
        "pressureKPa": ("not reported", "the PSI table gives the 1 g burn length and spread rate only"),
        "flowMps": ("not reported", "the PSI table gives the 1 g burn length and spread rate only"),
    },
    ("PSI-100", ""): {
        "o2Pct": ("not reported", "the PSI table lists flow and direction only; Saffire-I and -II measured 21.5-22.1 % O2"),
        "pressureKPa": ("not reported", "the PSI table lists flow and direction only"),
    },
    # SAME and SAME-R heated samples inside the Microgravity Science Glovebox, which holds ISS cabin air
    ("PSI-102", ""): {
        "o2Pct": ([21.0, 21.0], [("Urban et al. 2009 (SAME), NTRS 20120012884", "Microgravity Science Glovebox (MSG), an ISS facility"), ISS_AIR]),
        "pressureKPa": ([101.2, 101.2], [MSG_WV, ISS_AIR]),     # 14.7 psia less >= 1.3 mbar
    },
    ("PSI-101", ""): {
        "o2Pct": ([21.0, 21.0], [("Urban et al. 2013 (SAME-R), NTRS 20140006585",
                                  "The system was installed in the Microgravity Science Glovebox (MSG), an ISS facility"), ISS_AIR]),
        "pressureKPa": ([101.2, 101.2], [MSG_WV, ISS_AIR]),     # 14.7 psia less >= 1.3 mbar
    },
    ("PSI-47", ""): {
        "o2Pct": ("not reported", "sensor test: dust aerosol in sealed 15-liter Mylar bags, no flame"),
        "pressureKPa": ("not reported", "sensor test: dust aerosol in sealed 15-liter Mylar bags, no flame"),
        "flowMps": ("not reported", "sensor test: dust aerosol in sealed 15-liter Mylar bags, no flame"),
    },
    ("PSI-69", ""): {"flowMps": ("not reported", "free droplets in a quiescent chamber; no flow in the PSI table")},
    ("PSI-39", ""): {"flowMps": ("not reported", "free droplets in a quiescent chamber; no flow in the PSI table")},
    ("PSI-159", ""): {"flowMps": ("not reported", "spherical burner in a quiescent chamber; no flow in the PSI table")},
    ("PSI-10", ""): {"flowMps": ("not reported", "spherical burner in a quiescent chamber; no flow in the PSI table")},
    ("PSI-20", ""): {
        "pressureKPa": ("not reported", "PSI table: the chamber pressures were also varied but are not identified in this summary table"),
        "flowMps": ([0.0, 0.0], [("ACME overview, NTRS 20220015583",
                                  "A study focused on material flammability in a quiescent atmosphere emulated the burning of "
                                  "condensed-phased fuels")]),
    },
    ("PSI-23", ""): {
        "o2Pct": ([21.0, 30.0], [("PSI-23 Experimental table", "~21% O2 with N2 ... ~30% O2 with N2")]),
        "pressureKPa": ([ATM, ATM], [("PSI-23 Experimental table", "Atmosphere is ~1 atm but pressure increases and O2% drops with vitiation.")]),
        "flowMps": ("not reported", "spherical burner in a quiescent chamber; no flow in the PSI table"),
    },
    ("PSI-22", ""): {
        "o2Pct": ("not reported", "the PSI table lists fuel concentration and mesh polarity only"),
        "pressureKPa": ("not reported", "the PSI table lists fuel concentration and mesh polarity only"),
        "flowMps": ("not reported", "the PSI table lists fuel concentration and mesh polarity only"),
    },
    ("PSI-21", ""): {
        "o2Pct": ([21.0, 21.0], [(ACME_2014, "Measurements will be made of the structure of diluted methane and ethylene "
                                             "flames in an air coflow.")]),
        "pressureKPa": ("not reported", "the PSI table lists fuel concentrations only"),
        "flowMps": ("not reported", "the PSI table lists fuel concentrations only"),
    },
    ("PSI-107", ""): {
        "o2Pct": ([21.0, 21.0], [(ACME_2014, "the flame was enclosed within a small flow duct ... in the ELF, SPICE, and SLICE "
                                             "experiments ... In all cases, the atmosphere consisted of ~21% oxygen (by volume) "
                                             "with a balance of nitrogen.")]),
        "pressureKPa": ([100.0, 100.0], [(ACME_2014, "The pressure was consistently ~100 kPa")]),
    },
    ("PSI-106", ""): {
        "o2Pct": ([21.0, 21.0], [(ACME_2014, "In all cases, the atmosphere consisted of ~21% oxygen (by volume) with a "
                                             "balance of nitrogen.")]),
        "pressureKPa": ([100.0, 100.0], [(ACME_2014, "in the ELF, SPICE, and SLICE experiments. The pressure was "
                                                     "consistently ~100 kPa")]),
        "flowMps": ("not reported", "the PSI table lists fuel type only"),
    },
}
CHECK_TAG = "Black Fox source check"


def _sources_for(e: Envelope) -> dict:
    """the SOURCES entry of this envelope: same accession, longest matching label prefix"""
    hits = [(len(prefix), v) for (acc, prefix), v in SOURCES.items() if acc == e.accession and e.label.startswith(prefix)]
    return max(hits, key=lambda h: h[0])[1] if hits else {}


def check(envelopes, summary) -> tuple[list[Envelope], list[str]]:
    by_key = {(s["accession"], s["gravity"], s["config"]): s for s in summary}
    out, problems = [], []
    for e in envelopes:
        row = e.model_dump(by_alias=True)
        table = by_key.get(_envelope_key(e)) or by_key.get(_envelope_key(e)[:2] + ("",)) or {}
        src = _sources_for(e)
        notes, row["notReported"] = [], {}
        row["provenance"] = [p for p in row["provenance"]
                             if p["source"] != CHECK_TAG and p["source"] != "assumption"]
        ok = True
        for field, alias in FIELDS:
            spec = src.get(alias)
            if table.get(field):                                 # the PSI table has it: must match
                if row[alias] is None or [round(v, 6) for v in row[alias]] != [round(v, 6) for v in table[field]]:
                    problems.append(f"{e.accession} '{e.label}': {alias} {row[alias]} != PSI table {table[field]}")
                    ok = False
                else:
                    notes.append(f"{alias} = PSI table ({table['rows']} rows, {table['tables']})")
            elif spec and spec[0] == "not reported":
                row[alias] = None
                row["notReported"][alias] = spec[1]
            elif spec:
                value, quotes = spec
                row[alias] = value
                for source, quote in quotes:
                    if not any(p["source"] == source and p["quote"] == quote for p in row["provenance"]):
                        row["provenance"].append({"source": source, "quote": quote})
                notes.append(f"{alias} = {', '.join(s for s, _ in quotes)}")
            elif row[alias] is not None:                         # a value with no checked source
                problems.append(f"{e.accession} '{e.label}': {alias} {row[alias]} has no checked source")
                ok = False
            else:
                row["notReported"][alias] = "not given in the PSI table or the cited NASA documents"
        row["verified"] = ok
        if notes:
            row["provenance"].append({"source": CHECK_TAG, "quote": "; ".join(notes)})
        out.append(Envelope.model_validate(row))
    return out, problems


def main() -> int:
    envelopes, problems = check(data.get_envelopes(), summarise(data._load("psi_tests")))
    for p in problems:
        print("MISMATCH", p)
    (data.DATA / "envelopes.json").write_text(
        json.dumps([e.model_dump(by_alias=True) for e in envelopes], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"{sum(e.verified for e in envelopes)}/{len(envelopes)} envelopes verified")
    return 1 if problems else 0
