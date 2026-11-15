// The investigation side sheet on the evidence page: one PSI record with its test conditions,
// opened in place from any investigation name. Data: /api/flame/investigations/{accession}.
// The open record is kept in the URL (#...&acc=PSI-25) so it can be linked. textContent only.
import { t } from './i18n.js';
import { $, api } from './common.js';
import { gapRange, KPA_PER_PSI } from './charts.js';

const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
const params = () => new URLSearchParams(location.hash.slice(1));
const FIELD = { o2Pct: 'ev_o2', pressureKPa: 'ev_p', flowMps: 'inv_flow' };
const GRAVITY = { micro: 'gap_g_micro', earth: 'inv_g_earth', 'partial-proxy': 'inv_g_partial' };

function remember(acc) {
  const p = params();
  if (acc) p.set('acc', acc); else p.delete('acc');
  history.replaceState(null, '', `#${p}`);
}

function conditions(e) {
  const box = el('section', undefined, 'ev-env');
  const head = el('h3', e.label);
  // a row nobody has checked against its source is shown and marked, never hidden
  head.append(el('span', t(e.verified ? 'cov_checked' : 'cov_unchecked'), e.verified ? 'badge curated' : 'badge collected'));
  const table = el('table');
  const row = (key, value) => { const tr = el('tr'); tr.append(el('td', t(key)), el('td', value ?? t('cov_nr'))); table.append(tr); };
  row('inv_fuel', [e.fuel, e.geometry].filter(Boolean).join('; '));
  row('ev_o2', e.o2Pct && `${gapRange(e.o2Pct)} %`);
  row('ev_p', e.pressureKPa && `${gapRange(e.pressureKPa)} kPa (${gapRange(e.pressureKPa.map((p) => p / KPA_PER_PSI))} psi)`);
  row('inv_flow', e.flowMps && `${gapRange(e.flowMps.map((v) => v * 100))} cm/s`);
  row('ev_g', t(GRAVITY[e.gravity] || e.gravity));
  if (e.diluent) row('inv_diluent', e.diluent);
  box.append(head, table);
  for (const [field, why] of Object.entries(e.notReported || {})) box.append(el('p', `${t(FIELD[field] || field)}: ${why}`, 'ev-why'));
  box.append(el('p', e.keyFinding));
  return box;
}

export async function openInvestigation(acc) {
  if (!/^PSI-\d+$/.test(acc)) return;
  const dialog = $('invDrawer');
  $('invTitle').textContent = acc;
  $('invIntro').textContent = t('inv_loading');
  $('invBody').replaceChildren();
  if (!dialog.open) dialog.showModal();
  remember(acc);
  let inv;
  try {
    inv = await api(`/api/flame/investigations/${encodeURIComponent(acc)}`);
  } catch {
    $('invIntro').textContent = t('inv_error');
    return;
  }
  if (params().get('acc') !== acc) return;         // closed, or another one opened, while this loaded
  $('invTitle').textContent = inv.acronym;
  $('invIntro').textContent = [inv.accession, t(inv.kind === 'flight' ? 'inv_flight' : 'inv_ground'), ...inv.hardware].join(', ');
  const out = [el('h3', inv.title), el('p', inv.summary || inv.objectives)];
  out.push(...(inv.envelopes.length ? inv.envelopes.map(conditions) : [el('p', t('inv_none'), 'ev-why')]));
  for (const [key, text] of [['inv_objectives', inv.objectives], ['earth_row', inv.earthBenefits]]) {
    if (!text) continue;
    const more = el('details');
    more.append(el('summary', t(key)), el('p', text));
    out.push(more);
  }
  const foot = el('p', `${t('inv_pubs', { n: inv.publications.length })} `);
  if (/^https:\/\//.test(inv.psiUrl)) {
    const a = el('a', t('psi_open'));
    a.href = inv.psiUrl; a.target = '_blank'; a.rel = 'noopener';
    foot.append(a);
  }
  out.push(foot);
  $('invBody').replaceChildren(...out);
}

// an investigation name anywhere on the page: a button that opens the sheet
export function nameButton(accession, text) {
  const b = el('button', text, 'ev-name');
  b.type = 'button';
  b.onclick = () => openInvestigation(accession);
  return b;
}

// the close event can arrive after the next record was opened; only forget the record if the sheet is really shut
const shut = () => { if (!$('invDrawer').open) remember(null); };
// 'close' can be slow to arrive, so the close button, a click outside and Esc are checked directly as well
for (const type of ['close', 'click', 'cancel']) $('invDrawer').addEventListener(type, () => setTimeout(shut, 0));
addEventListener('hashchange', () => { const acc = params().get('acc'); if (acc) openInvestigation(acc); });
if (params().get('acc')) openInvestigation(params().get('acc'));      // a link straight to one record
