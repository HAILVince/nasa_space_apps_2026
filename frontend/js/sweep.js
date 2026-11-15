// "Variables: how did tests from the same investigation differ, and how were they the same?"
// One PSI investigation at a time: a row per configuration it ran (GET /api/flame/sweep), each row
// linked back to the CSV lines it was built from. An investigation with no rows shows why, never an
// empty table. The numbers and reasons come from the API; only the labels are fixed text.
import { t } from './i18n.js';
import { api } from './common.js';

const RAW_BASE = 'https://github.com/HAILVince/nasa_space_apps_2026/blob/main/blackfox/db/knowledge/raw_data/psi_combustion/tables/';
const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
const range = (r) => (r ? (r[0] === r[1] ? `${r[0]}` : `${r[0]}–${r[1]}`) : null);

function external(a, href, label) {
  a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer';
  if (label) a.title = a.ariaLabel = label;
  return a;
}

// a value cell: the range, or "not reported"; rows that lack the value are counted in the tooltip
function rangeCell(r, missing) {
  const td = el('td', range(r) ?? t('sw_nr'), r ? 'num' : 'num nr');
  if (missing && r) { td.title = t('sw_nr_rows', { n: missing }); td.textContent += ' *'; }
  return td;
}

function sourceCell(c) {
  const td = el('td', undefined, 'src');
  for (const s of c.sources) {
    const line = el('div');
    line.append(el('span', `${s.table} · `, 'tbl'));
    s.row_ranges.slice(0, 6).forEach(([a, b], i) => {
      const label = t('sw_open_row', { table: s.table, a });
      // row N of the cleaned data is line N + 1 of the CSV (the header is line 1)
      const link = external(el('a', a === b ? t('sw_row', { a }) : t('sw_rows', { a, b })), `${RAW_BASE}${encodeURIComponent(s.table)}?plain=1#L${a + 1}`, label);
      line.append(i ? ', ' : '', link);
    });
    if (s.row_ranges.length > 6) line.append(` … (${s.row_ranges.length})`);
    td.append(line);
  }
  return td;
}

function configRow(c) {
  const tr = el('tr');
  const cfg = el('td', c.config ?? t('sw_cfg_none'), c.config ? 'cfg' : 'cfg nr');
  for (const k of ['test_day', 'matrix']) if (c.kinds?.[k]) cfg.append(el('small', t(`sw_kind_${k}`, { n: c.kinds[k] })));
  // a table that never reports ignition shows "not reported", not "0 ignited"
  const silent = c.ignition_unreported === c.rows;
  const ign = el('td', silent ? t('sw_nr') : `${c.ignited} / ${c.rows}`, silent ? 'num nr' : 'num');
  if (c.ignition_unreported && !silent) ign.append(el('small', t('sw_ign_nr', { n: c.ignition_unreported })));
  tr.append(cfg, rangeCell(c.o2_pct, c.unreported.o2_pct), rangeCell(c.pressure_kpa, c.unreported.pressure_kpa),
    rangeCell(c.flow_mps, c.unreported.flow_mps), el('td', String(c.rows), 'num'), ign, sourceCell(c));
  return tr;
}

// the reason an investigation has no table: label, plus the cleaning step's own detail
function reasonText(g) {
  const base = t(`sw_r_${g.reason_code}`);
  return g.detail_code ? `${base}: ${t(`sw_d_${g.detail_code}`)}` : base;
}

export function renderSweep(box, d, investigations, onPick) {
  box.replaceChildren();
  const head = el('div', undefined, 'sw-head');
  const title = el('div'); title.append(el('h2', t('sw_title')), el('p', t('sw_lede'), 'lede'));
  const pick = el('label', undefined, 'sw-pick'); pick.append(el('span', t('sw_pick'), 'eyebrow'));
  const sel = el('select'); sel.id = 'swPick';
  const have = new Set(d.with_rows);
  for (const i of investigations) {
    const o = el('option', `${i.accession} · ${i.acronym}${have.has(i.accession) ? '' : ` — ${t('sw_no_rows')}`}`);
    o.value = i.accession; if (i.accession === d.accession) o.selected = true; sel.append(o);
  }
  sel.onchange = () => onPick?.(sel.value);
  pick.append(sel); head.append(title, pick); box.append(head);

  const meta = el('p', undefined, 'sw-meta');
  meta.append(external(el('a', `${d.accession} · ${d.acronym}`), d.psi_url, `${t('psi_open')}: ${d.accession}`));
  meta.append(` — ${t('sw_summary', { rows: d.rows, n: d.configurations.length, tables: d.tables.length })}`);
  box.append(meta);

  if (d.gap) {
    const g = el('p', undefined, 'sw-gap');
    g.append(el('b', t('sw_gap_h', { acc: d.accession })), ` ${reasonText(d.gap)}`);
    if (d.gap.raw_table) { g.append(' · '); g.append(external(el('a', d.gap.raw_table), RAW_BASE + encodeURIComponent(d.gap.raw_table), `${t('sw_raw')}: ${d.gap.raw_table}`)); }
    box.append(g);
  } else {
    const wrap = el('div', undefined, 'sw-scroll'), table = el('table');
    const tr = el('tr');
    for (const k of ['cfg', 'o2', 'p', 'flow', 'rows', 'ign', 'src']) tr.append(el('th', t(`sw_c_${k}`)));
    const thead = el('thead'); thead.append(tr);
    const tbody = el('tbody'); for (const c of d.configurations) tbody.append(configRow(c));
    table.append(thead, tbody); wrap.append(table); box.append(wrap);
    box.append(el('p', t('sw_note'), 'sw-note'));
  }

  const det = el('details', undefined, 'sw-gaps');
  det.append(el('summary', t('sw_gaps_h', { n: d.without_rows.length })));
  const ul = el('ul');
  for (const g of d.without_rows) {
    const li = el('li'); li.append(el('b', `${g.accession} · ${g.acronym}`), ` — ${reasonText(g)}`);
    ul.append(li);
  }
  det.append(ul); box.append(det);
}

async function boot() {
  const box = document.getElementById('sweep');
  if (!box) return;
  let acc = 'PSI-25', data = null, invs = [];
  const draw = () => data && renderSweep(box, data, invs, load);
  async function load(a) {
    try { data = await api(`/api/flame/sweep?accession=${encodeURIComponent(a)}`); acc = a; draw(); }
    catch { box.replaceChildren(el('p', t('sw_error'), 'sw-gap')); }
  }
  invs = (await api('/api/flame/context').catch(() => ({ investigations: [] }))).investigations;
  await load(acc);
  // the language buttons are bound by spread.js; re-draw after its handler has switched the language
}
boot();
