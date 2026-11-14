"""Frontend workspace (frontend/): the dashboard and chat use accessible markup and the documented API."""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
API_DOC = Path(__file__).resolve().parents[2] / "docs" / "API.md"
PAGE = (FRONTEND / "index.html").read_text()


def test_stylesheet_is_served_locally_and_inputs_are_labeled():
    assert 'href="/app.css"' in PAGE
    assert (FRONTEND / "app.css").is_file()
    assert 'for="m"' in PAGE and 'for="agent-language"' in PAGE
    assert 'name="viewport"' in PAGE


def test_enter_sends_shift_enter_newline():
    assert 'e.key === "Enter"' in PAGE and "!e.shiftKey" in PAGE


def test_only_documented_endpoints():
    used = set(re.findall(r'fetch\("(/api/[a-z/]+)"', PAGE))
    documented = set(re.findall(r"`(?:GET|POST) (/api/[a-z/]+)`", API_DOC.read_text()))
    assert used and used <= documented, f"undocumented: {used - documented}"


def test_untrusted_text_not_injected_as_html():
    # user text and snapshots go through textContent; only the server-rendered (escaped) answer uses innerHTML
    assert "p.textContent = msg.text" in PAGE and "pre.textContent = msg.snapshot" in PAGE
    assert PAGE.count("innerHTML") == 2   # the "<b></b>" label + msg.html
