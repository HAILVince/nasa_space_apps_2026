// The landing page. Behind the story sits a still of the 3D scene for each chapter (rendered
// from the lab's own renderer by tests/perf/stills.cjs); the section in the middle of the
// screen picks which one is shown, with a cross-fade done by the compositor. No WebGL runs
// here, so scrolling stays smooth on any machine; the live 3D scene is in the lab.
import { getLang } from './i18n.js';
import { $, loadEvidence, bindChrome } from './common.js';
import { bindHomeImpact } from './impact.js';

$('heroAsk')?.addEventListener('click', () => { location.href = './lab.html?ask=1'; });

let page = 'boot';
const ORDER = ['hero', 'ch1', 'ch2', 'ch3', 'ch4'];
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

// a backdrop's image starts loading when the chapter before it is shown
function load(key) {
  const layer = document.querySelector(`.bg[data-bg="${key}"]`);
  if (!layer || layer.dataset.loaded) return;
  layer.dataset.loaded = '1';
  for (const el of layer.querySelectorAll('[data-srcset]')) { el.srcset = el.dataset.srcset; el.removeAttribute('data-srcset'); }
}

// ---- hero film: a Blender loop over the hero (blender/build_cinematic.py), above js/scrub.js's video
const film = {
  el: null,
  want: false,
  playing: false,
  // wide layout (phones keep their portrait still), motion allowed, no data saver / slow link
  allowed() {
    const c = navigator.connection;
    return matchMedia('(min-width: 901px) and (min-aspect-ratio: 3/4)').matches && !reduced()
      && !(c && (c.saveData || /(^|slow-)2g|3g/.test(c.effectiveType || '')));
  },
  start() {
    const backdrop = document.querySelector('.backdrop');
    if (!backdrop || !this.allowed()) return;
    // created here, like js/scrub.js's video: nothing is in the page (or downloaded) when it is not used
    const v = this.el = document.createElement('video');
    v.className = 'film'; v.muted = true; v.loop = true; v.playsInline = true; v.preload = 'auto';
    for (const [k, val] of [['aria-hidden', 'true'], ['muted', ''], ['playsinline', ''], ['tabindex', '-1'], ['disablepictureinpicture', '']]) v.setAttribute(k, val);
    for (const [src, type] of [['./assets/video/hero-loop.webm', 'video/webm; codecs="vp9"'], ['./assets/video/hero-loop.mp4', 'video/mp4; codecs="avc1.640028"']]) {
      const s = document.createElement('source'); s.src = src; s.type = type; v.append(s);
    }
    backdrop.append(v);
    v.addEventListener('playing', () => { this.playing = true; if (this.want) v.classList.add('is-on'); });
    v.load();
    document.addEventListener('visibilitychange', () => this.sync());
    this.sync();
  },
  sync() {
    const v = this.el;
    if (!v) return;
    const on = !document.hidden && (page === 'hero' || page === 'boot');
    if (on === this.want) return;
    this.want = on;
    if (on) {
      v.hidden = false;
      if (this.playing) v.classList.add('is-on');
      v.play().catch(() => {});
    } else {
      // below the hero: paused and out of the layer tree at once, the scroll video underneath takes over
      // (fading a playing or paused video out over the scrubbed one cost long frames on a software GPU)
      v.classList.remove('is-on'); v.pause(); v.hidden = true;
    }
  },
};

let pending = null, pendingTimer = 0;
function requestPage(key) {
  if (key === page && !pending) return;
  pending = key;
  clearTimeout(pendingTimer);
  pendingTimer = setTimeout(() => { const k = pending; pending = null; setPage(k); }, 80);
}

function setPage(key) {
  if (key === page) return;
  page = key;
  document.body.dataset.section = key;
  for (const a of document.querySelectorAll('[data-nav]')) a.classList.toggle('is-on', a.dataset.nav === key || (a.dataset.nav === 'physics' && /^ch[123]$/.test(key)));
  const i = ORDER.indexOf(key);
  if (i >= 0) { load(key); load(ORDER[i + 1]); }
  film.sync();
}

function bindPage() {
  const watch = [...document.querySelectorAll('[data-scene]'), $('investigations'), $('business'), $('sources')];
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
  const nav = $('nav');
  let scrolled = null, ticking = false;
  const onScroll = () => {                     // one update per frame, class touched only on change
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      const s = scrollY > 24;
      if (s !== scrolled) { scrolled = s; nav.classList.toggle('scrolled', s); }
    });
  };
  addEventListener('scroll', onScroll, { passive: true }); onScroll();
}

// a #section link (the nav, or arriving from another page): the experiment dashboard fills in above the later
// sections after the jump and grows the page, which left the view somewhere else. Keep the target in place while
// the layout settles; any scroll input of the visitor's own ends it.
function keepAnchor(id, now = false) {
  const el = id && document.getElementById(id);
  if (!el) return;
  let first = !now, timer = 0;
  const ro = new ResizeObserver(() => {
    if (first) { first = false; return; }      // fires once on observe: after a click, let its smooth jump run
    el.scrollIntoView({ behavior: 'instant', block: 'start' });
  });
  const stop = () => { ro.disconnect(); clearTimeout(timer); for (const e of INPUT) removeEventListener(e, stop); };
  ro.observe(document.body);
  timer = setTimeout(stop, 5000);
  for (const e of INPUT) addEventListener(e, stop, { passive: true });
}
const INPUT = ['wheel', 'touchstart', 'keydown', 'pointerdown'];

function boot() {
  let relabelImpact = () => {};
  bindChrome(() => relabelImpact());
  relabelImpact = bindHomeImpact();
  bindPage();
  keepAnchor(location.hash.slice(1), true);              // arrived with #section: the page may have grown already
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href*="#"]');
    if (a && a.pathname === location.pathname) setTimeout(() => keepAnchor(a.hash.slice(1)));   // after its own pointerdown
  });
  if (page === 'boot') setPage('hero');
  loadEvidence('leo', 'polyethylene', 'refsShort', 8);
  document.documentElement.lang = getLang();
  // the film never competes with first paint: it is fetched once the page and its stills are in
  const later = () => (window.requestIdleCallback ? requestIdleCallback(() => film.start(), { timeout: 2000 }) : setTimeout(() => film.start(), 300));
  if (document.readyState === 'complete') later(); else addEventListener('load', later, { once: true });
}
boot();
