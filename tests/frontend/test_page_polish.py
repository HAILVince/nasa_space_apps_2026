"""Pages: no backdrop blur, and the pages are written in the default language.

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


def test_hero_film_is_an_optional_extra():
    page = (FRONTEND / "index.html").read_text()
    site = (FRONTEND / "js" / "site.js").read_text()
    assert "<video" not in page                                    # created by site.js only when it will play
    for kind in ("webm", "mp4"):
        assert f"./assets/video/hero-loop.{kind}" in site
        f = FRONTEND / "assets" / "video" / f"hero-loop.{kind}"
        assert f.is_file() and f.stat().st_size < 3_000_000
    assert "saveData" in site and "reduced()" in site and "min-width: 901px" in site
    assert "addEventListener('load'" in site and "v.pause()" in site
