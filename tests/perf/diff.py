"""Compare two screenshot folders from `node tests/perf/bench.cjs shots`.

    python tests/perf/diff.py <before-dir> <after-dir>

<name>.png (3D view, labels hidden) must match exactly; <name>-ui.png is the full page and is
reported for review (HTML marker labels may move by half a pixel between runs).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def diff(a: Path, b: Path) -> tuple[int, int, float]:
    x = np.asarray(Image.open(a).convert("RGB"), dtype=np.int16)
    y = np.asarray(Image.open(b).convert("RGB"), dtype=np.int16)
    if x.shape != y.shape:
        return -1, -1, -1.0
    d = np.abs(x - y).max(axis=2)
    return int((d > 0).sum()), int(d.max()), float(d.mean())


def main(before: str, after: str) -> int:
    bad = 0
    for a in sorted(Path(before).glob("*.png")):
        b = Path(after) / a.name
        if not b.exists():
            print(f"{a.name:34} missing in {after}"); bad += 1; continue
        n, mx, mean = diff(a, b)
        exact = not a.stem.endswith("-ui")
        ok = n == 0 if exact else True
        bad += not ok
        print(f"{a.name:34} {'EXACT' if n == 0 else 'DIFF ':5} pixels={n:7} max={mx:3} mean={mean:.4f}"
              + ("" if ok else "   <-- 3D image changed"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
