// Shared by the landing page (site.js) and the lab (lab.js): API access, the evidence list,
// the research drawer and the language switch. API text is always written with textContent.
import { t } from './i18n.js';
import { resumeGuide } from './guide.js';

export const $ = (id) => document.getElementById(id);
export const num = (v, d = 1) => (v === null || v === undefined ? '—' : Number(v).toFixed(d));
export const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

export async function api(path, body) {
  const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };

// ---- evidence: curated NASA records + fire-relevant database hits ----------------------------
let records = [];
let lastKey = '';

export async function loadEvidence(environment, material, listId = 'refsShort', max = 8) {
  const key = `${environment}|${material}`;
  if (key !== lastKey) {
    lastKey = key;
    try {
      records = (await api(`/api/fire/evidence?environment=${encodeURIComponent(environment)}&material=${encodeURIComponent(material)}`)).records;
    } catch { records = []; }
  }
  const ul = $(listId);
  if (ul) {
    ul.replaceChildren();
    for (const r of records.slice(0, max)) {
      const li = el('li'); const a = el('a', r.title);
      if (r.url && /^https?:\/\//.test(r.url)) { a.href = r.url; a.target = '_blank'; a.rel = 'noopener'; }
      li.append(a, el('small', [r.source, r.year].filter(Boolean).join(' · ')));
      ul.append(li);
    }
  }
  renderResearch();
}

export function renderResearch() {
  const list = $('researchList');
  if (!list) return;
  list.replaceChildren();
  $('recordView').hidden = true; list.hidden = false;
  if (!records.length) { list.textContent = t('research_none'); return; }
  for (const r of records) {
    const b = el('button', undefined, 'rcard');
    const m = el('div', undefined, 'meta');
    m.append(el('span', r.status || 'record', `badge ${r.status === 'curated' ? 'curated' : 'collected'}`), [r.source, r.year].filter(Boolean).join(' · '));
    b.append(el('h4', r.title), el('p', r.summary || ''), m);
    b.onclick = () => openRecord(r);
    list.append(b);
  }
}

async function openRecord(brief) {
  const view = $('recordView'), list = $('researchList');
  let rec = brief;
  try { rec = await api(`/api/research/${encodeURIComponent(brief.slug)}`); } catch { /* index still building: use the brief */ }
  view.replaceChildren();
  const back = el('button', t('back'), 'link');
  back.onclick = () => { view.hidden = true; list.hidden = false; };
  view.append(back, el('h3', rec.title), el('div', [rec.org, rec.source, rec.year].filter(Boolean).join(' · '), 'meta'), el('p', rec.summary || ''));
  if (rec.details) view.append(el('p', rec.details));
  if (rec.facts?.length) {
    const tb = el('table');
    for (const f of rec.facts.slice(0, 40)) { const tr = el('tr'); tr.append(el('td', f.name), el('td', `${f.value} ${f.unit || ''}`)); tb.append(tr); }
    view.append(el('h3', t('facts'), 'h3'), tb);
  }
  const srcs = rec.sources?.length ? rec.sources : rec.url ? [{ title: rec.title, url: rec.url }] : [];
  if (srcs.length) {
    view.append(el('h3', t('sources'), 'h3'));
    for (const s of srcs) {
      const a = el('a', s.title || s.url); a.style.display = 'block'; a.style.margin = '4px 0';
      if (s.url && /^https?:\/\//.test(s.url)) { a.href = s.url; a.target = '_blank'; a.rel = 'noopener'; }
      view.append(a);
    }
  }
  list.hidden = true; view.hidden = false;
}

// ---- drawers -------------------------------------------------------------------------------------
export function openDrawer(name) {
  const drawers = { research: 'researchDrawer', console: 'consoleDrawer' };
  for (const [k, id] of Object.entries(drawers)) if (k !== name && $(id)?.open) $(id).close();
  const d = $(drawers[name]);
  if (d && !d.open) d.showModal();
  if (name === 'research') renderResearch();
  if (name === 'console') $('chatInput')?.focus();
}

export function bindChrome() {
  for (const b of document.querySelectorAll('[data-tab-link]')) b.addEventListener('click', () => openDrawer(b.dataset.tabLink));
  for (const d of document.querySelectorAll('dialog')) {
    d.querySelector('[data-close]').onclick = () => d.close();
    d.addEventListener('click', (e) => { if (e.target === d) d.close(); });
  }
  resumeGuide();                             // the AI pointed at something on this page from the other one
}
