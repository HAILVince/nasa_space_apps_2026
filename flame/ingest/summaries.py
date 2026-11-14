"""Write the 2-3 sentence summaries into flame/data/investigations.json.

Written from the PSI objectives/approach, the PSI experiment tables and the papers cited in
flame/data/envelopes.json; plain words for a non-specialist. `python -m flame.ingest psi`
keeps them on a re-run (it carries existing summaries over).

Run: python -m flame.ingest.summaries
"""
import json
from pathlib import Path

from flame.models import Investigation

OUT = Path(__file__).resolve().parents[1] / "data" / "investigations.json"

SUMMARIES = {
 "PSI-10": "Spherical gas flames on the ISS, burning ethylene or propane from a porous sphere (normal flames) or burning oxygen into a fuel-filled chamber (inverse flames, up to 85 % oxygen). The goal was to find when flames start making soot and to design soot-free flames. Fundamental flame science; useful for oxygen-rich conditions but not a material test.",
 "PSI-20": "The Burning Rate Emulator: a flat porous gas burner that imitates a burning solid, so the 'material' can be varied by changing the fuel flow. Tested in still microgravity air at 21-40 % oxygen to see when small flat materials keep burning or go out. One of the few PSI tests above 30 % oxygen that speaks to material flammability.",
 "PSI-21": "Small methane and ethylene jet flames in coflowing air, from dilute to heavily sooting. The data tune computer models of soot and flame shape that fire simulations rely on. Fundamental science, no fire-safety numbers directly.",
 "PSI-22": "Coflow methane flames with a strong electric field that pushes on the ions in the flame and creates an 'ion wind'. In orbit this imitates a weak buoyant flow, so it is the only PSI experiment that mimics partial gravity. It does not burn habitat materials.",
 "PSI-23": "Spherical gas flames from a porous sphere, diluted with nitrogen or helium, at about 21 % and 30 % oxygen. Measures flame structure and how flames go out by radiating away their heat. Background physics for oxygen-enriched cabins.",
 "PSI-25": "BASS-II burned plastic rods, sheets and fabrics in a small wind tunnel on the ISS while the crew lowered the oxygen (13.6-22.2 %) and stepped the air speed down or up until the flame went out. It mapped the window of air speed in which materials keep burning - too little flow starves the flame, too much blows it out. A 1 g ground companion shows how to translate these limits to gravity.",
 "PSI-26": "BASS, the first glovebox series: fabrics, Nomex, Ultem, plastic spheres, slabs and wax burned in airflow up to 40 cm/s at 17-21.5 % oxygen. It showed how sample thickness, preheating and flow direction decide whether a flame survives in weightlessness. Basis for BASS-II.",
 "PSI-39": "Droplets of dodecane and dodecane mixtures burned at 0.5-5 atm; after the visible flame went out, many kept burning as nearly invisible low-temperature 'cool flames'. Fundamental chemistry, relevant as an unusual hidden-flame hazard.",
 "PSI-47": "DAFT tested whether a particle counter used for smoke detection, modified to work without gravity, can count dust particles on the ISS. Telling dust from smoke matters for avoiding false fire alarms, especially with lunar dust.",
 "PSI-60": "Ground analysis of the SPICE flame images: soot temperature and soot amount from colour pyrometry, compared with a detailed soot model in normal and microgravity. A computer and data study, not a flight test.",
 "PSI-62": "Ground computer model of flames spreading over the BASS samples (sheets, spheres, PMMA rods, wax), checked against BASS and BASS-II flight images reconstructed in 3-D. Links the solid-fuel flight data to simulation.",
 "PSI-68": "FLEX-2 burned droplets of fuel mixtures and jet-fuel surrogates at 0.5-3 atm and 17-30 % oxygen, some with a gentle imposed flow. Extends the FLEX extinction data to realistic fuels. Liquid fuels, not cabin materials.",
 "PSI-69": "FLEX burned methanol and heptane droplets to find the lowest oxygen at which a flame survives, at 0.7-3 atm, and how much carbon dioxide or helium shifts that limit. It is PSI's main data on fire suppression by diluting the atmosphere - what the ISS CO2 extinguisher relies on.",
 "PSI-98": "Saffire-I set fire to a 94 x 40 cm cotton-fiberglass sheet inside an empty Cygnus cargo vehicle after it left the ISS - the first fire at real spacecraft scale. The flame reached a steady speed and size instead of growing like fires on Earth.",
 "PSI-99": "Saffire-II burned nine 5 x 29 cm samples in Cygnus: silicone of several thicknesses, cotton-fiberglass, flat and structured PMMA, and PMMA with Nomex. The PSI table also gives 1 g results for the same samples: thin silicone burned completely on Earth but did not keep burning in weightlessness. The clearest 0 g vs 1 g comparison in PSI.",
 "PSI-100": "Saffire-III repeated the large cotton-fiberglass fire in Cygnus at a higher airflow of 30 cm/s, with the flame spreading with and against the flow. Cameras, thermocouples, radiometers and gas sensors recorded the fire.",
 "PSI-101": "SAME-R re-flew the smoke experiment: spacecraft materials heated until they smoked (no flames), now hotter, also in still air and with a fire-retardant foam, and a new particle instrument. Used to judge how well spacecraft smoke detectors work.",
 "PSI-102": "SAME heated five common spacecraft materials until they smoked and sampled the smoke particles on the ISS, to check whether smoke detectors designed on Earth see smoke the same way in microgravity.",
 "PSI-106": "SLICE studied how small gas jet flames lift off and stay attached as fuel dilution and coflow change, from more than 4,000 high-resolution images. Fundamental flame stability.",
 "PSI-107": "SPICE measured the smoke point - the fuel flow at which a small gas flame starts releasing soot - for several hydrocarbons in coflowing air of 5-65 cm/s. Soot is what smoke detectors see and what radiates heat from a fire.",
 "PSI-115": "Ground computer simulation of how smoke particles form and grow from a heated sample in the SAME geometry, on Earth and in microgravity. Supports smoke-detector design.",
 "PSI-117": "Ground 3-D computer model of droplet cool flames, validated against FLEX, testing how drift and heating change whether a cool flame survives.",
 "PSI-142": "Ground computer study of when cool flames go out, using conditions from the FLEX droplet tests. Fundamental chemistry.",
 "PSI-159": "ACME CFI-G: gaseous cool flames from a spherical burner and their jump to hot flames, at 0.5-3.3 bar and up to 85 % oxygen in the inverse setup - the highest-oxygen microgravity flames in PSI. Each test records ignition and self-extinction, but with gas fuels, not materials.",
}


def main():
    rows = json.loads(OUT.read_text(encoding="utf-8"))
    for row in rows:
        row["summary"] = SUMMARIES[row["accession"]]
        Investigation.model_validate(row)
    OUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} summaries -> {OUT}")


if __name__ == "__main__":
    main()
