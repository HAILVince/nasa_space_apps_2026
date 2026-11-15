// Landing page backdrop on desktop: a video of the 3D scene whose time follows the scroll position.
// Scrolling down plays it forward, scrolling up plays it backward, and the video runs as fast as the
// page scrolls. It is never played, only seeked. The footage is the old live 3D page, recorded while
// scrolling (tests/perf/scroll_video.py); anchors.json holds where each chapter was in that recording.
// Phones, reduced motion, a missing anchors.json and a video that fails to load all leave the stills as
// they are (they stay underneath the video as well).
const KEYS = ['hero', 'ch1', 'ch2', 'ch3', 'ch4'];
const NARROW = 900;                                  // px: at this width and below the page keeps the stills
const VIDEO = './assets/video/landing-scrub.mp4';
const ANCHORS = './assets/video/anchors.json';
const EASE = 0.18;                                   // share of the remaining distance covered per 60 Hz frame

const num = (x) => typeof x === 'number' && Number.isFinite(x);

// '' when the video may run, else why not
export function skipReason({ width, reducedMotion }) {
  if (width <= NARROW) return 'narrow';
  if (reducedMotion) return 'reduced-motion';
  return '';
}

export function validAnchors(a) {
  return !!a && num(a.fps) && a.fps > 0 && num(a.px_per_frame) && a.px_per_frame > 0 && num(a.height) && a.height > 0
    && num(a.frames) && a.frames > 1 && num(a.end) && a.end > 0 && !!a.sections && KEYS.every((k) => num(a.sections[k]));
}

// Keyframes: the page scroll at which each chapter starts on this page (xs), and on the recorded page (ys).
// A chapter starts when the viewport centre reaches its top; the recording ends when the viewport centre
// reaches the end of ch4, where the solid sections begin.
export function keyframes(a, { tops, ch4Height, viewport }) {
  const xs = [0], ys = [0];
  for (const k of KEYS.slice(1)) { xs.push(tops[k] - viewport / 2); ys.push(a.sections[k] - a.height / 2); }
  xs.push(tops.ch4 + ch4Height - viewport / 2); ys.push(a.end);
  return { xs, ys };
}

// piecewise-linear: scroll on this page -> scroll on the recorded page (clamped at both ends)
export function mapScroll(y, { xs, ys }) {
  const n = xs.length - 1;
  if (!(y > xs[0])) return ys[0];
  if (y >= xs[n]) return ys[n];
  let i = 0;
  while (y >= xs[i + 1]) i++;
  const w = xs[i + 1] - xs[i];
  return w > 0 ? ys[i] + ((ys[i + 1] - ys[i]) * (y - xs[i])) / w : ys[i + 1];
}

// video time (s) for a scroll position; the recording moved px_per_frame pixels per frame at fps
export function videoTime(a, kf, y) {
  const t = mapScroll(y, kf) / a.px_per_frame / a.fps;
  return Math.min((a.frames - 1) / a.fps, Math.max(0, t));
}

// one step of easing towards the target; the same curve at any frame rate
export function follow(cur, target, dtMs) {
  return cur + (target - cur) * (1 - (1 - EASE) ** (Math.min(100, dtMs) / (1000 / 60)));
}

function layout(env) {
  const top = (k) => env.document.querySelector(`[data-scene=${k}]`).getBoundingClientRect().top + env.scrollY;
  const tops = {};
  for (const k of KEYS) tops[k] = top(k);
  return { tops, ch4Height: env.document.querySelector('[data-scene=ch4]').offsetHeight, viewport: env.innerHeight };
}

// `env` is the window; tests pass a stand-in. Resolves to the video element, or null when it stays off.
export async function start(env = globalThis) {
  const doc = env.document, backdrop = doc.querySelector('.backdrop');
  if (!backdrop || skipReason({ width: env.innerWidth, reducedMotion: env.matchMedia('(prefers-reduced-motion: reduce)').matches })) return null;
  let a = null;
  try { const r = await env.fetch(ANCHORS); a = r.ok ? await r.json() : null; } catch { /* no anchors: no video */ }
  if (!validAnchors(a)) return null;

  const v = doc.createElement('video');
  v.className = 'scrub'; v.muted = true; v.playsInline = true; v.preload = 'auto';
  for (const [k, val] of [['aria-hidden', 'true'], ['muted', ''], ['playsinline', ''], ['tabindex', '-1']]) v.setAttribute(k, val);
  const half = 0.5 / a.fps;
  let kf = null, time = 0, raf = 0, last = 0, ready = false;
  const aim = () => videoTime(a, kf, env.scrollY);
  const show = () => backdrop.classList.toggle('has-scrub', ready && env.innerWidth > NARROW);

  function frame(now) {
    raf = 0;
    const target = aim();
    time = follow(time, target, last ? now - last : 1000 / 60); last = now;
    if (Math.abs(target - time) < 1e-3) time = target;
    if (!v.seeking && Math.abs(time - v.currentTime) >= half) v.currentTime = time;       // seeks never pile up
    if (time !== target || Math.abs(time - v.currentTime) >= half) raf = env.requestAnimationFrame(frame);
    else last = 0;                                                                         // settled: sleep until the next scroll
  }
  const wake = () => { if (ready && !raf) raf = env.requestAnimationFrame(frame); };
  const measure = () => { kf = keyframes(a, layout(env)); };
  const off = () => { ready = false; v.remove(); show(); };

  v.addEventListener('error', off);
  v.addEventListener('loadeddata', () => {                  // first frame decoded: seek to where the page is, then fade in
    measure(); ready = true; time = aim();
    if (time >= half) { v.addEventListener('seeked', show, { once: true }); v.currentTime = time; } else show();
  }, { once: true });
  backdrop.append(v);
  v.src = VIDEO;
  env.addEventListener('scroll', wake, { passive: true });
  env.addEventListener('resize', () => { if (ready) { measure(); show(); wake(); } });
  env.addEventListener('load', () => { if (ready) { measure(); wake(); } });          // images and fonts can move the chapters
  return v;
}

if (typeof document !== 'undefined' && typeof window !== 'undefined') start(window).catch(() => {});
