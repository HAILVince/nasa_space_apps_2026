# Performance and visual-regression tools

Browser-based checks for the 3D pages. They are not part of `pytest` / CI (they need Chromium and
take minutes on a software renderer); run them before and after any rendering or loading change.

| Command | What |
|---|---|
| `node tests/perf/bench.cjs measure out.json` | load time, transfer by type, frame time (avg and 99th percentile), CPU busy %, draw calls, triangles, programs, JS heap, heap and GPU-resource growth after 3 rounds of switching every environment and fire location |
| `node tests/perf/bench.cjs shots dir/` | deterministic screenshots of every lab view, mode, environment and quality tier, phone and tablet widths |
| `python tests/perf/diff.py before/ after/` | `<name>.png` (3D view only) must be pixel-identical; `<name>-ui.png` (full page) is listed for review |
| `node tests/perf/stills.cjs out/` | re-renders the landing page backdrops (`frontend/assets/img/bg-*`) from the 3D scene; needs the 3D landing page of commit c617a5a running |
| `node tests/perf/e2e.cjs` | clicks through every view, mode, environment (incl. fast switching), fire location, slider, playback control, language and landing chapter; fails on console errors or a blank 3D frame |

Start the site first: `uvicorn app.main:app --port 8010` (or set `BFX_URL` / pass the URL).

`shots` freezes time with Playwright's fake clock, seeds `Math.random`, disables CSS transitions
and pins everything that integrates over frames (animation mixer, Earth spin, camera tweens,
playback time), so the same code renders the same pixels. Everything runs on SwiftShader so the
numbers do not depend on the host GPU: absolute frame rates are far below a real GPU; compare
before/after ratios only.
