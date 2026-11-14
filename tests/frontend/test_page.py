"""Frontend workspace (frontend/): the page stays a bare chat and only uses the documented API."""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
API_DOC = Path(__file__).resolve().parents[2] / "docs" / "API.md"
PAGE = (FRONTEND / "index.html").read_text()


def test_no_styles_at_all():
    assert "<style" not in PAGE.lower() and 'rel="stylesheet"' not in PAGE and " style=" not in PAGE
    assert not list(FRONTEND.rglob("*.css"))


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
