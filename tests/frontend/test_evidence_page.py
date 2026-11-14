"""Frontend workspace: the evidence page (frontend/evidence.html), built in the site's own look."""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
PAGE = (FRONTEND / "evidence.html").read_text()
JS = (FRONTEND / "js" / "evidence.js").read_text()
CSS = (FRONTEND / "css" / "evidence.css").read_text()
I18N = (FRONTEND / "js" / "i18n.js").read_text()


def test_assets_are_local_files_and_the_site_stylesheet_comes_first():
    for ref in re.findall(r'(?:src|href)="\./([^"#?]+)', PAGE):
        assert (FRONTEND / ref).is_file() or ref == "", ref
    assert PAGE.index("./css/app.css") < PAGE.index("./css/evidence.css")
    assert "http" not in re.sub(r'href="https://github[^"]+"', "", PAGE)        # no CDN, no web fonts


def test_page_uses_the_site_type_and_colours_not_its_own():
    assert "@font-face" not in CSS and "font-family:" not in CSS.replace("font-family:var(--mono)", "")
    # app.css names its serif face "Serif", which CSS reads as the generic keyword: a system font
    assert "var(--serif)" not in CSS
    assert not re.findall(r"#[0-9a-fA-F]{6}\b", CSS.replace("#cbc7c0", ""))     # colours are app.css tokens
    assert "animation" not in CSS and "transition" not in CSS                   # nothing moves on a data view


def test_every_string_exists_in_both_languages():
    keys = set(re.findall(r'data-i18n="(\w+)"', PAGE)) | set(re.findall(r"t\('(\w+)'", JS))
    keys |= {f"ev_phase_{p}" for p in ("solid", "liquid", "gas", "aerosol", "none")}
    hu, en = I18N.split("\n  en: {")
    for key in sorted(keys):
        assert f"{key}:" in hu and f"{key}:" in en, key


def test_api_text_never_becomes_html():
    assert "innerHTML" not in JS and "insertAdjacentHTML" not in JS and "textContent" in JS
    assert set(re.findall(r"['`](/api/[a-z/]+)", JS)) == {"/api/flame/gapmap", "/api/flame/context"}


def test_gap_map_is_the_lab_chart_and_python_does_the_counting():
    assert "gapMap(" in JS and "from './charts.js'" in JS and 'id="evMap"' in PAGE and "<figcaption>" in PAGE
    for field in ("map.coverage?.[", "map.coverageByPhase?.[", "map.coveredBy?.["):
        assert field in JS, field                      # the endpoint's counts, never recomputed in the page
    assert "overlap" not in JS
    charts = (FRONTEND / "js" / "charts.js").read_text()
    assert charts.count("data-hab") == 3 and "[data-hab].is-off" in CSS      # the picked habitat stands out
    assert 'id="evMicro"' in PAGE and "micro_only=true" in JS and 'id="evCaveats"' in PAGE


def test_states_and_controls():
    for el in ("evPick", "evStatus", "evRetry", "evReadout", "evAtmosphere", "evCoverage", "evLegend", "evClip"):
        assert f'id="{el}"' in PAGE, el
    assert 'role="status"' in PAGE and 'aria-labelledby="evPickLabel"' in PAGE and 'name="viewport"' in PAGE
    assert "ev_error" in JS and "ev_loading" in JS and "aria-pressed" in JS


def test_other_pages_link_here():
    for name in ("index.html", "lab.html"):
        assert 'href="./evidence.html" data-i18n="nav_evidence"' in (FRONTEND / name).read_text(), name
