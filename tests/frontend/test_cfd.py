"""The CFD tab runs the teammate's Navier-Stokes fire solvers unchanged: the copies in frontend/js/cfd
must be byte-identical to the teammate's files, and the worker must run them to a fire."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("make_cfd_solvers", ROOT / "scripts" / "make_cfd_solvers.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)
JS = (ROOT / "frontend" / "js")


def test_solvers_are_the_teammates_files_byte_for_byte():
    for name, src in gen.SOLVERS.items():
        assert (gen.OUT / name).read_bytes() == src.read_bytes(), \
            f"{src.name} changed: run  python3 scripts/make_cfd_solvers.py  and commit frontend/js/cfd/{name}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("solver, item, secs, cfg", [
    ("solver_habitat.js", "food packaging", 40, {"dim": 2, "h": 0.1, "g": 0.165, "X": 34, "Pk": 56.5, "U": 10}),
    ("solver_spacecraft.js", "N4", 20, {"h": 0.3, "g": 0, "X": 34, "Pk": 56.5, "U": 20}),
])
def test_worker_runs_the_solver_to_a_fire(solver, item, secs, cfg):
    out = subprocess.run(["node", str(ROOT / "tests" / "frontend" / "cfd_worker_check.mjs"), solver, item, str(secs), json.dumps(cfg)],
                         capture_output=True, text=True, timeout=300)
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert r["ignited"] and r["field_lengths_ok"] and r["frames"] >= 2
    assert r["sim_t"] >= secs and len(r["rooms"]) == 6
    assert r["flame_cells"] + r["burnt_cells"] >= 1 and r["hottest_C"] > 50          # it really burned


def test_lab_has_the_cfd_tab_and_saves_its_outcome():
    lab = (JS / "lab.js").read_text()
    html = (ROOT / "frontend" / "lab.html").read_text()
    assert 'data-v="cfd"' in html and 'id="cfdCanvas"' in html and 'id="cfdSection"' in html
    assert "api/sim/outcome" in lab and "ensureCfd()" in lab
    engine = (JS / "cfd" / "engine.js").read_text()
    assert "from 'three'" in engine and "new Worker(new URL('./worker.js', import.meta.url))" in engine
    for model in ("solver_habitat.js", "solver_spacecraft.js"):
        assert model in engine
    worker = (JS / "cfd" / "worker.js").read_text()
    assert "S.step(0.25)" in worker and "importScripts(m.solver)" in worker   # stepped like the teammate's page
