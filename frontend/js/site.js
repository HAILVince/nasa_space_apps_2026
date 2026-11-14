// The landing page: the 3D scene stays behind the page; the section in the middle of the
// screen picks what it shows. Drag turns the module; the wheel scrolls the page.
import { getLang } from './i18n.js';
import { $, api, loadEvidence, bindChrome } from './common.js';

let catalog = null, viewer = null, page = 'boot', lastFrame = 0;
const story = { key: null, result: null, t: 0, from: 0, loop: 120, speed: 6 };
const cache = new Map();
const SCENES = {
  hero: { env: 'leo', view: 'exterior', mode: 'normal', rotate: true, shift: 0, shiftY: 0.27, run: { environment: 'leo', location: 'galley' }, from: 0 },
  ch1: { env: 'leo', view: 'fire', mode: 'normal', shift: 0.2, run: { environment: 'leo', location: 'glovebox', material: 'delrin', auto_vent_shutdown: false, vent_cm_s: 4 }, from: 6, loop: 70 },
  ch2: { env: 'moon', view: 'fire', mode: 'normal', shift: 0.2, run: { environment: 'moon', location: 'galley', material: 'polyethylene', auto_vent_shutdown: false, vent_cm_s: 12 }, from: 4, loop: 60 },
  ch3: { env: 'leo', view: 'cutaway', mode: 'airflow', shift: 0.18, run: { environment: 'leo', location: 'galley', material: 'polyethylene', auto_vent_shutdown: false, vent_cm_s: 15 }, from: 2, loop: 90 },
  ch4: { env: 'mars', view: 'exterior', mode: 'normal', rotate: true, shift: -0.3, run: { environment: 'mars', location: 'stowage' }, from: 0 },
};
const narrow = () => matchMedia('(max-width: 900px)').matches;
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

function rowAt(r, time) {
  const s = r.series, dt = s.length > 1 ? s[1].t - s[0].t : 2;
  const i = Math.min(s.length - 2, Math.max(0, Math.floor(time / dt)));
  const a = s[i], b = s[i + 1], f = Math.min(1, Math.max(0, (time - a.t) / dt));
  const out = {};
  for (const k of Object.keys(a)) out[k] = typeof a[k] === 'number' ? a[k] + (b[k] - a[k]) * f : a[k];
  return out;
}

async function enterScene(key) {
  if (!viewer || !catalog) return;
  if (!SCENES[key]) { viewer.setActive(false); return; }       // solid sections: stop rendering
  viewer.setActive(true);
  const sc = SCENES[key];
  viewer.setAutoRotate(!!sc.rotate && !reduced());
  viewer.setShift(narrow() ? 0 : innerWidth * sc.shift, innerHeight * (sc.shiftY || 0));
  const id = story.key = key;
  let r = cache.get(key);
  if (!r) { try { r = await api('/api/fire/simulate', sc.run); cache.set(key, r); } catch { return; } }
  if (story.key !== id) return;
  await viewer.setEnvironment(sc.env, catalog.environments[sc.env].g_fraction);
  if (story.key !== id) return;
  Object.assign(story, { result: r, from: sc.from, t: sc.from, loop: sc.loop || 120 });
  viewer.setScenario(r, catalog);
  viewer.setTime(story.t, rowAt(r, story.t), -1);
  viewer.setMode(sc.mode);
  viewer.setView(sc.view);
}

let pending = null, pendingTimer = 0;
function requestPage(key) {
  if (key === page && !pending) return;
  pending = key;
  clearTimeout(pendingTimer);
  pendingTimer = setTimeout(() => { const k = pending; pending = null; setPage(k); }, 160);
}

function setPage(key) {
  if (key === page) return;
  viewer?.settle();
  page = key;
  document.body.dataset.section = key;
  for (const a of document.querySelectorAll('[data-nav]')) a.classList.toggle('is-on', a.dataset.nav === key || (a.dataset.nav === 'physics' && /^ch[123]$/.test(key)));
  enterScene(key);
}

function frame(now) {
  requestAnimationFrame(frame);
  const dt = lastFrame ? Math.min(0.1, (now - lastFrame) / 1000) : 0;
  lastFrame = now;
  if (!story.result || !viewer || !SCENES[page]) return;
  const dur = Math.min(story.result.inputs.duration_s, story.loop), d = dt * story.speed;
  story.t += d;
  if (story.t > dur) { story.t = story.from; viewer.setTime(story.t, rowAt(story.result, story.t), -1); }
  else viewer.setTime(story.t, rowAt(story.result, story.t), d);
}

function bindPage() {
  const watch = [...document.querySelectorAll('[data-scene]'), $('investigations'), $('sources')];
  const io = new IntersectionObserver((es) => { for (const e of es) if (e.isIntersecting) requestPage(e.target.dataset.scene || e.target.id); },
    { rootMargin: '-48% 0px -48% 0px' });
  watch.forEach((el) => el && io.observe(el));
  const rv = new IntersectionObserver((es) => { for (const e of es) if (e.isIntersecting) { e.target.classList.add('in'); rv.unobserve(e.target); } }, { threshold: 0.12 });
  document.querySelectorAll('.reveal').forEach((el) => rv.observe(el));
  // stats count up once
  const cu = new IntersectionObserver((es) => {
    for (const e of es) {
      if (!e.isIntersecting) continue;
      cu.unobserve(e.target);
      if (reduced()) continue;
      const el = e.target, end = Number(el.dataset.to), sign = el.dataset.sign, t0 = performance.now();
      const step = (now) => { const k = Math.min(1, (now - t0) / 1600); el.textContent = sign + Math.round(end * (1 - (1 - k) ** 3)); if (k < 1) requestAnimationFrame(step); };
      requestAnimationFrame(step);
    }
  });
  document.querySelectorAll('.stats b').forEach((b) => {
    b.dataset.sign = b.textContent.trim().startsWith('−') ? '−' : '';
    b.dataset.to = b.textContent.replace('−', '').trim();
    cu.observe(b);
  });
  addEventListener('pointermove', (e) => viewer?.setPointer(e.clientX / innerWidth - 0.5, e.clientY / innerHeight - 0.5), { passive: true });
  const nav = $('nav');
  let scrolled = null, ticking = false;
  const onScroll = () => {                     // one update per frame, class touched only on change
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      const s = scrollY > 24;
      if (s !== scrolled) { scrolled = s; nav.classList.toggle('scrolled', s); }
      if (page === 'hero') viewer?.setDolly(scrollY / innerHeight);
    });
  };
  addEventListener('scroll', onScroll, { passive: true }); onScroll();
  addEventListener('resize', () => { if (SCENES[page]) viewer?.setShift(narrow() ? 0 : innerWidth * SCENES[page].shift, innerHeight * (SCENES[page].shiftY || 0)); });
}

async function boot() {
  bindChrome();
  bindPage();
  requestAnimationFrame(frame);
  try { catalog = await api('/api/fire/catalog'); } catch { return; }
  loadEvidence('leo', 'polyethylene', 'refsShort', 8);
  const bar = $('loadBar');
  try {
    const { Viewer } = await import('./viewer/viewer.js');
    viewer = new Viewer($('gl'), $('viewport'), $('labels'));
    window.bfx = { viewer };
    await viewer.init((p) => { bar.style.width = `${Math.round(p * 100)}%`; });
    viewer.setInteractive(true);
    viewer.setDragOnly(true);
    viewer.flyIn('exterior');
    bar.style.width = '100%';
    const current = page; page = 'boot'; setPage(current === 'boot' ? 'hero' : current);
    setTimeout(() => $('loader').classList.add('done'), 400);
  } catch (e) {
    console.error(e);
    bar.parentElement.hidden = true;            // the Cycles poster stays as the backdrop
  }
  document.documentElement.lang = getLang();
}
boot();
