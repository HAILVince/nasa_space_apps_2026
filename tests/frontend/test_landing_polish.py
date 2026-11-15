"""Landing page: the hero film stays an optional extra, and the pages are written in the default language.

- The hero film (blender/build_cinematic.py) must never cost a visitor who does not see it: no
  download before the page has loaded, none on phones, with reduced motion or a data saver, and no
  decoding while another chapter's backdrop is on screen. Its first frame is the hero still.
- The HTML is the English text (the site's default), so an English visitor never sees Hungarian
  text before the scripts run, and the Latin Extended font subsets are not fetched for nothing.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
PAGE = (FRONTEND / "index.html").read_text()
SITE = (FRONTEND / "js" / "site.js").read_text()
CSS = (FRONTEND / "css" / "app.css").read_text()


def test_hero_film_is_fetched_only_on_request():
    video = re.search(r"<video[^>]*class=\"film\"[^>]*>(.*?)</video>", PAGE, re.S)
    assert video, "hero film element"
    tag = video.group(0)[: video.group(0).index(">") + 1]
    for attr in ("muted", "loop", "playsinline", 'preload="none"'):
        assert attr in tag, attr
    assert "autoplay" not in tag and "poster=" not in tag            # the still under it is the poster
    sources = re.findall(r"<source ([^>]*)>", video.group(1))
    assert sources and all("data-src=" in s and " src=" not in s for s in sources)
    for kind in ("webm", "mp4"):
        f = FRONTEND / "assets" / "video" / f"hero-loop.{kind}"
        assert f.is_file() and f.stat().st_size < 3_000_000, f        # a backdrop, not a download


def test_hero_film_respects_the_visitor():
    assert "prefers-reduced-motion" in SITE or "reduced()" in SITE
    assert "saveData" in SITE and "effectiveType" in SITE
    assert "min-width: 900px" in SITE                                  # phones keep the portrait still
    assert "addEventListener('load'" in SITE                           # never competes with first paint
    assert "v.pause()" in SITE and "visibilitychange" in SITE          # no decoding off screen
    assert re.search(r"@media \(prefers-reduced-motion:reduce\)\{\.backdrop \.film\{display:none\}\}", CSS)


def test_no_backdrop_blur():
    # the frontend README promises none: blur over a moving backdrop costs a full-screen pass per frame
    for css in (FRONTEND / "css").glob("*.css"):
        assert "backdrop-filter" not in css.read_text(), css.name


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_pages_are_written_in_the_default_language():
    script = (
        "const fs=require('fs');const s=fs.readFileSync(process.argv[1],'utf8');"
        "const a=s.indexOf('const T = {');const b=s.indexOf('\\n};\\n',a)+3;"
        "process.stdout.write(JSON.stringify(new Function(s.slice(a,b).replace('const T =','return'))().en));"
    )
    out = subprocess.run(["node", "-e", script, str(FRONTEND / "js" / "i18n.js")], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    en = json.loads(out.stdout)
    unescape = lambda t: t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    for name in ("index.html", "lab.html", "evidence.html", "spread.html"):
        html = (FRONTEND / name).read_text()
        assert re.search(r'<html lang="en"[ >]', html), name
        # elements whose whole content is text: it must be the English string i18n.js writes
        for key, text in re.findall(r'data-i18n="([a-z0-9_]+)"[^>]*>([^<]*)</', html):
            assert key in en, (name, key)
            assert unescape(text) == en[key], (name, key, text)
