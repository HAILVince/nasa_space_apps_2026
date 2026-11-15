"""Copy the data the deck's charts need out of the project, so the slides show what the site shows.

Run from the repository root:

    .venv/bin/python pitch/tools/sync_envelopes.py

envelopes  slides 3 and 4: the gap map, from flame.gapmap (the same data /evidence.html draws)
brief      slide 6: the Moon-base ranking of the investigations (flame.rank), how many cleaned PSI test rows
           each investigation gave (flame/data/psi_tests.json), and one run of the cabin fire model on the
           lunar surface (blackfox.physics.fire), the scenario of the slide 5 screenshot

Each set is written to pitch/assets/<name>.json and into the <script id="<name>"> block of pitch/deck.html
(a page opened from disk cannot fetch a JSON file, so the deck carries its own copy).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from blackfox.physics import fire  # noqa: E402
from flame import data, gapmap, rank  # noqa: E402

PITCH = ROOT / "pitch"


def build() -> dict:
    g = gapmap.gap_map()
    habitats = {h["id"]: h for h in g["habitats"]}
    iss, moon = habitats["iss"], habitats["moon-base"]
    envelopes = [{"accession": r["accession"], "name": r["acronym"], "phase": r["fuelPhase"], "gravity": r["gravity"],
                  "o2Pct": list(r["o2Pct"]), "pressureKPa": list(r["pressureKPa"]), "verified": r["verified"]}
                 for r in g["rectangles"]]
    return {
        "source": "flame/gapmap.py gap_map(), from flame/data/envelopes.json, habitats.json and investigations.json",
        "axes": {k: list(v) for k, v in g["axes"].items()},
        "investigations": len(data.get_investigations()),
        "unplaced": len(g["unplaced"]),
        "points": {
            "iss": {"name": "ISS", "o2Pct": iss["o2Pct"][0], "pressureKPa": iss["pressureKPa"][0]},
            # the dot is NASA's exploration atmosphere (8.2 psia, 34 % O2): the low-pressure corner of the range
            "moon": {"name": "Moon base", "o2Pct": moon["o2Pct"][1], "pressureKPa": moon["pressureKPa"][0],
                     "range": {"o2Pct": list(moon["o2Pct"]), "pressureKPa": list(moon["pressureKPa"])},
                     "coveredByPhase": g["coverageByPhase"]["moon-base"]},
        },
        "envelopes": envelopes,
    }


def build_brief() -> dict:
    ranked = rank.rank_for_habitat(data.get_habitat("moon-base"))
    run = fire.simulate(environment="moon")
    end = 100.0                                   # seconds shown; this fire is out before that
    rows: dict[str, int] = {}
    for test in data.get_psi_tests():
        rows[test.accession] = rows.get(test.accession, 0) + 1
    return {
        "source": "flame/rank.py rank_for_habitat('moon-base') with the default weights; flame/data/psi_tests.json; "
                  "blackfox/physics/fire.py simulate(environment='moon') with the lab's defaults",
        "ranking": [{"name": r.acronym, "score": round(r.score, 3)} for r in ranked],
        "tests": [{"accession": a, "rows": n} for a, n in sorted(rows.items(), key=lambda kv: -kv[1])],
        "fire": {
            "inputs": {k: run["inputs"][k] for k in ("environment", "material", "location", "pressure_kpa", "o2_pct")},
            "endS": end,
            "t": [row["t"] for row in run["series"] if row["t"] <= end],
            "hrrKW": [round(row["hrr_kw"], 3) for row in run["series"] if row["t"] <= end],
            "events": [{"t": e["t"], "key": e["key"]} for e in run["timeline"]["events"]],
        },
    }


def write(name: str, payload: dict, html: str) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (PITCH / "assets" / f"{name}.json").write_text(text + "\n", encoding="utf-8")
    block = re.compile(rf'(<script type="application/json" id="{name}">)(.*?)(</script>)', re.S)
    if not block.search(html):
        sys.exit(f'pitch/deck.html has no <script type="application/json" id="{name}"> block')
    return block.sub(lambda m: m.group(1) + "\n" + text + "\n" + m.group(3), html, count=1)


def main() -> None:
    payload, brief = build(), build_brief()
    deck = PITCH / "deck.html"
    html = write("envelopes", payload, deck.read_text(encoding="utf-8"))
    deck.write_text(write("brief", brief, html), encoding="utf-8")
    phases = {}
    for e in payload["envelopes"]:
        phases[e["phase"]] = phases.get(e["phase"], 0) + 1
    print(f'{payload["investigations"]} investigations, {len(payload["envelopes"])} envelopes on the map '
          f'({payload["unplaced"]} cannot be placed), by fuel phase: {phases}')
    print("Moon base covered by:", payload["points"]["moon"]["coveredByPhase"])
    print(f'test rows: {sum(t["rows"] for t in brief["tests"])} from {len(brief["tests"])} investigations')
    print(f'ranking: {len(brief["ranking"])} investigations, first {brief["ranking"][0]["name"]}; '
          f'fire run: {brief["fire"]["inputs"]}, events {[(e["key"], e["t"]) for e in brief["fire"]["events"]]}')


if __name__ == "__main__":
    main()
