"""Frontend workspace (frontend/): the fire-safety lab page, its local assets and the API contract."""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
API_DOC = Path(__file__).resolve().parents[2] / "docs" / "API.md"
PAGE = (FRONTEND / "index.html").read_text()
LAB = (FRONTEND / "lab.html").read_text()
JS = {p.relative_to(FRONTEND).as_posix(): p.read_text() for p in (FRONTEND / "js").rglob("*.js")}
APP = JS["js/lab.js"] + JS["js/common.js"]


# Links that the backend answers itself instead of a file in frontend/ (see app/main.py);
# tests/backend checks that each one really responds.
SERVER_ROUTES = {"fire-sim"}


def test_page_assets_are_local_files():
    for ref in re.findall(r'(?:src|href|srcset|data-srcset)="\./([^"#]+)"', PAGE + LAB):
        ref = ref.split("?")[0]
        if ref not in SERVER_ROUTES:
            assert (FRONTEND / ref).is_file(), ref
    imports = re.findall(r'"three(?:/addons/)?":"\./([^"]+)"', LAB)      # the landing page runs no 3D
    assert imports and all((FRONTEND / i).exists() for i in imports)
    for src in JS.values():
        for ref in re.findall(r"'\./assets/([^'`$]+)'", src):
            assert (FRONTEND / "assets" / ref).is_file(), ref
    for f in ("habitat.glb", "habitat_ao.webp", "rocks.glb", "moon_globe.webp", "terrain_moon.json", "terrain_mars.json"):
        assert (FRONTEND / "assets" / "3d" / f).is_file(), f


def test_vendored_three_addons_resolve():
    addons = FRONTEND / "vendor" / "three" / "addons"
    for src in JS.values():
        for ref in re.findall(r"from 'three/addons/([^']+)'", src):
            assert (addons / ref).is_file(), ref
    for path in addons.rglob("*.js"):
        for ref in re.findall(r"from '(\.\.?/[^']+)'", path.read_text()):
            assert (path.parent / ref).resolve().is_file(), f"{path.name} -> {ref}"


def test_only_documented_endpoints():
    used = set(re.findall(r"['`](/api/[a-z/]+)", "\n".join(JS.values())))
    documented = set(re.findall(r"`(?:GET|POST) (/api/[a-z/{}]+)`", API_DOC.read_text()))
    documented = {d.split("{")[0].rstrip("/") + ("/" if "{" in d else "") for d in documented}
    assert used and used <= documented, f"undocumented: {used - documented}"


def test_controls_for_every_scenario_input():
    for el in ("envGrid", "pressure", "o2", "temp", "location", "material", "vent", "autoVent", "suppression", "respTime"):
        assert f'id="{el}"' in LAB, el
    assert set(re.findall(r'data-v="(\w+)"', LAB)) >= {"exterior", "cutaway", "interior", "fire", "normal", "xray", "thermal", "airflow"}


def test_enter_sends_shift_enter_newline():
    assert "e.key === 'Enter' && !e.shiftKey && !e.isComposing" in APP


def test_untrusted_text_never_becomes_html():
    # research records and user text are written with textContent; innerHTML only takes the
    # server-escaped chat answer and locally formatted numbers
    assert "d.innerHTML = html;" in APP and "d.textContent = text;" in APP
    assert "innerHTML" not in JS["js/common.js"] and "innerHTML" not in JS["js/site.js"]
    for line in APP.splitlines():
        if "innerHTML =" in line and "''" not in line:
            assert "html" in line or "b.innerHTML = v" in line or "ends.innerHTML" in line, line


def test_dashboard_and_chat_inputs_are_labeled():
    for el in ("scenario", "focus", "research-query", "research-results", "compare"):
        assert f'id="{el}"' in PAGE, el
    for el in ("agent-language", "chatInput"):
        assert f'id="{el}"' in LAB, el
    assert 'for="agent-language"' in LAB and 'for="chatInput"' in LAB and 'name="viewport"' in PAGE + LAB
    dash = JS["js/dashboard.js"]
    assert "innerHTML" not in dash and "textContent" in dash


def test_landing_links_to_the_lab_page():
    assert './lab.html' in PAGE and './js/site.js' in PAGE and './js/lab.js' in LAB


def test_one_main_simulator_takes_over_the_fire_spread_links():
    assert 'href="./lab.html?view=2d" data-i18n="nav_spread"' in PAGE and 'href="./lab.html?view=2d" data-i18n="nav_spread"' in LAB
    assert 'href="./lab.html?view=2d" data-i18n="cta_how"' in PAGE
    # the old stand-alone page stays (it also holds the PSI "Variables" view); menus open the main simulator
    assert (FRONTEND / "spread.html").exists()


def test_lab_runs_only_when_the_user_starts_it():
    lab = JS["js/lab.js"]
    assert "runSimulation" not in lab and "rerun(" not in lab                  # no automatic runs any more
    assert "$('startBtn').onclick = start;" in lab and "api('/api/sim/start'" in lab
    body = lab[lab.index("function changed()"):]
    body = body[:body.index("\n}\n")]
    assert "api(" not in body and "start(" not in body                          # a change never starts a run
    for el in ("startBtn", "startNote", "simView", "spread2d", "spCanvas", "lining", "qualitySel", "load3d"):
        assert f'id="{el}"' in LAB, el


def test_device_profile_sets_quality_but_never_physics():
    dev = JS["js/device.js"]
    assert all(k in dev for k in ("hardwareConcurrency", "deviceMemory", "WEBGL_debug_renderer_info", "pointer: coarse", "saveData"))
    engine = JS["js/spread/engine.js"]
    assert "M.step(0.1)" in engine and "budgetMs" in engine                    # fixed physics step, per-frame budget
    assert "this.acc %= 0.1" in engine                                          # falls behind instead of skipping physics
    assert "import { createModel } from './model.js'" in engine


def test_teammate_sim_upload_has_calculator_check():
    sim = (Path(__file__).resolve().parents[2] / "blackfox" / "db" / "knowledge" / "habitat_fire_sim.html")
    if sim.is_file():  # the teammate replaces this file by upload; /fire-sim falls back to spread.html
        text = sim.read_text(encoding="utf-8")
        used = set(re.findall(r"`(/api/[a-z/]+)\?", text))
        documented = set(re.findall(r"`GET (/api/flame/[a-z]+)`", API_DOC.read_text()))
        assert used <= documented, f"undocumented: {used - documented}"


def test_lab_shows_a_scenario_the_ai_set():
    lab = JS["js/lab.js"]
    assert "if (data.scenario) applyScenario(data.scenario)" in lab
    body = lab[lab.index("function applyScenario"):]
    body = body[:body.index("\n}\n")]
    assert all(call in body for call in ("syncInputs()", "viewer?.setEnvironment(", "changed()"))
    assert "Object.keys(S)" in body                 # applies exactly the fields the lab keeps


def test_lab_accession_badge_links_to_the_psi_record():
    lab, i18n = JS["js/lab.js"], JS["js/i18n.js"]
    assert "a.href = inv.psiUrl" in lab and "a.target = '_blank'" in lab and "a.rel = 'noopener noreferrer'" in lab
    assert "if (!inv?.psiUrl) return null" in lab                      # no psiUrl, no link
    assert "psiLink(invs.get(e.accession), e.accession)" in lab        # the accession badge itself is the link
    assert "a.title = a.ariaLabel" in lab and "t('psi_open')" in lab   # accessible label, not only coloured text
    assert len(re.findall(r"psi_open: '[^']+'", i18n)) == 2
    assert "PSI rekord megnyitása" in i18n and "Open the PSI record" in i18n
