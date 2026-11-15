// The landing page. Behind the story sits a still of the 3D scene for each chapter (rendered
// from the lab's own renderer by tests/perf/stills.cjs); the section in the middle of the
// screen picks which one is shown, with a cross-fade done by the compositor. No WebGL runs
// here, so scrolling stays smooth on any machine; the live 3D scene is in the lab.
import { getLang } from './i18n.js';
import { $, loadEvidence, bindChrome } from './common.js';
import { bindHomeImpact } from './impact.js';

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

function boot() {
  let relabelImpact = () => {};
  bindChrome(() => relabelImpact());
  relabelImpact = bindHomeImpact();
  bindPage();
  if (page === 'boot') setPage('hero');
  loadEvidence('leo', 'polyethylene', 'refsShort', 8);
  document.documentElement.lang = getLang();
}
boot();
