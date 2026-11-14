// The evidence page (evidence.html): pick a cabin atmosphere, see which PSI investigations
// ran tests inside it and where nothing did. Data: /api/flame/gapmap (what was tested) and
// /api/flame/context (the habitats). Everything from the API is written with textContent.
import { t } from './i18n.js';
import { $, api, bindChrome } from './common.js';

const KPA_PER_PSI = 6.89476;
const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
const fmt = (x) => String(+x.toFixed(1));
const range = (r) => (fmt(r[0]) === fmt(r[1]) ? fmt(r[0]) : `${fmt(r[0])}–${fmt(r[1])}`);
const overlap = (a, b) => a[0] <= b[1] && b[0] <= a[1];

let map = null, ctx = null;
const fromHash = () => new URLSearchParams(location.hash.slice(1)).get('habitat');
let current = fromHash() || 'moon-base';
// a link to another habitat, or the back button, changes only the hash
addEventListener('hashchange', () => { const id = fromHash(); if (ctx?.habitats.some((h) => h.id === id)) { current = id; render(); } });

async function load() {
  $('evRetry').hidden = true;
  $('evStatus').textContent = t('ev_loading');
  try {
    [map, ctx] = await Promise.all([api('/api/flame/gapmap'), api('/api/flame/context')]);
  } catch {
    $('evStatus').textContent = t('ev_error');
    $('evRetry').hidden = false;
    return;
  }
  $('evStatus').textContent = '';
  if (!ctx.habitats.some((h) => h.id === current)) current = ctx.habitats[0].id;
  $('evReadout').hidden = false;
  render();
}

function render() {
  if (!map) return;
  $('evPick').replaceChildren(...ctx.habitats.map((h) => {
    const b = el('button', h.name, 'chip');
    b.type = 'button';
    b.classList.toggle('is-on', h.id === current);
    b.setAttribute('aria-pressed', String(h.id === current));
    b.onclick = () => { current = h.id; history.replaceState(null, '', `#habitat=${h.id}`); render(); };
    return b;
  }));
  const h = ctx.habitats.find((x) => x.id === current);
  atmosphere(h);
  coverage(h);
}

function atmosphere(h) {
  const title = el('h3', h.name);
  if (h.assumed) { const b = el('span', t('ev_assumed'), 'badge'); b.title = t('ev_assumed_tip'); title.append(b); }
  const facts = el('dl', undefined, 'ev-facts');
  const po2 = [h.o2Pct[0] * h.pressureKPa[0] / 100, h.o2Pct[1] * h.pressureKPa[1] / 100];
  for (const [k, v] of [
    ['ev_o2', `${range(h.o2Pct)} %`],
    ['ev_p', `${range(h.pressureKPa)} kPa (${range(h.pressureKPa.map((p) => p / KPA_PER_PSI))} psi)`],
    ['ev_po2', `${range(po2)} kPa`],
    ['ev_g', `${h.gravityG} g`],
  ]) facts.append(el('dt', t(k)), el('dd', v));
  const note = el('p', h.notes, 'ev-note');
  if (/^https:\/\//.test(h.sourceUrl)) {
    const a = el('a', t('ev_source'));
    a.href = h.sourceUrl; a.target = '_blank'; a.rel = 'noopener';
    note.append(' ', a);
  }
  $('evAtmosphere').replaceChildren(title, facts, note);
}

function coverage(h) {
  // same rule as the API's coverage count: the test envelope and the cabin's ranges overlap on both axes
  const inside = map.rectangles.filter((r) => overlap(h.o2Pct, r.o2Pct) && overlap(h.pressureKPa, r.pressureKPa));
  const byAcc = new Map(ctx.investigations.map((i) => [i.accession, i]));
  const found = [...new Set(inside.map((r) => r.accession))].map((acc) => byAcc.get(acc)).filter(Boolean);
  const solids = found.filter((i) => i.fuelPhase === 'solid').length;
  const out = [el('p', found.length ? t('ev_cov_n', { n: found.length, total: ctx.investigationCount }) : t('ev_cov_0'), 'ev-count')];
  if (found.length) {
    out.push(el('p', solids ? t('ev_solids_n', { n: solids }) : t('ev_solids_0'), solids ? 'ev-solids' : 'ev-solids gap'));
    const list = el('ul', undefined, 'ev-list');
    for (const i of found) {
      const a = el('a', i.acronym);
      if (/^https:\/\//.test(i.psiUrl)) { a.href = i.psiUrl; a.target = '_blank'; a.rel = 'noopener'; }
      const li = el('li');
      li.append(a, el('span', t(`ev_phase_${i.fuelPhase}`)));
      list.append(li);
    }
    out.push(list);
  }
  if (map.unplaced.length) out.push(el('p', t('ev_unplaced', { n: map.unplaced.length }), 'ev-note'));
  $('evCoverage').replaceChildren(...out);
}

$('evRetry').onclick = load;
bindChrome(render);      // a language switch redraws the readout in the new language
load();
