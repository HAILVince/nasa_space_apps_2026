// Research dashboards: experiment families from the NASA "Flame in Freefall" challenge brief,
// ranked by topic relevance per mission and fire-safety focus (app/research.py). Every text
// from the API is written with textContent.
import { t } from './i18n.js';

const $ = (id) => document.getElementById(id);
const scenarioSelect = $('scenario'), focusSelect = $('focus');
const status = $('research-status'), results = $('research-results');
let version = 0, loaded = false;

function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}

async function json(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${t('dash_error')} (${r.status})`);
  return r.json();
}

async function loadResearch() {
  const v = ++version;
  status.textContent = t('dash_loading');
  results.replaceChildren();
  $('comparison').replaceChildren();
  const params = new URLSearchParams({ scenario: scenarioSelect.value, focus: focusSelect.value, q: $('research-query').value });
  try {
    const data = await json(`/api/research/dashboard?${params}`);
    if (v !== version) return;
    const limits = $('research-limits');
    limits.replaceChildren(el('h3', t('dash_limits')));
    data.limitations.forEach((x) => limits.append(el('p', x)));
    status.textContent = t('dash_counts', { n: data.total, p: data.counts.prevention, d: data.counts.detection, s: data.counts.suppression });
    if (!data.total) results.append(el('p', t('dash_none')));
    for (const item of data.investigations) {
      const card = el('article', undefined, 'dash-card');
      const label = el('label');
      const check = document.createElement('input'); check.type = 'checkbox'; check.value = item.id;
      label.append(check, document.createTextNode(` ${t('dash_pick')}`));
      const src = el('a', t('dash_source'));
      if (/^https?:\/\//.test(item.source_url)) { src.href = item.source_url; src.target = '_blank'; src.rel = 'noopener'; }
      card.append(el('h3', item.title), el('div', `${t('dash_relevance')} ${item.relevance_score} · ${item.focus}`, 'score'),
        el('p', item.summary), el('p', item.ranking_reasons.join(' ')),
        el('p', `${t('dash_fuel')}: ${item.fuel}. ${t('dash_hw')}: ${item.hardware}`), label, src);
      results.append(card);
    }
  } catch (e) {
    if (v === version) status.textContent = `${e.message}. ${t('dash_retry')}`;
  }
}

async function compare() {
  const ids = Array.from(results.querySelectorAll('input:checked'), (i) => i.value);
  const target = $('comparison');
  target.replaceChildren();
  if (ids.length < 2 || ids.length > 4) { target.textContent = t('dash_pick_2_4'); return; }
  const v = version;
  target.textContent = t('dash_loading');
  try {
    const data = await json(`/api/research/compare?${new URLSearchParams({ ids: ids.join(',') })}`);
    if (v !== version) return;
    const table = el('table');
    table.append(el('caption', t('dash_caption')));
    const head = el('tr');
    t('dash_cols').forEach((c) => head.append(el('th', c)));
    table.append(head);
    for (const i of data.investigations) {
      const row = el('tr');
      [i.title, i.focus, i.fuel, i.hardware, i.gravity, i.oxygen_percent ?? t('unknown'), i.pressure_kpa ?? t('unknown'),
        i.airflow_m_s ?? t('unknown')].forEach((x) => row.append(el('td', String(x))));
      table.append(row);
    }
    target.replaceChildren(table);
  } catch (e) { if (v === version) target.textContent = e.message; }
}

async function init() {
  if (loaded) return;
  loaded = true;
  try {
    const data = await json('/api/research/scenarios');
    for (const s of data.scenarios) {
      const o = el('option', t(`scn_${s.id}`) === `scn_${s.id}` ? s.label : t(`scn_${s.id}`)); o.value = s.id; scenarioSelect.append(o);
    }
    loadResearch();
  } catch (e) { loaded = false; status.textContent = `${e.message}. ${t('dash_retry')}`; }
}

$('research-form').addEventListener('submit', (e) => { e.preventDefault(); loadResearch(); });
$('compare').addEventListener('click', compare);
// load when the section comes near the screen
new IntersectionObserver((entries, io) => {
  if (entries.some((e) => e.isIntersecting)) { io.disconnect(); init(); }
}, { rootMargin: '400px 0px' }).observe($('investigations'));
