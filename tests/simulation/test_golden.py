"""The fire model's outputs are pinned: a change of any number here must be deliberate.

golden_fire.json was written from the model as committed; regenerate it only together with a
reviewed change to blackfox/physics/fire.py. Tolerance: 1e-9 relative (floating point only).
"""
import json
from pathlib import Path

import pytest

from blackfox.physics import fire

GOLDEN = json.loads((Path(__file__).parent / "golden_fire.json").read_text())


@pytest.mark.parametrize("g", GOLDEN, ids=lambda g: f"{g['environment']}-{g['location']}-{g['auto_vent_shutdown']}")
def test_simulation_outputs_are_unchanged(g):
    r = fire.simulate(g["environment"], location=g["location"], auto_vent_shutdown=g["auto_vent_shutdown"])
    f, fl, pk, tl = r["flammability"], r["flame"], r["peaks"], r["timeline"]
    got = {"moc_eff": f["moc_eff"], "margin_pct": f["margin_pct"], "flammable": f["flammable"],
           "spread_cm_s": fl["spread_cm_s"], "temperature_k": fl["temperature_k"], "hrr_kw": pk["hrr_kw"],
           "co_ppm": pk["co_ppm"], "burned_g": pk["burned_g"], "alarm_s": tl["alarm_s"],
           "extinguished_s": tl["extinguished_s"], "events": [e["key"] for e in tl["events"]],
           "hrr_sum": sum(x["hrr_kw"] for x in r["series"]), "o2_end": r["series"][-1]["o2_pct"]}
    for k, v in got.items():
        want = g[k]
        if isinstance(want, float):
            assert v == pytest.approx(want, rel=1e-9, abs=1e-12), k
        else:
            assert v == want, k
