"""Copy the gap-map data the deck needs out of the project, so slide 4 shows what the site shows.

Run from the repository root:

    .venv/bin/python pitch/tools/sync_envelopes.py

It asks flame.gapmap for the same data /evidence.html draws, keeps only the fields the chart uses, and writes
them to pitch/assets/envelopes.json and into the <script id="envelopes"> block of pitch/deck.html (a page opened
from disk cannot fetch a JSON file, so the deck carries its own copy).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flame import data, gapmap  # noqa: E402

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


def main() -> None:
    payload = build()
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (PITCH / "assets" / "envelopes.json").write_text(text + "\n", encoding="utf-8")
    deck = PITCH / "deck.html"
    html = deck.read_text(encoding="utf-8")
    block = re.compile(r'(<script type="application/json" id="envelopes">)(.*?)(</script>)', re.S)
    if not block.search(html):
        sys.exit('pitch/deck.html has no <script type="application/json" id="envelopes"> block')
    deck.write_text(block.sub(lambda m: m.group(1) + "\n" + text + "\n" + m.group(3), html, count=1), encoding="utf-8")
    phases = {}
    for e in payload["envelopes"]:
        phases[e["phase"]] = phases.get(e["phase"], 0) + 1
    print(f'{payload["investigations"]} investigations, {len(payload["envelopes"])} envelopes on the map '
          f'({payload["unplaced"]} cannot be placed), by fuel phase: {phases}')
    print("Moon base covered by:", payload["points"]["moon"]["coveredByPhase"])


if __name__ == "__main__":
    main()
