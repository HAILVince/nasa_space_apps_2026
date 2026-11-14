"""Copy the teammate's CFD fire solvers into the site, unchanged, so the main simulator runs them.

    python3 scripts/make_cfd_solvers.py

The files are copied byte for byte (tests/frontend/test_cfd.py checks it): the main simulator runs
exactly the teammate's physics. Their pages load three.js from a CDN and build one HTML file per
solver; the main simulator only needs the solvers, which it runs in frontend/js/cfd/worker.js.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "blackfox" / "db" / "knowledge"
OUT = ROOT / "frontend" / "js" / "cfd"
SOLVERS = {
    # two-deck habitat; cfg.dim = 2 (vertical section) or 3 (full 3D)
    "solver_habitat.js": K / "simulation_NavierStokes_2D" / "src" / "solver.js",
    # ISS-like spacecraft: lab module with rack ring, node with crew quarters and galley, airlock (3D)
    "solver_spacecraft.js": K / "Spacecraft_Cabin_Fire" / "src" / "solver.js",
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, src in SOLVERS.items():
        (OUT / name).write_bytes(src.read_bytes())
        print(f"copied {src.relative_to(ROOT)} -> {(OUT / name).relative_to(ROOT)}")
