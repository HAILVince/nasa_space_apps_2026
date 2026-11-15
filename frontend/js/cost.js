// Home page, For Businesses: what one cabin fire costs. Every price comes from flame/data/finance.json
// (GET /api/flame/finance: NASA's price list, NASA OIG audits, insurers' reports) and the event sizes from
// real fires (GET /api/flame/events: Mir 1997, ISS 2006). Only the replaced-hardware mass is an assumption,
// and the page says so. Text is written with textContent; numbers are formatted here.
import { t, getLang } from './i18n.js';
import { $, api } from './common.js';

const TILES = [
  ['iss_crew_time_price', 'cost_t_crew'],
  ['cargo_cost_per_kg_crs1', 'cost_t_cargo'],
  ['iss_cost_per_day', 'cost_t_day'],
  ['ins_capacity_2025', 'cost_t_ins'],
];
// replaced hardware is not given by any source: a starting value the visitor can change
const PRESETS = {
  'iss-2006-elektron': { hours: (e) => e.emergencyH, kg: 0 },
  'mir-1997-candle-fire': { hours: (e) => e.masksH, kg: 50 },
};

const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };

function usd(v) {
  return new Intl.NumberFormat(getLang() === 'hu' ? 'hu-HU' : 'en-US',
    v >= 1e5 ? { style: 'currency', currency: 'USD', notation: 'compact', maximumSignificantDigits: 3 }
      : { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v);
}

function source(item, fin) {
  if (item.kind === 'derived' && fin[item.derivedFrom?.[0]]) item = fin[item.derivedFrom[0]];   // cite the audit, not the sum
  const a = el('a', `${item.source.split(',')[0]} · ${item.asOf.slice(0, 4)}`);
  a.href = item.url; a.target = '_blank'; a.rel = 'noopener';
  return a;
}

export function bindFireCost() {
  const form = $('costForm');
  if (!form) return () => {};
  let fin = null, events = [];

  const fillEvents = () => {
    const sel = $('costEvent'), v = sel.value;
    sel.replaceChildren(...events.filter((e) => PRESETS[e.id]).map((e) => new Option(t(`cost_ev_${e.id}`), e.id)),
      new Option(t('cost_ev_custom'), 'custom'));
    sel.value = v || 'mir-1997-candle-fire';
  };

  const preset = () => {
    const e = events.find((x) => x.id === $('costEvent').value);
    if (!e) return;
    $('costCrew').value = e.crew;
    $('costHours').value = PRESETS[e.id].hours(e);
    $('costKg').value = PRESETS[e.id].kg;
  };

  const render = () => {
    if (!fin) return;
    const tiles = $('costTiles');
    tiles.replaceChildren(...TILES.filter(([id]) => fin[id]).map(([id, key]) => {
      const it = fin[id], d = el('div');
      const unit = { 'USD/h': '/h', 'USD/kg': '/kg', 'USD/day': `/${t('cost_day')}` }[it.unit] || '';
      d.append(el('b', usd(it.value) + unit), el('span', t(key)), source(it, fin));
      return d;
    }));

    const crew = Math.max(0, Number($('costCrew').value) || 0);
    const hours = Math.max(0, Number($('costHours').value) || 0);
    const kg = Math.max(0, Number($('costKg').value) || 0);
    const crewCost = crew * hours * fin.iss_crew_time_price.value;
    const cargoCost = kg * fin.cargo_cost_per_kg_crs1.value;
    const total = crewCost + cargoCost;
    const issHour = fin.iss_cost_per_year.value / (365 * 24);

    const table = document.createElement('table');
    const row = (label, value, note, cls) => {
      const tr = table.insertRow(); if (cls) tr.className = cls;
      tr.insertCell().textContent = label;
      tr.insertCell().textContent = value;
      tr.insertCell().textContent = note;
    };
    row(t('cost_r_crew'), usd(crewCost), t('cost_r_crew_n', { crew, hours: hours.toLocaleString(getLang() === 'hu' ? 'hu-HU' : 'en-US'), rate: usd(fin.iss_crew_time_price.value) }));
    row(t('cost_r_cargo'), usd(cargoCost), t('cost_r_cargo_n', { kg, rate: usd(fin.cargo_cost_per_kg_crs1.value) }));
    const n1 = (x) => x.toLocaleString(getLang() === 'hu' ? 'hu-HU' : 'en-US', { maximumFractionDigits: 1 });
    row(t('cost_r_total'), usd(total), t('cost_r_total_n', { h: n1(total / issHour) }), 'total');
    $('costOut').replaceChildren(table);

    const e = events.find((x) => x.id === $('costEvent').value);
    $('costNote').textContent = [
      t('cost_save', { total: usd(total) }),
      e ? t('cost_from', { what: t(`cost_ev_${e.id}`) }) : '',
      kg > 0 ? t('cost_kg_assumed') : '',
      t('cost_price_note'),
    ].filter(Boolean).join(' ');
  };

  form.addEventListener('input', (ev) => {
    if (ev.target.id === 'costEvent') preset();
    else if (['costCrew', 'costHours', 'costKg'].includes(ev.target.id)) $('costEvent').value = 'custom';
    render();
  });
  form.addEventListener('submit', (ev) => ev.preventDefault());

  const io = new IntersectionObserver(async (es) => {
    if (!es.some((x) => x.isIntersecting)) return;
    io.disconnect();
    try {
      const [f, ev] = await Promise.all([api('/api/flame/finance'), api('/api/flame/events')]);
      fin = Object.fromEntries(f.items.map((i) => [i.id, i]));
      events = ev.events;
    } catch (err) { console.error(err); $('costNote').textContent = t('start_failed'); return; }
    fillEvents(); preset(); render();
  }, { rootMargin: '200px 0px' });
  io.observe(form);
  return () => { if (fin) { fillEvents(); render(); } };      // on a language change
}
