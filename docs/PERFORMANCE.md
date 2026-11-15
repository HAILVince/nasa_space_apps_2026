# Performance pass (November 2026)

## Update: the landing page no longer runs WebGL

Scrolling the landing page still stuttered on real machines: the full-screen 3D scene (flame
ray-march, smoke, bloom, shadows) rendered on every frame while the page scrolled, and entering a
chapter loaded terrain and compiled shaders mid-scroll. The landing page now shows a still of
each chapter's 3D scene instead, rendered by the lab's own renderer at high quality
(`tests/perf/stills.cjs`, 2400×1350 desktop and 828×1792 portrait WebP, 641 KB for all ten);
the section on screen cross-fades its still in (opacity only, done by the compositor). The
next chapter's image loads when the previous one is shown. The live 3D scene is in the lab.

| Landing page | 3D scene (before) | Stills (now) |
|---|---|---|
| Downloaded | 2.7–6.1 MB (model, 3D engine, textures) | 77–110 KB backdrop + 18–139 KB per further chapter |
| Frame time while wheel-scrolling (software GPU) | ~200 ms | 17 ms avg, 50 ms max (desktop); 16.7 ms (phone) |

Lab: the frame-time watchdog now reacts after 1.5 s instead of 3 s, counts frames up to 1 s
long (before, frames over 250 ms reset it, so a machine managing only a few frames a second never
stepped down), and waits 2.5 s after loading before judging.

## Update: scroll-scrubbed video backdrop (desktop)

On desktop the landing page puts a video of the 3D scene behind the text (`frontend/js/scrub.js`,
`frontend/assets/video/landing-scrub.mp4`, 6.2 MB). It is never played: its time is a function of
the scroll position (piecewise-linear between the chapters, so any page layout lines up), so
scrolling down plays it forward, up plays it backward, and its speed follows the scroll speed.
The script eases towards the target time every animation frame and seeks only when the video is
not already seeking, so seeks never pile up; it sleeps when the page stops moving. No WebGL runs.

The footage is the old live 3D landing page (commit c617a5a) with the current 3D viewer and cabin
model, recorded frame by frame with `tests/perf/scroll_video.py`: 1920×1080 (a 1280×720 page
rendered at device scale 1.5, the high quality tier's maximum), a stepped fake clock, a seeded
`Math.random`, the page scrolled linearly at 7.5 px per frame (one screen = 1.6 s of video); 506
frames at 60 fps (8.4 s), x264 `-crf 24`, BT.709, with a keyframe every 8 frames (133 ms) so that
backward seeks decode at most seven frames. `anchors.json` next to it says where each chapter sits
in the recording. The simulated fire clock and camera moves run faster than on the live page,
because a chapter is on screen for only ~1.8 s of video (see the script's header).

Phones (viewport 900 px and narrower) and visitors with `prefers-reduced-motion` keep the stills
exactly as before and never download the video; so do browsers where `anchors.json` is missing or
the video fails to load. The stills stay in the page under the video as the fallback.
Checked in Edge (Intel Iris Xe) while wheel-scrolling top to bottom and back: frame interval 16.7 ms
median, 16.8 ms 95th percentile, 33 ms 99th, one 83 ms outlier in 969 frames (1080p, 60 fps video).


Goal: make the site faster on every machine **without** changing what it shows. Every change
below was checked against the previous code with the tools in `tests/perf/` (see its README).

## What changed

| Area | Bottleneck | Change | Visual effect |
|---|---|---|---|
| Transfer | 3.48 MB habitat model and all scripts sent uncompressed by the app (nginx gzip level 1 in production) | `app/static.py`: text files and the model gzip-9 compressed once, kept in memory; `Cache-Control: no-cache` + ETag so repeat visits get empty 304s and deploys are never served stale | none (gzip is lossless; round trip tested byte for byte) |
| Startup | Moon globe (Gateway) and rock models loaded before the first frame on every page | loaded on first use / when the page is idle; surface terrain starts loading when the pointer reaches its button (lab) or one chapter ahead (landing) | none |
| Startup | the 3D module graph and the model started downloading only after the page scripts and the catalog request (waterfall) | `modulepreload` + model/AO preload in the page head; viewer import starts before the catalog returns (landing preload at low priority: the wordmark is the first paint) | none |
| Flame shader | both 4-octave noise evaluations ran for every ray step, also in empty parts of the box | exact bound: the noise moves the surface by at most `0.5·R·m·|flicker|`; samples farther than that skip it (same float operation order) | pixel-identical |
| Draw calls | flame box drawn while its shader discards every fragment (strength < 0.002) | not drawn then (after its first frame, so the shader still compiles up front) | pixel-identical |
| GPU uploads | 4000-particle smoke buffers uploaded every frame, also with no smoke | uploaded only while a particle is alive or just died | pixel-identical |
| DOM | marker transforms, time slider, clock, play icon written every frame; the whole SVG time-series chart rebuilt 8×/s, also while paused | written only on change; the chart is built once per result and only its cursor moves | identical |
| Layout | `clientWidth/clientHeight` read every frame | cached from the ResizeObserver | identical |
| Bugs found | landing: scrolling into a chapter before the model loaded threw (`…reading 'SurfaceKit'`); a slow environment load could overwrite a newer choice; vent switch / coverage panel race | fixed | — |

Nothing was removed or lowered: resolution, MSAA, bloom, shadows, flame ray-march steps, smoke
particle counts, textures and geometry are unchanged. The fire model's numbers are unchanged
(`tests/simulation/test_golden.py` pins 40 scenarios to 1e-9).

## Measurements

Local, Chromium + SwiftShader (software GPU), 1366×768, DPR 1, quality tier as chosen by the page
(low on SwiftShader) unless stated. Production could not be measured from the build machine (its
network proxy blocks the site). Software rendering is far slower than any real GPU: compare the
before/after ratios, not the absolute frame times.

| Metric | Before | After | Change |
|---|---|---|---|
| Landing: bytes transferred until 3D ready | 6.08 MB | 2.74 MB | −55 % |
| Lab: bytes transferred until 3D ready | 6.11 MB | 2.72 MB | −55 % |
| Habitat model on the wire (app) | 3.48 MB | 0.98 MB | −72 % |
| Text + model vs production nginx gzip-1 | 1.40 MB | 1.22 MB | −13 % |
| Landing: time to 3D ready | 5.1 s | 4.1 s | −21 % |
| Lab: time to 3D ready | 5.5 s | 4.5–4.8 s | −13…−18 % |
| Frame cost, lab exterior, high tier (identical frames, 2 runs) | 780 ms | 744 ms | −4.6 % |
| Frame cost, burning flame (galley), high tier | 2255 ms | 2159 ms | −4.3 % |
| Frame cost, burning flame (glovebox), high tier | 1453 ms | 1406 ms | −3.2 % |
| Frame cost, burning flame, low tier | 1523 ms | 1559 ms | +2 % (within the ±4 % run-to-run spread) |
| Main-thread busy, landing, steady state | 1.5 % | 0.6 % | −61 % |
| JS heap after 3 rounds of every environment × location | flat (24.5 MB → 24.5 MB) | flat (23.1 MB → 23.1 MB) | no growth |
| LCP / CLS (landing) | 244 ms / 0 | 248 ms / 0 | same |

The page `load` event fires later than before (the preloaded 3D files now count towards it);
what a visitor sees — first paint and the 3D scene — comes as early or earlier.

## Visual verification

`node tests/perf/bench.cjs shots` on the old and the new code, `python tests/perf/diff.py`:
18 states (lab exterior / fire / thermal / X-ray / airflow / interior; ISS, Gateway, Moon,
Mars, Earth; burning flames at low, medium and high quality including Mars; phone 390×844 and
tablet 768×1024; landing desktop and phone). **All 18 3D images are pixel-identical.** The full
pages are identical too, except up to 23 pixels changed by 1/255 in HTML text anti-aliasing
and half-pixel snapping of marker labels (also seen between two runs of the same code).

`node tests/perf/e2e.cjs` clicks through every view, mode, environment (including fast
switching), location, slider, playback control, language and landing chapter: no errors.

## Not done (would trade quality or needs more validation)

- Meshopt/Draco or KTX2 compression of the model and textures: smaller still, but geometry
  quantization / lossy textures change the image, and the encoder could not be run here.
- Lower-resolution rendering, fewer ray-march steps or particles by default: quality trade-offs
  (the existing frame-time watchdog only drops effects on machines that stay slow for 3 s).
- Long-lived immutable caching: needs content-hashed file names (a build step).
- Brotli: not available in the server's Python environment; gzip-9 is used.
- Moving the fire model into a Web Worker: it runs on the server in 5–7 ms per scenario.
