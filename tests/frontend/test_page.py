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


def test_fire_spread_page_is_local_and_linked():
    spread = (FRONTEND / "spread.html").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in spread and "./js/spread.js" in spread
    assert "./spread.html" in PAGE and "./spread.html" in LAB


def test_spread_page_calls_only_documented_flame_endpoints():
    spread = (FRONTEND / "spread.html").read_text(encoding="utf-8")
    used = set(re.findall(r"`(/api/[a-z/]+)\?", spread))
    documented = set(re.findall(r"`GET (/api/flame/[a-z]+)`", API_DOC.read_text()))
    assert used and used <= documented, f"undocumented: {used - documented}"
    nomex = spread.split("const MAT")[1].split("nomex:")[1].split("},\n")[0]
    assert "ASSUMED" not in nomex


def test_teammate_sim_upload_has_calculator_check():
    sim = (Path(__file__).resolve().parents[2] / "blackfox" / "db" / "knowledge" / "habitat_fire_sim.html")
    if sim.is_file():  # the teammate replaces this file by upload; /fire-sim falls back to spread.html
        text = sim.read_text(encoding="utf-8")
        used = set(re.findall(r"`(/api/[a-z/]+)\?", text))
        documented = set(re.findall(r"`GET (/api/flame/[a-z]+)`", API_DOC.read_text()))
        assert used <= documented, f"undocumented: {used - documented}"
