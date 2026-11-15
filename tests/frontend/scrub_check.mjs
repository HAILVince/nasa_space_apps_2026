// Checks for frontend/js/scrub.js, the scroll-scrubbed video backdrop. Run by test_scrub.py, or alone:
//   node --test tests/frontend/scrub_check.mjs
// The module's maths are pure functions; start() is driven with a stand-in window so the fallback
// conditions (narrow screen, reduced motion, missing anchors, video error) can be checked without a browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const { skipReason, validAnchors, keyframes, mapScroll, videoTime, follow, start } =
  await import(pathToFileURL(path.join(root, 'frontend/js/scrub.js')).href);
const anchors = JSON.parse(readFileSync(path.join(root, 'frontend/assets/video/anchors.json'), 'utf8'));

// the page the footage was recorded on (1280×720) and a few other layouts
const OLD = { tops: anchors.sections, ch4Height: 792, viewport: anchors.height };
const near = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) <= eps, `${a} vs ${b}`);

test('the shipped anchors.json is valid', () => {
  assert.ok(validAnchors(anchors));
  assert.equal(anchors.fps, 30);
  near(anchors.px_per_frame, anchors.height / (1.6 * anchors.fps));          // one screen of scrolling = 1.6 s
  near(anchors.end, (anchors.frames - 1) * anchors.px_per_frame);            // end = scroll of the last frame
  const s = anchors.sections;
  assert.ok(s.hero === 0 && s.hero < s.ch1 && s.ch1 < s.ch2 && s.ch2 < s.ch3 && s.ch3 < s.ch4 && s.ch4 < anchors.end + anchors.height);
});

test('validAnchors rejects broken data', () => {
  for (const bad of [null, undefined, {}, 'x', { ...anchors, fps: 0 }, { ...anchors, frames: 1 }, { ...anchors, px_per_frame: 'a' },
    { ...anchors, end: NaN }, { ...anchors, sections: { hero: 0 } }, { ...anchors, sections: { ...anchors.sections, ch3: null } }]) {
    assert.equal(validAnchors(bad), false);
  }
});

test('fallback: phones and reduced motion keep the stills', () => {
  assert.equal(skipReason({ width: 1280, reducedMotion: false }), '');
  assert.equal(skipReason({ width: 901, reducedMotion: false }), '');
  assert.equal(skipReason({ width: 900, reducedMotion: false }), 'narrow');       // <= 900 px
  assert.equal(skipReason({ width: 390, reducedMotion: false }), 'narrow');
  assert.equal(skipReason({ width: 1920, reducedMotion: true }), 'reduced-motion');
});

test('keyframes: chapters start when the viewport centre reaches their top, hero at 0', () => {
  const kf = keyframes(anchors, OLD);
  assert.deepEqual(kf.xs.slice(0, 5), [0, 975 - 360, 1767 - 360, 2559 - 360, 3351 - 360]);
  assert.deepEqual(kf.ys.slice(0, 5), kf.xs.slice(0, 5));                         // same page: same positions
  assert.equal(kf.xs[5], 3351 + 792 - 360);                                       // end of ch4 at the viewport centre
  assert.equal(kf.ys[5], anchors.end);
});

test('mapScroll: identity on the recorded layout, clamped outside', () => {
  const kf = keyframes(anchors, OLD);
  for (let y = 0; y <= kf.xs[5]; y += 7) near(mapScroll(y, kf), y, anchors.end - kf.xs[5] + 1e-6);   // only the last frame is rounded up
  for (let i = 0; i < kf.xs.length; i++) near(mapScroll(kf.xs[i], kf), kf.ys[i]);                  // every keyframe maps exactly
  assert.equal(mapScroll(-500, kf), 0);
  assert.equal(mapScroll(1e9, kf), anchors.end);
});

test('mapScroll: layout-independent (taller or shorter page, other viewport)', () => {
  const tall = { tops: { hero: 0, ch1: 1500, ch2: 2900, ch3: 4300, ch4: 5700 }, ch4Height: 1200, viewport: 900 };
  const kf = keyframes(anchors, tall);
  // each chapter's start lands on the recorded chapter's start, whatever the page looks like
  assert.deepEqual(kf.xs, [0, 1500 - 450, 2900 - 450, 4300 - 450, 5700 - 450, 5700 + 1200 - 450]);
  for (let i = 1; i < 5; i++) near(mapScroll(kf.xs[i], kf), anchors.sections[['hero', 'ch1', 'ch2', 'ch3', 'ch4'][i]] - 360);
  // halfway through a chapter on this page = halfway through it on the recorded one
  const mid = (kf.xs[2] + kf.xs[3]) / 2;
  near(mapScroll(mid, kf), (kf.ys[2] + kf.ys[3]) / 2);
  // never decreasing as the page scrolls down
  let prev = -1;
  for (let y = -50; y < 8000; y += 13) { const m = mapScroll(y, kf); assert.ok(m >= prev); prev = m; }
});

test('mapScroll: zero-height segments do not divide by zero', () => {
  const kf = { xs: [0, 100, 100, 200], ys: [0, 10, 20, 30] };
  for (const y of [0, 50, 99.9, 100, 100.1, 150, 200, 300]) assert.ok(Number.isFinite(mapScroll(y, kf)));
});

test('videoTime: scroll / px_per_frame / fps, clamped to the video', () => {
  const kf = keyframes(anchors, OLD);
  assert.equal(videoTime(anchors, kf, 0), 0);
  assert.equal(videoTime(anchors, kf, -80), 0);
  near(videoTime(anchors, kf, 450), 1);                                            // 450 px = 30 frames = 1 s
  near(videoTime(anchors, kf, 720), 1.6);                                          // one screen = 1.6 s
  const last = (anchors.frames - 1) / anchors.fps;
  near(videoTime(anchors, kf, 1e9), last);
  assert.ok(videoTime(anchors, kf, 1e9) <= anchors.frames / anchors.fps);
  assert.ok(videoTime(anchors, kf, 2000) > videoTime(anchors, kf, 1999));          // forward with the scroll, backward against it
});

test('follow: same curve at any frame rate, settles on the target', () => {
  near(follow(0, 1, 1000 / 60), 0.18);
  const oneStep = follow(0, 1, 1000 / 30), twoSteps = follow(follow(0, 1, 1000 / 60), 1, 1000 / 60);
  near(oneStep, twoSteps);                                                          // 30 Hz = two 60 Hz frames
  const fine = Array.from({ length: 4 }).reduce((c) => follow(c, 1, 1000 / 240), 0);
  near(fine, follow(0, 1, 1000 / 60));                                              // 240 Hz = one 60 Hz frame
  let c = 0;
  for (let i = 0; i < 120; i++) c = follow(c, 5, 1000 / 60);
  near(c, 5, 1e-6);
  near(follow(2, 2, 16), 2);
  assert.ok(follow(0, 1, 5000) < 1);                                                // a long stall does not overshoot
});

// ---- start() with a stand-in window --------------------------------------------------------------------

class El extends EventTarget {
  constructor() { super(); this.attrs = {}; this.removed = false; this.children = []; this._t = 0; this.seeking = false; this.seeks = []; this.played = false;
    const cl = new Set(); this.classList = { toggle: (n, f) => (f ?? !cl.has(n) ? cl.add(n) : cl.delete(n)), contains: (n) => cl.has(n) }; }
  setAttribute(k, v) { this.attrs[k] = v; }
  append(c) { this.children.push(c); }
  remove() { this.removed = true; }
  play() { this.played = true; }
  get currentTime() { return this._t; }
  set currentTime(t) { this._t = t; this.seeks.push(t); this.seeking = true; }
  fire(type) { this.dispatchEvent(new Event(type)); }
}

function world({ width = 1280, reduced = false, anchorsResponse = { ok: true, json: async () => anchors }, scrollY = 0 } = {}) {
  const backdrop = new El(), video = new El(), queue = [], listeners = {};
  const env = {
    innerWidth: width, innerHeight: 720, scrollY,
    matchMedia: () => ({ matches: reduced }),
    fetch: async () => { if (anchorsResponse instanceof Error) throw anchorsResponse; return anchorsResponse; },
    addEventListener: (t, fn) => { (listeners[t] ||= []).push(fn); },
    requestAnimationFrame: (fn) => queue.push(fn),
    document: {
      querySelector: (sel) => {
        if (sel === '.backdrop') return backdrop;
        const k = /data-scene=(\w+)/.exec(sel)?.[1];
        return { getBoundingClientRect: () => ({ top: OLD.tops[k] - env.scrollY }), offsetHeight: 792 };
      },
      createElement: () => video,
    },
  };
  let now = 1000;
  const frames = (n) => { for (let i = 0; i < n && queue.length; i++) { const fn = queue.shift(); now += 1000 / 60; fn(now); } };
  const scrollTo = (y) => { env.scrollY = y; for (const fn of listeners.scroll || []) fn(); };
  const seeked = () => { video.seeking = false; video.fire('seeked'); };
  return { env, backdrop, video, queue, frames, scrollTo, seeked, listeners };
}

test('start: stays off on a narrow screen, with reduced motion, without anchors', async () => {
  for (const opts of [
    { width: 900 }, { width: 390 }, { reduced: true },
    { anchorsResponse: { ok: false, json: async () => ({}) } },                     // 404
    { anchorsResponse: new Error('network') },
    { anchorsResponse: { ok: true, json: async () => { throw new SyntaxError('bad json'); } } },
    { anchorsResponse: { ok: true, json: async () => ({ fps: 30 }) } },             // incomplete
  ]) {
    const w = world(opts);
    assert.equal(await start(w.env), null, JSON.stringify(Object.keys(opts)));
    assert.equal(w.backdrop.children.length, 0);                                    // no <video> added
    assert.equal(w.backdrop.classList.contains('has-scrub'), false);
    assert.equal((w.listeners.scroll || []).length, 0);                             // nothing listens
  }
});

test('start: a video that fails to load is removed and the stills stay', async () => {
  const w = world();
  const v = await start(w.env);
  assert.equal(v, w.video);
  assert.equal(v.attrs['aria-hidden'], 'true');
  assert.equal(v.muted, true); assert.equal(v.playsInline, true); assert.equal(v.preload, 'auto');
  assert.equal(w.backdrop.children.length, 1);
  assert.equal(w.backdrop.classList.contains('has-scrub'), false);                 // hidden until the first frame is ready
  v.fire('error');
  assert.equal(v.removed, true);
  assert.equal(w.backdrop.classList.contains('has-scrub'), false);
  w.scrollTo(500); w.frames(5);
  assert.equal(v.seeks.length, 0);                                                  // and it never seeks
});

test('start: first frame fades the video in; scrolling seeks it, never plays it', async () => {
  const w = world();
  const v = await start(w.env);
  v.fire('loadeddata');
  assert.equal(w.backdrop.classList.contains('has-scrub'), true);                  // at the top: shown at once
  w.scrollTo(720);                                                                  // one screen down
  assert.equal(w.queue.length, 1);
  w.frames(1);
  assert.ok(v.seeks.length === 1 && v.seeks[0] > 0 && v.seeks[0] < 1.6);           // eased, not a jump
  const firstSeek = v.seeks[0];
  w.frames(3);                                                                      // still seeking: no more seeks pile up
  assert.equal(v.seeks.length, 1);
  w.seeked();
  for (let i = 0; i < 200 && w.queue.length; i++) { w.frames(1); if (v.seeking) w.seeked(); }   // settles on 1.6 s
  assert.ok(Math.abs(v.currentTime - 1.6) < 0.5 / 30 + 1e-9, String(v.currentTime));
  assert.ok(v.seeks.length > 1 && v.seeks[1] > firstSeek);
  assert.equal(v.played, false);                                                    // never played
});

test('start: the loop sleeps when settled and wakes on scroll; scrolling up plays backward', async () => {
  const w = world();
  const v = await start(w.env);
  v.fire('loadeddata');
  w.scrollTo(1200);
  for (let i = 0; i < 400 && w.queue.length; i++) { w.frames(1); if (v.seeking) w.seeked(); }
  assert.equal(w.queue.length, 0);                                                  // asleep
  const there = v.currentTime;
  assert.ok(there > 2);
  w.scrollTo(300);                                                                  // up
  assert.equal(w.queue.length, 1);                                                  // woken by the scroll
  for (let i = 0; i < 400 && w.queue.length; i++) { w.frames(1); if (v.seeking) w.seeked(); }
  assert.ok(v.currentTime < there);
  assert.ok(Math.abs(v.currentTime - 300 / 15 / 30) < 0.5 / 30 + 1e-9);
  assert.equal(w.queue.length, 0);
});

test('start: loaded part-way down the page, it seeks there before showing', async () => {
  const w = world({ scrollY: 1500 });
  const v = await start(w.env);
  v.fire('loadeddata');
  assert.ok(v.seeks.length === 1 && v.seeks[0] > 3);
  assert.equal(w.backdrop.classList.contains('has-scrub'), false);                 // waits for the seek
  w.seeked();
  assert.equal(w.backdrop.classList.contains('has-scrub'), true);
});

test('start: resizing to a phone width hides the video', async () => {
  const w = world();
  const v = await start(w.env);
  v.fire('loadeddata');
  assert.equal(w.backdrop.classList.contains('has-scrub'), true);
  w.env.innerWidth = 700;
  for (const fn of w.listeners.resize) fn();
  assert.equal(w.backdrop.classList.contains('has-scrub'), false);
  w.env.innerWidth = 1280;
  for (const fn of w.listeners.resize) fn();
  assert.equal(w.backdrop.classList.contains('has-scrub'), true);
});
