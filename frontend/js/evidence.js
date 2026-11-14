// The evidence page (evidence.html): pick a cabin atmosphere, see which PSI investigations
// ran tests inside it and where nothing did, on the same gap map the lab draws (charts.js).
// Python (flame/gapmap.py) decides what is on the map and counts the coverage; nothing is
// recomputed here. Everything from the API is written with textContent.
import { t } from './i18n.js';
import { $, api, bindChrome } from './common.js';
import { gapMap, gapRange, KPA_PER_PSI, PHASE_COLOR, HABITAT_COLOR } from './charts.js';
import { showRanking } from './ranking.js';

const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
const psi = (r) => gapRange(r.map((p) => p / KPA_PER_PSI));
const atm = (o, p) => `${gapRange(o)} % O₂, ${gapRange(p)} kPa (${psi(p)} psi)`;

let map = null, ctx = null;
const fromHash = () => new URLSearchParams(location.hash.slice(1)).get('habitat');
let current = fromHash() || 'moon-base';
// a link to another habitat, or the back button, changes only the hash
addEventListener('hashchange', () => { const id = fromHash(); if (ctx?.habitats.some((h) => h.id === id)) { current = id; render(); } });

async function load() {
  $('evRetry').hidden = true;
  $('evStatus').textContent = t('ev_loading');
  try {
    [map, ctx] = await Promise.all([api(`/api/flame/gapmap${$('evMicro').checked ? '?micro_only=true' : ''}`),
                                    ctx || api('/api/flame/context')]);
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
  $('evPick').replaceChildren(...ctx.habitats.map((h, i) => {
    const b = el('button', undefined, 'chip');
    const n = el('span', String(i + 1), 'gap-badge');      // the same number and colour as on the map
    n.style.color = HABITAT_COLOR[i % HABITAT_COLOR.length];
    b.append(n, h.name);
    b.type = 'button';
    b.classList.toggle('is-on', h.id === current);
    b.setAttribute('aria-pressed', String(h.id === current));
    b.onclick = () => { current = h.id; history.replaceState(null, '', `#habitat=${h.id}`); render(); };
    return b;
  }));
  const h = ctx.habitats.find((x) => x.id === current);
  atmosphere(h);
  coverage(h);
  chart();
  showRanking(h.id, new Map(ctx.investigations.map((i) => [i.accession, i.psiUrl])));
}

function atmosphere(h) {
  const title = el('h3', h.name);
  if (h.assumed) { const b = el('span', t('ev_assumed'), 'badge'); b.title = t('ev_assumed_tip'); title.append(b); }
  const facts = el('dl', undefined, 'ev-facts');
  const po2 = [h.o2Pct[0] * h.pressureKPa[0] / 100, h.o2Pct[1] * h.pressureKPa[1] / 100];
  for (const [k, v] of [
    ['ev_o2', `${gapRange(h.o2Pct)} %`],
    ['ev_p', `${gapRange(h.pressureKPa)} kPa (${psi(h.pressureKPa)} psi)`],
    ['ev_po2', `${gapRange(po2)} kPa`],
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
  const byAcc = new Map(ctx.investigations.map((i) => [i.accession, i]));
  // ?. so an older server that lacks a field shows a count without names instead of a blank page
  const found = (map.coveredBy?.[h.id] || []).map((acc) => byAcc.get(acc)).filter(Boolean);
  const n = map.coverage?.[h.id] ?? 0, solids = map.coverageByPhase?.[h.id]?.solid ?? 0;
  const out = [el('p', n ? t('ev_cov_n', { n, total: ctx.investigationCount }) : t('ev_cov_0'), 'ev-count')];
  if (n) {
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

function chart() {
  const svg = $('evMap');
  svg.setAttribute('aria-label', t('gap_aria'));
  const { offscale } = gapMap(svg, map, {
    x: t('gap_x'), psi: t('gap_psi'), y: t('gap_y'),
    iso: (c) => { const k = `gap_iso_${Math.round(c.po2KPa)}`; const s = t(k); return s === k ? c.label : s; },
    envTitle: (r) => `${r.acronym} (${r.accession})\n${r.fuel}\n${atm(r.o2Pct, r.pressureKPa)}\n${t(`gap_g_${r.gravity}`)}`,
    habTitle: (hb) => `${hb.name}\n${atm(hb.o2Pct, hb.pressureKPa)}`,
  });
  for (const n of svg.querySelectorAll('[data-hab]')) n.classList.toggle('is-off', n.dataset.hab !== current);

  const item = (mark, text) => { const s = el('span'); s.append(mark, text); return s; };
  const legend = ['solid', 'liquid', 'gas', 'aerosol'].map((ph) => {
    const sw = el('i', undefined, 'sw'); sw.style.background = `${PHASE_COLOR[ph]}33`; sw.style.borderColor = PHASE_COLOR[ph];
    return item(sw, t(`gap_lg_${ph}`));
  });
  legend.push(item(el('i', undefined, 'sw dash'), t('gap_lg_hab')), item(el('span', '✕', 'x'), t('gap_lg_inc')));
  $('evLegend').replaceChildren(...legend);
  $('evClip').textContent = offscale.length
    ? t('gap_clip', { list: [...new Set(offscale.map((r) => `${r.acronym} (${gapRange(r.pressureKPa)} kPa)`))].join(', ') }) : '';
  const micro = map.rectangles.filter((r) => r.gravity === 'micro').length;
  // when every drawn box is already a microgravity test the switch would change nothing, so it is not offered
  $('evMicro').parentElement.hidden = !$('evMicro').checked && micro === map.rectangles.length;
  $('evCaveats').replaceChildren(el('li', t('gap_cav_g', { m: micro, k: map.rectangles.length })), el('li', t('gap_cav_gap')));
}

$('evRetry').onclick = load;
$('evMicro').onchange = load;      // the server leaves out the ground tests and recounts
bindChrome(render);                // a language switch redraws everything in the new language
load();
