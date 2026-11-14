# Workspace 1 — Frontend: the fire-safety lab

`index.html` + `css/app.css` + native ES modules in `js/`. No build step: Three.js r180 and its
add-ons are vendored in `vendor/three/`, fonts in `fonts/`, the Blender-built model and
textures in `assets/`. WebGL 2 is required for the 3D view.

| File | Does |
|---|---|
| `js/app.js` | state, API calls, scenario/result panels, playback, research drawer, AI console, guided tour, URL state (`#environment=moon&location=galley...`) |
| `js/i18n.js` | Hungarian / English strings (`.hu` domains start in Hungarian) |
| `js/charts.js` | SVG flammability map (O2 vs pressure with the measured NASA points) and fire history |
| `js/viewer/viewer.js` | renderer, bloom post-processing, GLB + baked AO, X-ray / thermal / airflow modes, cameras, markers |
| `js/viewer/environments.js` | Earth orbit (procedural Earth with atmosphere), lunar orbit (lunar globe), lunar and Martian surfaces (terrain + rocks), Earth lab |
| `js/viewer/fire.js` | ray-marched flame: round and blue in 0 g, tall and sooty under gravity, colour from the computed flame temperature |
| `js/viewer/smoke.js` | smoke particles carried by the cabin ventilation field (rising only with gravity) and streamlines |

Rules:

- Only call endpoints listed in `docs/API.md` (the test checks it).
- User text and research records go into the page with `textContent`; only the server-escaped
  chat answer (`message.html`) may use `innerHTML`.
- `?fps=2` caps the frame rate (useful for software rendering and screenshots).

Test: `pytest tests/frontend`. Run: start the backend (see CONTRIBUTING.md), open http://127.0.0.1:8000.
