"""The "show me" guide: every show_on_page target exists on its page, and the help strings exist in both languages."""

import re
from pathlib import Path

from blackfox.tools.ui_tools import TARGETS

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
HTML = {"home": (FRONTEND / "index.html").read_text(), "lab": (FRONTEND / "lab.html").read_text()}
JS = {p.name: p.read_text() for p in (FRONTEND / "js").glob("*.js")}


def test_every_target_is_on_its_page_exactly_once():
    for target, (page, _) in TARGETS.items():
        assert HTML[page].count(f'data-guide="{target}"') == 1, (target, page)
        other = "lab" if page == "home" else "home"
        assert f'data-guide="{target}"' not in HTML[other], target
    on_pages = set(re.findall(r'data-guide="([a-z_0-9]+)"', HTML["home"] + HTML["lab"]))
    assert on_pages == set(TARGETS)                       # nothing on the pages the AI cannot name


def test_view_targets_name_a_real_simulator_view():
    views = set(re.findall(r'data-guide-view="([a-z0-9]+)"', HTML["lab"]))
    buttons = set(re.findall(r'data-v="(3d|2d|ship3d)"', HTML["lab"][HTML["lab"].index('id="simView"'):]))
    assert views and views <= buttons


def test_quick_start_steps_point_at_real_targets():
    steps = re.findall(r'data-show="([a-z_]+)"', HTML["lab"])
    assert len(steps) == 3 and set(steps) <= set(TARGETS)


def test_chat_and_both_pages_run_the_guide():
    assert "resumeGuide()" in JS["common.js"] and "from './guide.js'" in JS["common.js"]
    assert "if (data.ui) showFromChat(msg, data.ui)" in JS["lab.js"]
    g = JS["guide.js"]
    assert "sessionStorage" in g and "prefers-reduced-motion" in g and "guide-hl" in g and "scrollIntoView" in g
    assert "innerHTML" not in g                            # the AI's note is text, never HTML


def test_help_strings_exist_in_both_languages():
    i18n = JS["i18n.js"]
    hu, en = i18n[i18n.index("  hu: {"):i18n.index("  en: {")], i18n[i18n.index("  en: {"):]
    keys = ["hero_sub", "hero_ask", "qs_title", "qs_hide", "qs_1", "qs_2", "qs_3", "qs_ask", "hint_env", "hint_atm",
            "hint_src", "hint_resp", "try_k", "try_1", "try_2", "try_3", "try_4", "show_me", "guide_here", "guide_back",
            "v_idle_t", "v_idle"]
    for k in keys:
        assert f"{k}: '" in hu and f"{k}: '" in en, k
    for k in re.findall(r'data-i18n="((?:qs|hint|try|hero)_[a-z0-9_]+)"', HTML["home"] + HTML["lab"]):
        assert k in keys, k
