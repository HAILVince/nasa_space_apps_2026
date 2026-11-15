#!/usr/bin/env python3
"""Records the footage for the landing page's scroll-scrubbed video backdrop.

The footage is the old live 3D landing page (commit c617a5a: a WebGL scene behind the text, a camera
dolly on the hero, one scene per chapter). It is rendered frame by frame on a stepped fake clock
while the page scrolls linearly, so every frame is reproducible and the speed is exact:
one screen of scrolling is `--seconds-per-screen` (1.6 s) of video. A chapter is therefore on screen
for ~1.8 s of video, so camera moves are shortened (--tween-ms) and the simulated fire clock runs
faster (--story-speed) than on the live page; everything else is the page's own code. The recording
ends when the viewport centre reaches the end of the ch4 section (where the solid sections begin).

    git worktree add ../bf-old c617a5a                      # the old live 3D landing page
    python tests/perf/scroll_video.py rig ../bf-old          # + this checkout's 3D viewer and model
    (cd ../bf-old && python -m venv .venv && .venv/bin/pip install -r requirements.txt \
        && .venv/bin/uvicorn app.main:app --port 8124)
    pip install playwright && playwright install chromium
    python tests/perf/scroll_video.py record  frames/            # frames/00000.jpg ... + anchors.json
    python tests/perf/scroll_video.py encode  frames/ frontend/assets/video/

The page layout, scroll handling and chapter scenes are the old landing page's; the 3D viewer (flame,
smoke, camera moves) and the cabin model are this checkout's, so the footage shows their current look.

Needs a GPU for sensible speed (use --channel msedge/chrome to drive an installed browser,
--headed if headless WebGL is black or slow, or --launch-arg=--use-angle=default).
The JPEG frames are scratch files: do not commit them. See tests/perf/README.md.
"""
import argparse
import datetime as dt
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

W, H = 1280, 720
FPS = 30
STEP_MS = 33                                   # fake-clock time per video frame
KEYS = ['hero', 'ch1', 'ch2', 'ch3', 'ch4']
ENV = {'hero': 'leo', 'ch1': 'leo', 'ch2': 'moon', 'ch3': 'leo', 'ch4': 'mars'}
HIDE = '.nav, main, .skip, .labels, .vignette, .poster, footer, .loader'
EPOCH = dt.datetime(2026, 11, 14, 12, 0, 0, tzinfo=dt.timezone.utc)

# fixed LCG for Math.random (window.__seed(n) re-seeds it)
SEED_JS = """(() => { let s = 1234567; window.__seed = (v) => { s = v >>> 0; };
  Math.random = () => ((s = (s * 1103515245 + 12345) >>> 0) / 4294967296); })();"""
# counts the section observer's deliveries, so the recorder can wait for "the page has noticed the scroll"
IO_JS = """(() => { const O = window.IntersectionObserver;
  window.__ioSeq = 0;
  window.IntersectionObserver = class extends O {
    constructor(cb, opts) {
      super((es, ob) => { cb(es, ob); for (const e of es) if (e.isIntersecting && e.target.dataset && e.target.dataset.scene) window.__ioSeq++; }, opts);
    }
  }; })();"""
NO_MOTION_JS = """addEventListener('DOMContentLoaded', () => { const st = document.createElement('style');
  st.textContent = '*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}';
  document.head.append(st); });"""
STATE_JS = """([k, env]) => document.body.dataset.section === k && !!window.bfx && window.bfx.story.key === k
  && !!window.bfx.story.result && window.bfx.viewer.envName === env"""
# the same starting state for every recording: settled hero camera, story clock at its start, seeded noise
RESET_JS = """([tweenMs, speed]) => {
  const v = window.bfx.viewer, st = window.bfx.story;
  v.tweenMs = tweenMs; st.speed = speed;          // see --tween-ms / --story-speed
  v.setView(v.view, true); v.tween = null; v.userTurning = false; v.dolly = 0;
  v.baseDist = v.camera.position.distanceTo(v.controls.target);
  v.shift = v.shiftTarget; v.shiftY = v.shiftYTarget; v.ptr.x = v.ptr.tx = 0; v.ptr.y = v.ptr.ty = 0;
  v.mixer?.setTime(0); if (v.envs.earth) v.envs.earth.rotation.y = 0;
  window.__seed(7); st.t = st.from; v.smoke.reset(); v._shadowT = 0; v.shadowsDirty();
  let n = 0; const c = v.composer, r = c.render.bind(c);
  c.render = (...a) => { n++; return r(...a); }; window.__renders = () => n;
}"""


# the frames are full-range JPEGs (BT.601): convert to limited-range BT.709 and tag it, so every browser shows the same colours
COLOR = 'scale=in_range=pc:in_color_matrix=bt601:out_range=tv:out_color_matrix=bt709,format=yuv420p'
TAGS = ['-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv']


def find_ffmpeg():
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit('ffmpeg not found: install it, or `pip install imageio-ffmpeg`')


class Recorder:
    def __init__(self, page, args):
        self.page, self.args = page, args

    def tick(self, ms=17, pause=0.04):
        self.page.clock.run_for(ms)
        time.sleep(pause)

    def until(self, expr, arg=None, label='', patience=0.0, limit=300.0):
        """Poll for a page condition in real time. The fake clock only advances once `patience`
        seconds have passed (0 = from the start): some loading steps need frames to make progress."""
        t0, ticked = time.time(), 0
        while not self.page.evaluate(expr, arg):
            if time.time() - t0 > limit:
                raise TimeoutError(f'timeout waiting for {label or expr}')
            if time.time() - t0 >= patience:
                self.tick()
                ticked += 1
            else:
                time.sleep(0.05)
        return ticked

    def wait_state(self, key, patience=0.0):
        n = self.until(STATE_JS, [key, ENV[key]], f'scene {key}', patience)
        if n and patience:
            print(f'  note: scene {key} needed {n} clock ticks to finish loading (not fully deterministic)')


def measure(page):
    return page.evaluate("""() => {
      const top = (el) => Math.round(el.getBoundingClientRect().top + scrollY);
      const sec = {}; for (const k of ['hero', 'ch1', 'ch2', 'ch3', 'ch4']) sec[k] = top(document.querySelector(`[data-scene=${k}]`));
      const ch4 = document.querySelector('[data-scene=ch4]');
      return { sections: sec, ch4_height: ch4.offsetHeight, inner: innerHeight, doc: document.documentElement.scrollHeight };
    }""")


def entered(sections, y):
    """The scene the page shows at scroll y. The page's IntersectionObserver band is the middle 4%
    of the viewport ('-48% 0 -48% 0'), so a section is entered when its top passes 52% of the height."""
    key = 'hero'
    for k in KEYS:
        if sections[k] - y <= H * 0.52:
            key = k
    return key


def record(args):
    from playwright.sync_api import sync_playwright
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('*.jpg'):
        f.unlink()
    launch = {'headless': not args.headed, 'args': args.launch_arg or []}
    if args.channel:
        launch['channel'] = args.channel
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)
        ctx = browser.new_context(viewport={'width': W, 'height': H}, device_scale_factor=args.scale)
        page = ctx.new_page()
        page.on('pageerror', lambda e: print('pageerror', e))
        for js in (SEED_JS, IO_JS, NO_MOTION_JS):
            page.add_init_script(js)
        page.clock.install(time=EPOCH)
        page.goto(f'{args.base}/?{args.query}')
        page.clock.pause_at(EPOCH + dt.timedelta(minutes=1))
        rec = Recorder(page, args)
        print(f'GPU: {page.evaluate("""() => { const g = document.createElement("canvas").getContext("webgl2");
          const e = g.getExtension("WEBGL_debug_renderer_info"); return g.getParameter(e ? e.UNMASKED_RENDERER_WEBGL : g.RENDERER); }""")}')
        rec.until('() => !!(window.bfx && window.bfx.viewer && window.bfx.viewer.habitat)', label='the 3D viewer')
        page.clock.fast_forward(1500)
        page.add_style_tag(content=f'{HIDE}{{visibility:hidden!important}}')

        lay = measure(page)
        sections = lay['sections']
        ppf = H / (args.seconds_per_screen * FPS)                         # scroll pixels per video frame
        end_y = sections['ch4'] + lay['ch4_height'] - H / 2              # the viewport centre reaches the end of ch4
        frames = math.ceil(end_y / ppf) + 1
        if args.limit:
            frames = min(frames, args.limit)
        end = (frames - 1) * ppf
        print(f'sections {sections}  px/frame {ppf}  frames {frames}  end {end}  video {round(W * args.scale)}x{round(H * args.scale)}')

        # warm-up: visit every chapter so models, terrain and simulations are loaded, then come back
        for k in KEYS[1:]:
            page.evaluate('(y) => scrollTo(0, y)', sections[k])
            rec.wait_state(k)
            for _ in range(8):
                rec.tick()
        page.evaluate('() => scrollTo(0, 0)')
        rec.wait_state('hero')
        for _ in range(8):
            rec.tick()
        page.evaluate(RESET_JS, [args.tween_ms, args.story_speed])
        now = page.evaluate('performance.now()')
        page.clock.fast_forward(max(0, 600000 - now))                    # same performance.now() at frame 0
        page.clock.run_for(100)
        time.sleep(0.2)

        # record
        section, expect, dup, renders0 = 'hero', 'hero', 0, page.evaluate('window.__renders()')
        t0 = time.time()
        for i in range(frames):
            y = round(i * ppf)
            seq = page.evaluate('(y) => { const s = window.__ioSeq; scrollTo(0, y); return s; }', y)
            want = entered(sections, y)
            if want != expect:                                            # a section switch is due
                t1 = time.time()
                while page.evaluate('window.__ioSeq') == seq:
                    if time.time() - t1 > 3:
                        print(f'  warning: no section observer callback at scroll {y} (expected {want})')
                        break
                    time.sleep(0.02)
                expect = want
            page.clock.run_for(STEP_MS)
            time.sleep(args.settle)
            r = page.evaluate('window.__renders()')
            if r == renders0:
                dup += 1                                                  # no new render since the last frame
            renders0 = r
            page.screenshot(path=str(out / f'{i:05d}.jpg'), type='jpeg', quality=92)
            cur = page.evaluate('document.body.dataset.section')
            if cur != section and cur in ENV:                             # the page switched scene: let it load
                print(f'  frame {i} scroll {y}: scene {section} -> {cur}')
                rec.wait_state(cur, patience=3.0)
                section = cur
            if i % 25 == 0:
                print(f'  frame {i}/{frames}  scroll {y}  scene {cur}  {time.time() - t0:.0f}s')
        browser.close()
    if dup:
        print(f'WARNING: {dup} frames had no new 3D render (the page frame cap is throttling the recorder)')
    anchors = {'fps': FPS, 'frames': frames, 'px_per_frame': ppf, 'width': W, 'height': H,
               'video_width': round(W * args.scale), 'video_height': round(H * args.scale),
               'sections': sections, 'end': end}
    (out / 'anchors.json').write_text(json.dumps(anchors, indent=2) + '\n')
    print(f'wrote {frames} frames and anchors.json to {out}')


def rig(args):
    """copy this checkout's 3D viewer code and cabin model into the old-landing-page worktree"""
    root, dst = Path(__file__).resolve().parents[2], Path(args.worktree)
    if not (dst / 'frontend' / 'js' / 'site.js').is_file():
        sys.exit(f'{dst} is not the c617a5a worktree (no frontend/js/site.js)')
    for sub in ('js/viewer', 'assets/3d'):
        shutil.copytree(root / 'frontend' / sub, dst / 'frontend' / sub, dirs_exist_ok=True)
        print('copied', sub)


def encode(args):
    frames, dest = Path(args.frames), Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    ff = find_ffmpeg()
    src = ['-y', '-framerate', str(FPS), '-i', str(frames / '%05d.jpg')]
    mp4 = dest / 'landing-scrub.mp4'
    crf = args.crf
    while True:
        subprocess.run([ff, *src, '-vf', COLOR, '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-g', '4', '-bf', '0',
                        '-pix_fmt', 'yuv420p', *TAGS, '-movflags', '+faststart', str(mp4)], check=True)
        mb = mp4.stat().st_size / 1e6
        print(f'{mp4.name}: {mb:.2f} MB at crf {crf}')
        if mb <= args.max_mb or crf >= 36:
            break
        crf += 2
    if args.webm:
        webm = dest / 'landing-scrub.webm'
        subprocess.run([ff, *src, '-vf', COLOR, '-c:v', 'libvpx-vp9', '-crf', str(crf + 8), '-b:v', '0', '-g', '4',
                        '-auto-alt-ref', '0', '-lag-in-frames', '0', '-pix_fmt', 'yuv420p', *TAGS, str(webm)], check=True)
        print(f'{webm.name}: {webm.stat().st_size / 1e6:.2f} MB')
    shutil.copy(frames / 'anchors.json', dest / 'anchors.json')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('record', help='render the JPEG frames and anchors.json')
    r.add_argument('out')
    r.add_argument('--base', default='http://127.0.0.1:8124')
    r.add_argument('--query', default='q=high', help='page query string (q=high: highest quality tier)')
    r.add_argument('--seconds-per-screen', type=float, default=1.6)
    r.add_argument('--channel', help='installed browser to drive: msedge, chrome (default: bundled Chromium)')
    r.add_argument('--headed', action='store_true')
    r.add_argument('--launch-arg', action='append', help='extra browser flag, e.g. --launch-arg=--use-angle=default')
    r.add_argument('--settle', type=float, default=0.06, help='real seconds to let the GPU present a frame before the screenshot')
    r.add_argument('--scale', type=float, default=1.5,
                   help='device scale factor: 1.5 renders 1920x1080 (the page\'s high tier renders at most 1.5x; page layout stays 1280x720)')
    r.add_argument('--tween-ms', type=float, default=1300,
                   help='camera move between scenes (the live page used 2200: a chapter is on screen for only ~1.8 s of video)')
    r.add_argument('--story-speed', type=float, default=12,
                   help='simulated seconds per second for the fire (the live page used 6): lets the flame show within a chapter')
    r.add_argument('--limit', type=int, default=0, help='record only the first N frames (testing)')
    g = sub.add_parser('rig', help='copy this checkout\'s 3D viewer and cabin model into the old-landing-page worktree')
    g.add_argument('worktree')
    e = sub.add_parser('encode', help='encode the frames to landing-scrub.mp4 (+ .webm) and copy anchors.json')
    e.add_argument('frames')
    e.add_argument('dest')
    e.add_argument('--crf', type=int, default=24)
    e.add_argument('--max-mb', type=float, default=12)
    e.add_argument('--webm', action='store_true')
    a = ap.parse_args()
    {'record': record, 'rig': rig, 'encode': encode}[a.cmd](a)
