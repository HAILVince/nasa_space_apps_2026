// Export the deck for submission and for the day, from the local preview server (pitch/ on port 8766).
//
//   node pitch/tools/export.mjs pdf            ->  pitch/deck.pdf       one page per slide (1-12, then A1-A3), final state
//   node pitch/tools/export.mjs video [secs]   ->  pitch/deck-loop.mp4  1920 x 1080, 30 fps, the autoplay loop once
//
// Start the server first:  python3 -m http.server 8766 --directory pitch
// The video is rendered on a manual clock (CLOCK below): timers, requestAnimationFrame and every CSS
// transition or Web Animation move exactly one frame between screenshots, so the motion is even however
// slow the machine is. Needs ffmpeg; the PDF needs pdfunite (poppler).
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launch, sleep } from './cdp.mjs';

const BASE = process.env.DECK || 'http://127.0.0.1:8766/deck.html';
const out = name => fileURLToPath(new URL(`../${name}`, import.meta.url));
const mode = process.argv[2];
if (mode !== 'pdf' && mode !== 'video') { console.error('usage: node export.mjs pdf | video [seconds]'); process.exit(2); }

// Replaces the page's clock. __advance(ms) runs due timers and one animation frame, then moves every
// CSS transition and Web Animation to the same moment (each is paused and placed by hand).
const CLOCK = `(() => {
  let now = performance.now(), seq = 0, frames = [];
  const timers = new Map(), born = new WeakMap();
  performance.now = () => now;
  const dateBase = Date.now() - now; Date.now = () => Math.round(dateBase + now);
  window.requestAnimationFrame = cb => { frames.push({ id: ++seq, cb }); return seq; };
  window.cancelAnimationFrame = id => { frames = frames.filter(f => f.id !== id); };
  window.setTimeout = (cb, ms = 0, ...a) => { timers.set(++seq, { at: now + Math.max(0, +ms || 0), cb, a }); return seq; };
  window.clearTimeout = id => timers.delete(id);
  window.__advance = ms => {
    const end = now + ms;
    for (;;) {
      let next = null;
      for (const [id, t] of timers) if (t.at <= end && (!next || t.at < next[1].at)) next = [id, t];
      if (!next) break;
      timers.delete(next[0]); now = Math.max(now, next[1].at);
      typeof next[1].cb === 'function' && next[1].cb(...next[1].a);
      sync();
    }
    now = end;
    const run = frames; frames = [];
    run.forEach(f => f.cb(now));
    sync();
    return true;
  };
  function sync() {
    for (const a of document.getAnimations()) {
      if (!born.has(a)) { born.set(a, now - (a.currentTime || 0)); a.pause(); }
      a.currentTime = now - born.get(a);
    }
  }
})()`;

const page = await launch();
const ids = await (async () => {
  await page.goto(`${BASE}?still`, 1500);
  return page.eval(`[...document.querySelectorAll('#stage > .slide')].map((s, i, all) => s.hasAttribute('data-appendix')
    ? 'a' + (i - all.filter(x => !x.hasAttribute('data-appendix')).length + 1) : String(i + 1))`);
})();

if (mode === 'pdf') {
  const dir = mkdtempSync(join(tmpdir(), 'deck-pdf-'));
  const files = [];
  for (const id of ids) {
    await page.goto('about:blank', 100);
    await page.goto(`${BASE}?still#${id}`, 1200);
    await page.eval('document.fonts.ready.then(() => true)');
    const r = await page.send('Page.printToPDF', { printBackground: true, preferCSSPageSize: true, pageRanges: '1',
      marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0 });
    const file = join(dir, `${String(files.length).padStart(2, '0')}.pdf`);
    writeFileSync(file, Buffer.from(r.data, 'base64'));
    files.push(file);
  }
  execFileSync('pdfunite', [...files, out('deck.pdf')]);
  rmSync(dir, { recursive: true, force: true });
  console.log(`deck.pdf: ${files.length} pages (${ids.join(' ')})`);
} else {
  const FPS = 30;
  const secs = parseFloat(process.argv[3]) || await page.eval(`[...document.querySelectorAll('#stage > .slide:not([data-appendix])')].reduce((a, s) => a + +s.dataset.dur, 0)`);
  await page.goto('about:blank', 100);
  await page.goto(`${BASE}#1`, 2000);                       // loaded and fonts in, sitting on slide 1
  await page.eval(CLOCK);
  await page.eval(`document.body.classList.add('idle'); dispatchEvent(new KeyboardEvent('keydown', { key: 'Home' })); dispatchEvent(new KeyboardEvent('keydown', { key: 'a' })); true`);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out('deck-loop.mp4')], { stdio: ['pipe', 'inherit', 'inherit'] });
  const frames = Math.round(secs * FPS);
  const t0 = Date.now();
  for (let i = 0; i < frames; i++) {
    await page.eval(`__advance(${1000 / FPS})`);
    const r = await page.send('Page.captureScreenshot', { format: 'jpeg', quality: 92 });
    if (!ff.stdin.write(Buffer.from(r.data, 'base64'))) await new Promise(res => ff.stdin.once('drain', res));
    if (i % (FPS * 10) === 0) console.log(`${(i / FPS).toFixed(0)} s rendered, ${((Date.now() - t0) / 1000).toFixed(0)} s elapsed`);
  }
  ff.stdin.end();
  await new Promise(res => ff.on('close', res));
  console.log(`deck-loop.mp4: ${frames} frames, ${secs} s`);
}
if (page.errors.length) console.log('page errors:', page.errors);
await page.close();
