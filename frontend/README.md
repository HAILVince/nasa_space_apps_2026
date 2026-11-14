# Workspace 1 — Frontend: the fire-safety lab

Three pages. `index.html` (`js/site.js`): one WebGL canvas behind the page, drag turns the module, the wheel scrolls. `lab.html` (`js/lab.js`): the interactive lab as a full-screen app with its own 3D view (wheel zooms). Shared code: `js/common.js`. `spread.html` (`js/spread.js`): the team's room-to-room fire spread simulator (2D, six rooms, doors and hatches) in the site's look, HU/EN labels.

On the landing page The 3D scene is fixed behind the whole page and the sections
scroll over it: **hero** (Earth orbit, slow orbit of the module) → **three physics chapters**
(each switches the scene: 0 g flame, lunar flame, ventilation streamlines) → **lab** (glass
panels over the live scene; the user's own scenario, URL-shareable) → **investigations** and
**sources** (solid sections; the canvas stops rendering there). Story chapters run their own
cached simulations and never overwrite the lab settings. The wheel scrolls the page;
Ctrl/Cmd + wheel zooms the 3D view. Type: Barlow Condensed (display), Instrument Serif italic
(accents), Inter (text), IBM Plex Mono (numbers); one accent colour (ember).

`index.html` + `css/app.css` + native ES modules in `js/`. No build step: Three.js r180 and its
add-ons are vendored in `vendor/three/`, fonts in `fonts/`, the Blender-built model and
textures in `assets/`. WebGL 2 is required for the 3D view.

| File | Does |
|---|---|
| `js/lab.js` (lab.html) | state, API calls, scenario/result panels, playback, research drawer, AI console, guided tour, URL state (`#environment=moon&location=galley...`) |
| `js/dashboard.js` | the *Investigations* section: research dashboards and comparison (`/api/research/scenarios`, `dashboard`, `compare`) |
| `js/i18n.js` | Hungarian / English strings (`.hu` domains start in Hungarian) |
| `js/charts.js` | SVG flammability map (O2 vs pressure with the measured NASA points) and fire history |
| `js/viewer/viewer.js` | renderer, bloom post-processing, GLB + baked AO, X-ray / thermal / airflow modes, cameras, markers |
| `js/viewer/environments.js` | Earth orbit (procedural Earth with atmosphere), lunar orbit (lunar globe), lunar and Martian surfaces (terrain + rocks), Earth lab |
| `js/viewer/fire.js` | ray-marched flame: round and blue in 0 g, tall and sooty under gravity, colour from the computed flame temperature |
| `js/viewer/smoke.js` | smoke particles carried by the cabin ventilation field (rising only with gravity) and streamlines |

Rules:

- Only call endpoints listed in `docs/API.md` (the test checks it).
- Agent replies default to English; the reply language selector in the AI console switches to Hungarian.
- Enter sends a chat message, Shift+Enter makes a new line.
- User text and research records go into the page with `textContent`; only the server-escaped
  chat answer (`message.html`) may use `innerHTML`.
- `?fps=2` caps the frame rate (useful for software rendering and screenshots).
- Quality adapts per machine: the start tier (`low` / `medium` / `high`) comes from the GPU name,
  cores and memory; a frame-time watchdog steps down when a 2-s average drops under ~36 fps and
  tries one step up on fast machines. Tiers set pixel ratio, MSAA, bloom, shadow map size, flame
  ray-march steps and the smoke particle budget. `?q=low|medium|high` forces a tier.
- Shadows are redrawn only when the scene changes (and a few times a second while the solar
  arrays turn). A paused lab with no input renders at 24 fps. No CSS backdrop blur anywhere.
- Rendering: dynamic resolution (the render scale follows the frame time every second, 0.55–1×) on top of the quality tiers.
- 0 g flames use their own shader branch modelled on NASA CFM/FLEX/BASS images: a thin blue-violet sheet brightest at its rim, a faint peach interior, soot sparks near the fuel, a dark quenched gap on the fuel, a comet shape in forced flow, slow breathing.
- Buoyant flames puff at f ≈ 1.5/√D Hz scaled by √(g/g₀) (pool-fire correlation); 0 g flames are steady.

Test: `pytest tests/frontend`. Run: start the backend (see CONTRIBUTING.md), open http://127.0.0.1:8000.
