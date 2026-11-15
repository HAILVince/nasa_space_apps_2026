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
    ("solver_living.js", "food packaging", 40, {"dim": 2, "h": 0.1, "g": 0.165, "X": 34, "Pk": 56.5, "U": 10}),
    # the grids light devices (phones) get: coarse, but real 3D
    ("solver_habitat.js", "food packaging", 40, {"dim": 3, "h": 0.25, "g": 0.165, "X": 34, "Pk": 56.5, "U": 10}),
    ("solver_living.js", "food packaging", 40, {"dim": 3, "h": 0.25, "g": 0.165, "X": 34, "Pk": 56.5, "U": 10}),
])
def test_worker_runs_the_solver_to_a_fire(solver, item, secs, cfg):
    out = subprocess.run(["node", str(ROOT / "tests" / "frontend" / "cfd_worker_check.mjs"), solver, item, str(secs), json.dumps(cfg)],
                         capture_output=True, text=True, timeout=300)
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert r["ignited"] and r["field_lengths_ok"] and r["frames"] >= 2
    assert r["sim_t"] >= secs and len(r["rooms"]) == (7 if solver == "solver_living.js" else 6)
    assert r["flame_cells"] + r["burnt_cells"] >= 1 and r["hottest_C"] > 50          # it really burned


def test_lab_has_the_cfd_tab_and_saves_its_outcome():
    lab = (JS / "lab.js").read_text()
    html = (ROOT / "frontend" / "lab.html").read_text()
    assert 'data-v="cfd"' in html and 'id="cfdCanvas"' in html
    # the CFD is always 3D: no section view and no 3D/section switch
    assert 'id="cfdSection"' not in html and 'id="cfdMode"' not in html and "$('cfdMode')" not in lab
    assert "api/sim/outcome" in lab and "ensureCfd()" in lab
    engine = (JS / "cfd" / "engine.js").read_text()
    assert "from 'three'" in engine and "new Worker(new URL('./worker.js', import.meta.url))" in engine
    for model in ("solver_habitat.js", "solver_spacecraft.js", "solver_living.js"):
        assert model in engine
    worker = (JS / "cfd" / "worker.js").read_text()
    assert "S.step(0.25)" in worker and "importScripts(m.solver)" in worker   # stepped like the teammate's page


def test_living_quarters_habitat_is_the_teammates_physics_with_a_new_layout():
    living = (gen.OUT / gen.LIVING).read_text(encoding="utf-8")
    assert living == gen.living_text(), "run  python3 scripts/make_cfd_solvers.py"
    hab = gen.SOLVERS["solver_habitat.js"].read_text(encoding="utf-8")
    ship = gen.SOLVERS["solver_spacecraft.js"].read_text(encoding="utf-8")
    # undo the documented geometry and material changes: what remains must be the teammate's habitat solver
    back = living[len(gen.HEADER):]
    for old, new in gen.GEOMETRY:
        back = back.replace(new, old, 1)
    back = back.replace(gen.mat_block(ship), gen.mat_block(hab), 1)
    a, b = back.index("const ROOMS=["), back.index("// ---------------- state ----------------")
    c, d = hab.index("const ROOMS=["), hab.index("// ---------------- state ----------------")
    assert back[:a] + back[b:] == hab[:c] + hab[d:]                         # every physics line identical


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_living_quarters_layout_is_complete_in_2d_and_3d():
    script = """
const {createSolver}=require(process.argv[1]);
const out={};
for (const dim of [2,3]) { const S=createSolver({dim, h: dim===2?0.1:0.2, iters:24});
  out[dim]={ rooms: S.ROOMS.map((r,ri)=>S.room.reduce((a,x,k)=>a+(x===ri&&S.type[k]===0?1:0),0)), items: S.ITEMS.map(i=>i.cells),
    openings: S.OPEN.map(o=>o.cells.length), sup: S.sup.reduce((a,b)=>a+b,0), ret: S.ret.reduce((a,b)=>a+b,0), mats: S.MKEYS.length }; }
console.log(JSON.stringify(out));"""
    out = subprocess.run(["node", "-e", script, str(gen.OUT / gen.LIVING)], capture_output=True, text=True, timeout=120)
    res = json.loads(out.stdout)
    for dim in ("2", "3"):
        r = res[dim]
        assert len(r["rooms"]) == 7 and min(r["rooms"]) > 100, r["rooms"]       # every room has air
        assert len(r["items"]) == 18 and min(r["items"]) > 0, r["items"]         # every furnishing is on the grid
        assert len(r["openings"]) == 7 and min(r["openings"]) > 0 and r["sup"] > 0 and r["ret"] > 0 and r["mats"] == 12


def test_every_device_gets_the_cfd_in_3d():
    engine = (JS / "cfd" / "engine.js").read_text()
    assert "dim: 2" not in engine and "drawSection" not in engine and "'section'" not in engine
    assert engine.count("low: { dim: 3, h: 0.25 }") == 2          # habitat and living quarters on phones
