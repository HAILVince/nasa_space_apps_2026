"""The landing page's scroll-scrubbed video backdrop (frontend/js/scrub.js): the mapping from scroll
position to video time, the fallbacks that keep today's stills, and how the page loads it.
The behaviour checks run in Node (scrub_check.mjs); the rest is plain file checks."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
VIDEO = FRONTEND / "assets" / "video"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_scrub_mapping_and_fallbacks():
    out = subprocess.run(["node", "--test", str(ROOT / "tests" / "frontend" / "scrub_check.mjs")],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr


def test_landing_page_loads_the_script_and_keeps_the_stills():
    page = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'src="./js/scrub.js"' in page
    assert (FRONTEND / "js" / "scrub.js").is_file()
    assert page.count('class="bg"') == 5                      # the five stills are still there for phones, reduced motion, errors
    assert "<video" not in page                               # the video is added by the script only when it will be used


def test_video_is_hidden_until_the_script_marks_it_ready():
    css = (FRONTEND / "css" / "app.css").read_text(encoding="utf-8")
    assert re.search(r"\.backdrop \.scrub\{[^}]*opacity:0", css)
    assert re.search(r"\.backdrop\.has-scrub \.scrub\{opacity:1\}", css)
    assert "body[data-section=investigations] .backdrop.has-scrub .scrub" in css      # fades out where the solid sections start
    assert "body[data-section=sources] .backdrop.has-scrub .scrub" in css


def test_shipped_footage_matches_its_anchors():
    anchors = json.loads((VIDEO / "anchors.json").read_text())
    assert anchors["fps"] in (30, 60) and anchors["height"] == 720
    assert anchors["px_per_frame"] == pytest.approx(720 / (1.6 * anchors["fps"]))      # one screen of scrolling is 1.6 s of video
    assert anchors["end"] == pytest.approx((anchors["frames"] - 1) * anchors["px_per_frame"])
    mp4 = VIDEO / "landing-scrub.mp4"
    assert mp4.is_file() and 0 < mp4.stat().st_size < 12_000_000
    assert mp4.read_bytes()[4:8] == b"ftyp"
