"""The main simulator's 2D fire-spread model must stay exactly the teammate's physics:
frontend/js/spread/model.js is generated from blackfox/db/knowledge/habitat_fire_sim.html, and the
Node check runs both side by side and requires every field to be bit-identical."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("make_spread_model", ROOT / "scripts" / "make_spread_model.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def test_model_module_is_generated_from_the_teammates_current_file():
    expected = gen.module_text(gen.physics_block(gen.SOURCE.read_text(encoding="utf-8")))
    assert gen.TARGET.read_text(encoding="utf-8") == expected, \
        "habitat_fire_sim.html changed: run  python3 scripts/make_spread_model.py  and commit frontend/js/spread/model.js"


def test_copied_block_touches_no_page():
    block = gen.physics_block(gen.SOURCE.read_text(encoding="utf-8"))
    for dom in ("document.", "$(", "window.", "CSS."):
        assert dom not in block, dom


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_module_runs_bit_identical_to_the_original():
    out = subprocess.run(["node", str(ROOT / "tests" / "frontend" / "spread_equivalence.mjs")],
                         capture_output=True, text=True, timeout=600)
    report = json.loads(out.stdout)
    assert report["ok"] and out.returncode == 0, json.dumps(report, indent=1)
    assert all(s["identical"] for s in report["scenarios"])
    assert any(s["cells_ignited"] > 50 for s in report["scenarios"])          # the fire really spreads somewhere
    assert any(s["vent_off_at_s"] for s in report["scenarios"])               # the automatic vent shutdown was exercised
    assert all(report["ignition_points_are_fuel"].values())
