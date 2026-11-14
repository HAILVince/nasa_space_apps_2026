import { t, label, setLang, getLang } from './i18n.js';
import { flammabilityMap, timeSeries } from './charts.js';

const $ = (id) => document.getElementById(id);
const S = {
  environment: 'leo', location: 'avionics_rack', material: null, pressure_kpa: null, o2_pct: null, temp_c: null,
  vent_cm_s: 12, auto_vent_shutdown: true, suppression: 'co2', response_s: 60,
};
let catalog = null, result = null, viewer = null, evidenceRecs = [];
let simT = 0, playing = true, speed = 8, lastFrame = 0, reqId = 0;
const SPEEDS = [1, 4, 8, 16, 32];
const ORBS = {
  leo: 'radial-gradient(circle at 35% 35%,#8fd0ff,#1d5fa8 55%,#0a2142)',
  lunar_orbit: 'radial-gradient(circle at 35% 35%,#e9e9e6,#8d8c88 55%,#2f2f2d)',
  moon: 'linear-gradient(180deg,#000 0 50%,#8b8985 50%)',
  mars: 'radial-gradient(circle at 35% 35%,#f0a070,#b3532a 55%,#4a1d0c)',
  earth: 'radial-gradient(circle at 35% 35%,#d9dde0,#6c757c 60%,#2b3034)',
};
const EV_COLOR = { ignition: '#f08a3c', alarm: '#e8c547', vent_off: '#5ad1e6', co2: '#5ad1e6', water_mist: '#5ad1e6', crew_on_scene: '#8e9aa4', extinguished: '#59d38c', self_extinguished: '#59d38c', co_smac: '#a58cff' };

const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const num = (v, d = 1) => (v === null || v === undefined ? '—' : Number(v).toFixed(d));
const fill = (input) => input.style.setProperty('--fill', `${(input.value - input.min) / (input.max - input.min) * 100}%`);

// ---------------------------------------------------------------- data
async function api(path, body) {
  const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function scenarioBody() {
  return { ...S };
}

let debounce;
function rerun(delay = 140) {
  clearTimeout(debounce);
  debounce = setTimeout(runSimulation, delay);
}

async function runSimulation() {
  const id = ++reqId;
  saveHash();
  let r;
  try { r = await api('/api/fire/simulate', scenarioBody()); } catch (e) { console.error(e); return; }
  if (id !== reqId) return;
  result = r;
  viewer?.setScenario(result, catalog);
  simT = 0; playing = true; viewer?.setTime(0, rowAt(0), -1);
  renderResults();
  loadEvidence();
}

// ---------------------------------------------------------------- scenario panel
function buildScenario() {
  const grid = $('envGrid');
  grid.replaceChildren();
  for (const [key, env] of Object.entries(catalog.environments)) {
    const b = document.createElement('button');
    b.className = 'env'; b.setAttribute('role', 'radio'); b.dataset.v = key;
    const orb = document.createElement('span'); orb.className = 'orb'; orb.style.background = ORBS[key];
    const name = document.createElement('b'); name.textContent = label(env.label);
    const g = document.createElement('small');
    g.textContent = env.g_fraction < 0.01 ? `≈ 10⁻⁶ g · ${t('gravity')}` : `${env.g_fraction.toFixed(3)} g · ${env.g_m_s2.toFixed(2)} m/s²`;
    b.append(orb, name, g);
    b.onclick = () => selectEnvironment(key);
    grid.append(b);
  }
  const chips = $('atmPresets');
  chips.replaceChildren();
  for (const pr of ATM_PRESETS) {
    const c = document.createElement('button');
    c.className = 'chip'; c.textContent = pr.label; c.title = pr.title;
    c.onclick = () => { S.pressure_kpa = pr.p; S.o2_pct = pr.o; syncInputs(); rerun(); };
    chips.append(c);
  }
  const locSel = $('location');
  locSel.replaceChildren(...Object.entries(catalog.locations).map(([k, l]) => new Option(label(l.label), k)));
  const matSel = $('material');
  matSel.replaceChildren(...Object.entries(catalog.materials).map(([k, m]) => new Option(label(m.label), k)));
}

const ATM_PRESETS = [
  { label: 'ISS 101.4 / 21', p: 101.4, o: 21, title: 'ISS, Shuttle, Commercial Crew (14.7 psia)' },
  { label: 'Gateway 70.3 / 26.5', p: 70.3, o: 26.5, title: 'Gateway / lunar lander (10.2 psia)' },
  { label: 'EA 56.5 / 34', p: 56.5, o: 34, title: 'Moon-to-Mars exploration atmosphere (8.2 psia)' },
  { label: 'Saffire V 70.7 / 26.2', p: 70.7, o: 26.2, title: 'Saffire V test conditions in Cygnus' },
];

function selectEnvironment(key, keepAtm = false) {
  S.environment = key;
  const d = catalog.environments[key].defaults;
  if (!keepAtm) { S.pressure_kpa = d.pressure_kpa; S.o2_pct = d.o2_pct; S.temp_c = d.temp_c; }
  syncInputs();
  viewer?.setEnvironment(key, catalog.environments[key].g_fraction);
  rerun(0);
}

function syncInputs() {
  const env = catalog.environments[S.environment];
  for (const b of $('envGrid').children) b.setAttribute('aria-checked', String(b.dataset.v === S.environment));
  const facts = $('envFacts'); facts.replaceChildren();
  for (const f of env.facts) {
    const dt = document.createElement('dt'); dt.textContent = f.name.split(' / ')[getLang() === 'hu' ? 0 : 1] || f.name;
    const unit = f.unit.includes(' / ') ? f.unit.split(' / ')[getLang() === 'hu' ? 0 : 1] : f.unit;
    const dd = document.createElement('dd'); dd.textContent = `${typeof f.value === 'number' ? +f.value.toPrecision(4) : f.value} ${unit}`;
    facts.append(dt, dd);
  }
  const p = S.pressure_kpa ?? env.defaults.pressure_kpa, o = S.o2_pct ?? env.defaults.o2_pct, tc = S.temp_c ?? env.defaults.temp_c;
  $('pressure').value = p; $('o2').value = o; $('temp').value = tc; $('vent').value = S.vent_cm_s; $('respTime').value = S.response_s;
  $('pressureOut').innerHTML = ''; $('pressureOut').append(`${num(p, 1)} kPa`, Object.assign(document.createElement('small'), { textContent: `${num(p / 6.894757, 2)} psia` }));
  $('o2Out').textContent = `${num(o, 1)} %`;
  $('tempOut').textContent = `${num(tc, 1)} °C`;
  $('ventOut').textContent = `${num(S.vent_cm_s, 1)} cm/s`;
  $('respOut').textContent = `${S.response_s} s`;
  $('ppo2').textContent = `${num(p * o / 100, 1)} kPa`;
  for (const id of ['pressure', 'o2', 'temp', 'vent', 'respTime']) fill($(id));
  const [lo, hi] = catalog.references.ventilation_nominal_cm_s;
  Object.assign($('ventBand').style, { left: `${lo / 40 * 100}%`, width: `${(hi - lo) / 40 * 100}%` });
  $('location').value = S.location;
  $('material').value = S.material || catalog.locations[S.location].default_material;
  for (const b of $('suppression').children) b.setAttribute('aria-checked', String(b.dataset.v === S.suppression));
  $('autoVent').checked = S.auto_vent_shutdown;
  for (const c of $('atmPresets').children) {
    const pr = ATM_PRESETS.find((x) => x.label === c.textContent);
    c.classList.toggle('is-on', pr && Math.abs(pr.p - p) < 0.05 && Math.abs(pr.o - o) < 0.05);
  }
  materialHint();
}

function materialHint() {
  const m = catalog.materials[$('material').value];
  if (!m) return;
  const pts = m.moc_points;
  const near = pts.reduce((a, b) => (Math.abs(b.pressure_kpa - 101) < Math.abs(a.pressure_kpa - 101) ? b : a));
  $('materialHint').textContent = t('material_hint', {
    form: t(`form_${m.form}`), moc: `${near.moc_pct}%`, p: `${near.pressure_kpa} kPa`,
    dhc: m.heat_of_combustion_mj_kg, tox: m.toxic_products.join(', '),
  });
}

function bindInputs() {
  const on = (id, key, conv = Number) => {
    $(id).addEventListener('input', (e) => { S[key] = conv(e.target.value); syncInputs(); rerun(); });
  };
  on('pressure', 'pressure_kpa'); on('o2', 'o2_pct'); on('temp', 'temp_c'); on('vent', 'vent_cm_s'); on('respTime', 'response_s');
  $('location').onchange = (e) => selectLocation(e.target.value);
  $('material').onchange = (e) => { S.material = e.target.value; syncInputs(); rerun(0); };
  $('autoVent').onchange = (e) => { S.auto_vent_shutdown = e.target.checked; rerun(0); };
  for (const b of $('suppression').children) b.onclick = () => { S.suppression = b.dataset.v; syncInputs(); rerun(0); };
  $('resetAtm').onclick = () => selectEnvironment(S.environment);
  for (const b of $('viewSeg').children) b.onclick = () => setView(b.dataset.v);
  for (const b of $('modeSeg').children) b.onclick = () => setMode(b.dataset.v);
  $('play').onclick = () => { playing = !playing; if (result && simT >= result.inputs.duration_s) simT = 0; };
  $('restart').onclick = () => { simT = 0; playing = true; viewer?.setTime(0, rowAt(0), -1); };
  $('speed').onclick = () => { speed = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length]; $('speed').textContent = `×${speed}`; };
  $('time').addEventListener('input', (e) => { const nt = Number(e.target.value); viewer?.setTime(nt, rowAt(nt), nt < simT ? -1 : nt - simT); simT = nt; playing = false; });
  for (const b of document.querySelectorAll('[data-lang]')) b.onclick = () => { setLang(b.dataset.lang); relabel(); };
  for (const b of document.querySelectorAll('.tab')) b.onclick = () => openTab(b.dataset.tab);
  for (const b of document.querySelectorAll('[data-tab-link]')) b.onclick = () => openTab(b.dataset.tabLink);
  for (const d of document.querySelectorAll('dialog')) {
    d.querySelector('[data-close]').onclick = () => d.close();
    d.addEventListener('close', () => openTab('sim', true));
    d.addEventListener('click', (e) => { if (e.target === d) d.close(); });
  }
  $('chatForm').onsubmit = sendChat;
  $('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); $('chatForm').requestSubmit(); }
  });
  $('tourBtn').onclick = tour;
}

function selectLocation(key) {
  S.location = key;
  S.material = null;              // each place has its typical material; the user can change it
  syncInputs();
  rerun(0);
  if (viewer && viewer.view !== 'exterior') setTimeout(() => setView('fire'), 200);
}

function setView(v) {
  for (const b of $('viewSeg').children) b.setAttribute('aria-checked', String(b.dataset.v === v));
  viewer?.setView(v);
}

function setMode(m) {
  for (const b of $('modeSeg').children) b.setAttribute('aria-checked', String(b.dataset.v === m));
  viewer?.setMode(m);
  const lg = $('legend');
  lg.hidden = m !== 'thermal' && m !== 'airflow';
  lg.replaceChildren();
  if (m === 'thermal') {
    lg.append(t('legend_thermal'));
    const ramp = document.createElement('div'); ramp.className = 'ramp';
    ramp.style.background = 'linear-gradient(90deg,#000004,#420a68,#932667,#dd513a,#fca50a,#fcffa4)';
    const ends = document.createElement('div'); ends.className = 'ends';
    ends.innerHTML = '<span>+0 K</span><span>+150 K</span><span>+300 K</span>';
    lg.append(ramp, ends);
  } else if (m === 'airflow') lg.append(t('legend_air'));
}

// ---------------------------------------------------------------- results
function rowAt(time) {
  if (!result) return null;
  const s = result.series;
  const dt = s.length > 1 ? s[1].t - s[0].t : 2;
  const i = Math.min(s.length - 2, Math.max(0, Math.floor(time / dt)));
  const a = s[i], b = s[i + 1], f = Math.min(1, Math.max(0, (time - a.t) / dt));
  const out = {};
  for (const k of Object.keys(a)) out[k] = typeof a[k] === 'number' ? a[k] + (b[k] - a[k]) * f : a[k];
  return out;
}

function renderResults() {
  const r = result, f = r.flammability, fl = r.flame, tl = r.timeline, pk = r.peaks;
  const lvl = r.verdict.level;
  const colors = { low: 'var(--low)', elevated: 'var(--elevated)', high: 'var(--high)', critical: 'var(--critical)' };
  const bgs = { low: '#10201a', elevated: '#221f10', high: '#26180f', critical: '#2a1213' };
  $('verdict').style.setProperty('--vc', colors[lvl]);
  $('verdict').style.setProperty('--vbg', bgs[lvl]);
  $('vLevel').textContent = t(`lv_${lvl}`);
  $('vSub').textContent = `${label(catalog.materials[r.inputs.material].label)} · ${label(catalog.locations[r.inputs.location].label).split(' (')[0]}`;
  const det = tl.alarm_s !== null ? t('v_det', { t: `${num(tl.alarm_s, 0)} s`, how: t(tl.events.find((e) => e.key === 'alarm')?.detail === 'crew' ? 'how_crew' : 'how_detector') }) : t('v_nodet');
  $('vText').textContent = f.flammable
    ? t('v_burn', { margin: num(f.margin_pct, 1), spread: `${num(fl.spread_cm_s, 2)} cm/s`, hrr: `${num(pk.hrr_kw, 2)} kW`, det })
    : t('v_low', { margin: num(-f.margin_pct, 1) });
  const smac = catalog.references.co_smac_1h_ppm;
  const metrics = [
    ['m_moc1g', `${num(f.moc_1g, 1)}<small>%</small>`],
    ['m_moceff', `${num(f.moc_eff, 1)}<small>%</small>`],
    ['m_margin', `${f.margin_pct > 0 ? '+' : ''}${num(f.margin_pct, 1)}<small>%</small>`, f.margin_pct > 3 ? 'bad' : f.margin_pct > 0 ? 'warn' : 'good'],
    ['m_spread', `${num(fl.spread_cm_s, 2)}<small>cm/s</small>`],
    ['m_tflame', `${num(fl.temperature_k, 0)}<small>K</small>`],
    ['m_hrr', `${num(pk.hrr_kw, pk.hrr_kw < 1 ? 2 : 1)}<small>kW</small>`, pk.hrr_kw > 5 ? 'bad' : ''],
    ['m_alarm', tl.alarm_s === null ? t('none') : `${num(tl.alarm_s, 0)}<small>s</small>`, tl.alarm_s === null && f.flammable ? 'bad' : ''],
    ['m_co', `${num(pk.co_ppm, 1)}<small>ppm</small>`, pk.co_ppm >= smac ? 'bad' : pk.co_ppm > smac * 0.3 ? 'warn' : ''],
    ['m_flow', `${num(f.effective_flow_cm_s, 1)}<small>cm/s</small>`],
  ];
  const box = $('metrics'); box.replaceChildren();
  for (const [k, v, cls] of metrics) {
    const d = document.createElement('div'); d.className = `metric ${cls || ''}`;
    const s = document.createElement('span'); s.textContent = t(k, { smac: `${smac} ppm` });
    const b = document.createElement('b'); b.innerHTML = v;       // numbers formatted locally, no external text
    d.append(s, b); box.append(d);
  }
  flammabilityMap($('mapChart'), r.map, { p: r.inputs.pressure_kpa, o: r.inputs.o2_pct, flammable: f.flammable },
    ATM_PRESETS.slice(0, 3).map((x) => ({ p: x.p, o: x.o, label: x.label.split(' ')[0] })), { flam: t('map_flam'), nonflam: t('map_nonflam') });
  $('mapLegend').innerHTML = '';
  for (const [c, k, dash] of [['#f08a3c', 'map_eff'], ['#8e9aa4', 'map_1g', 1], ['#5ad1e6', 'map_norm', 1]]) {
    const s = document.createElement('span'); const i = document.createElement('i');
    i.style.background = dash ? `repeating-linear-gradient(90deg,${c} 0 3px,transparent 3px 5px)` : c;
    s.append(i, t(k)); $('mapLegend').append(s);
  }
  const s2 = document.createElement('span'); s2.textContent = `○ ${t('map_meas')} (NASA WSTF)`; $('mapLegend').append(s2);
  $('tsLegend').innerHTML = '';
  for (const [c, k] of [['#f08a3c', 'ts_hrr'], ['#a58cff', 'ts_co'], ['#9aa5ad', 'ts_smoke']]) {
    const s = document.createElement('span'); const i = document.createElement('i'); i.style.background = c; s.append(i, t(k)); $('tsLegend').append(s);
  }
  $('tsSub').textContent = `${mmss(r.inputs.duration_s)} · ${r.inputs.auto_vent_shutdown ? 'auto vent-off' : ''}`;
  $('time').max = r.inputs.duration_s; $('tEnd').textContent = mmss(r.inputs.duration_s);
  const marks = $('eventMarks'); marks.replaceChildren();
  for (const e of tl.events) {
    if (e.key === 'ignition') continue;
    const i = document.createElement('i'); i.style.left = `${e.t / r.inputs.duration_s * 100}%`; i.style.background = EV_COLOR[e.key] || '#999';
    i.dataset.l = t(`ev_${e.key}`); marks.append(i);
  }
  const env = catalog.environments[r.inputs.environment];
  $('hudEnv').textContent = `HAB–01 · ${label(env.label)}`;
  $('hudSub').textContent = `${num(r.inputs.pressure_kpa, 1)} kPa · ${num(r.inputs.o2_pct, 1)} % O₂ · ${num(r.inputs.temp_c, 0)} °C · ${label(catalog.materials[r.inputs.material].label)}`;
  renderLog();
}

function renderLog() {
  if (!result) return;
  const ol = $('eventLog'); ol.replaceChildren();
  for (const e of result.timeline.events) {
    const li = document.createElement('li'); li.className = e.t <= simT ? 'past' : 'future';
    const tm = document.createElement('time'); tm.textContent = mmss(e.t);
    const i = document.createElement('i'); i.style.background = EV_COLOR[e.key] || '#999';
    const s = document.createElement('span');
    s.textContent = t(`ev_${e.key}`) + (e.detail === 'burnout' ? ` (${t('burnout')})` : e.detail === 'crew' ? ` — ${t('how_crew')}` : '');
    li.append(tm, i, s); ol.append(li);
  }
}

function renderHud(row) {
  const h = $('hudReadout');
  if (!row) { h.replaceChildren(); return; }
  const items = [['hud_hrr', `${num(row.hrr_kw, row.hrr_kw < 1 ? 2 : 1)} kW`], ['hud_o2', `${num(row.o2_pct, 2)} %`], ['hud_co', `${num(row.co_ppm, 1)} ppm`],
    ['hud_flow', row.vent ? `${num(S.vent_cm_s, 0)} cm/s` : t('vent_off')]];
  h.replaceChildren(...items.map(([k, v]) => { const d = document.createElement('div'); const s = document.createElement('span'); s.textContent = t(k); const b = document.createElement('b'); b.textContent = v; d.append(s, b); return d; }));
}

// ---------------------------------------------------------------- evidence + research drawer
async function loadEvidence() {
  const key = `${S.environment}|${result.inputs.material}`;
  if (loadEvidence.key === key) return;
  loadEvidence.key = key;
  try {
    evidenceRecs = (await api(`/api/fire/evidence?environment=${encodeURIComponent(S.environment)}&material=${encodeURIComponent(result.inputs.material)}`)).records;
  } catch { evidenceRecs = []; }
  const ul = $('refsShort'); ul.replaceChildren();
  for (const r of evidenceRecs.slice(0, 4)) {
    const li = document.createElement('li'); const a = document.createElement('a');
    a.href = r.url || '#'; a.target = '_blank'; a.rel = 'noopener'; a.textContent = r.title;
    const sm = document.createElement('small'); sm.textContent = [r.source, r.year].filter(Boolean).join(' · ');
    li.append(a, sm); ul.append(li);
  }
  renderResearch();
}

function renderResearch() {
  const list = $('researchList'); list.replaceChildren();
  $('recordView').hidden = true; list.hidden = false;
  if (!evidenceRecs.length) { list.textContent = t('research_none'); return; }
  for (const r of evidenceRecs) {
    const b = document.createElement('button'); b.className = 'rcard';
    const h = document.createElement('h4'); h.textContent = r.title;
    const p = document.createElement('p'); p.textContent = r.summary || '';
    const m = document.createElement('div'); m.className = 'meta';
    const badge = document.createElement('span'); badge.className = `badge ${r.status === 'curated' ? 'curated' : 'collected'}`; badge.textContent = r.status || 'record';
    m.append(badge, [r.source, r.year].filter(Boolean).join(' · '));
    b.append(h, p, m); b.onclick = () => openRecord(r);
    list.append(b);
  }
}

async function openRecord(brief) {
  const view = $('recordView'); const list = $('researchList');
  let rec = brief;
  try { rec = await api(`/api/research/${encodeURIComponent(brief.slug)}`); } catch { /* index still building: use the brief */ }
  view.replaceChildren();
  const back = document.createElement('button'); back.className = 'link'; back.textContent = t('back');
  back.onclick = () => { view.hidden = true; list.hidden = false; };
  const h = document.createElement('h3'); h.textContent = rec.title;
  const meta = document.createElement('div'); meta.className = 'meta'; meta.style.cssText = 'font:10px var(--mono);color:var(--dim)';
  meta.textContent = [rec.org, rec.source, rec.year].filter(Boolean).join(' · ');
  const p = document.createElement('p'); p.textContent = rec.summary || '';
  view.append(back, h, meta, p);
  if (rec.details) { const d = document.createElement('p'); d.textContent = rec.details; view.append(d); }
  if (rec.facts?.length) {
    const h4 = document.createElement('h3'); h4.className = 'h3'; h4.textContent = t('facts'); h4.style.marginTop = '14px';
    const tb = document.createElement('table');
    for (const f of rec.facts.slice(0, 40)) {
      const tr = document.createElement('tr');
      const a = document.createElement('td'); a.textContent = f.name;
      const b = document.createElement('td'); b.textContent = `${f.value} ${f.unit || ''}`;
      tr.append(a, b); tb.append(tr);
    }
    view.append(h4, tb);
  }
  const srcs = rec.sources?.length ? rec.sources : rec.url ? [{ title: rec.title, url: rec.url }] : [];
  if (srcs.length) {
    const h4 = document.createElement('h3'); h4.className = 'h3'; h4.textContent = t('sources'); h4.style.marginTop = '14px';
    view.append(h4);
    for (const s of srcs) {
      const a = document.createElement('a'); a.textContent = s.title || s.url; a.style.display = 'block'; a.style.margin = '4px 0';
      if (s.url && /^https?:\/\//.test(s.url)) { a.href = s.url; a.target = '_blank'; a.rel = 'noopener'; }
      view.append(a);
    }
  }
  list.hidden = true; view.hidden = false;
}

function openTab(tab, fromClose = false) {
  for (const b of document.querySelectorAll('.tab')) b.classList.toggle('is-active', b.dataset.tab === tab);
  if (fromClose) return;
  if (tab === 'research') { $('consoleDrawer').close(); $('researchDrawer').showModal(); renderResearch(); }
  else if (tab === 'console') { $('researchDrawer').close(); $('consoleDrawer').showModal(); $('chatInput').focus(); }
  else { $('researchDrawer').close(); $('consoleDrawer').close(); }
}

// ---------------------------------------------------------------- AI console
function chatMessage(role, text, html) {
  const d = document.createElement('div'); d.className = `msg ${role}`;
  if (html) d.innerHTML = html;            // server-rendered, escaped Markdown
  else d.textContent = text;
  $('chatLog').append(d); d.scrollIntoView({ block: 'end' });
  return d;
}

async function sendChat(e) {
  e.preventDefault();
  const text = $('chatInput').value.trim();
  if (!text) return;
  $('chatInput').value = '';
  chatMessage('user', text);
  const pending = chatMessage('assistant pending', t('thinking'));
  try {
    const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text, lang: getLang(), context: scenarioBody() }) });
    const data = await r.json();
    pending.remove();
    if (!r.ok) throw new Error(data.error || r.status);
    chatMessage('assistant', data.message.text, data.message.html);
  } catch { pending.remove(); chatMessage('assistant', t('chat_error')); }
}

async function loadSession() {
  try {
    const s = await api('/api/session');
    for (const m of s.messages.slice(-12)) chatMessage(m.role, m.text, m.role === 'assistant' ? m.html : null);
  } catch { /* no session yet */ }
}

// ---------------------------------------------------------------- guided tour
let touring = false;
async function tour() {
  if (touring) { touring = false; return; }
  touring = true;
  const steps = t('tour_steps');
  const plan = [
    () => { setView('exterior'); },
    () => { S.location = 'galley'; S.material = null; selectEnvironment('leo'); setTimeout(() => setView('fire'), 600); },
    () => { selectEnvironment('lunar_orbit'); setView('cutaway'); },
    () => { selectEnvironment('moon'); setTimeout(() => setView('fire'), 700); },
    () => { selectEnvironment('mars'); setTimeout(() => setView('exterior'), 300); },
  ];
  const cap = $('caption');
  for (let i = 0; i < plan.length && touring; i++) {
    plan[i]();
    cap.hidden = false; cap.replaceChildren();
    const b = document.createElement('b'); b.textContent = `${i + 1}/${plan.length} · ${steps[i][0]}`;
    cap.append(b, steps[i][1]);
    await new Promise((res) => setTimeout(res, 7500));
  }
  cap.hidden = true; touring = false;
}

// ---------------------------------------------------------------- language, url state
function relabel() {
  for (const b of document.querySelectorAll('[data-lang]')) b.classList.toggle('is-on', b.dataset.lang === getLang());
  $('chatInput').placeholder = t('chat_ph');
  if (!catalog) return;
  buildScenario(); syncInputs();
  viewer?.relabel((k) => label(catalog.locations[k].label).split(' (')[0]);
  if (result) renderResults();
  setMode(viewer?.mode || 'normal');
}

function saveHash() {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(S)) if (v !== null && v !== undefined) q.set(k, String(v));
  history.replaceState(null, '', `#${q}`);
}

function loadHash() {
  const q = new URLSearchParams(location.hash.slice(1));
  for (const k of Object.keys(S)) {
    if (!q.has(k)) continue;
    const v = q.get(k);
    S[k] = typeof S[k] === 'boolean' ? v === 'true' : ['environment', 'location', 'material', 'suppression'].includes(k) ? v : Number(v);
  }
  if (!catalog.environments[S.environment]) S.environment = 'leo';
  if (!catalog.locations[S.location]) S.location = 'avionics_rack';
  if (S.material && !catalog.materials[S.material]) S.material = null;
}

// ---------------------------------------------------------------- playback loop
function frame(now) {
  requestAnimationFrame(frame);
  const dt = lastFrame ? Math.min(0.1, (now - lastFrame) / 1000) : 0;
  lastFrame = now;
  if (!result) return;
  const dur = result.inputs.duration_s;
  let dSim = 0;
  if (playing) { dSim = dt * speed; simT = Math.min(dur, simT + dSim); if (simT >= dur) playing = false; }
  const row = rowAt(simT);
  viewer?.setTime(simT, row, dSim);
  $('time').value = simT; fill($('time'));
  $('tNow').textContent = mmss(simT);
  $('playIcon').setAttribute('d', playing ? 'M4 2.5h3v11H4zM9 2.5h3v11H9z' : 'M4 2.5v11l9-5.5z');
  if (!frame.n || now - frame.n > 120) {           // ~8 Hz for the DOM-heavy parts
    frame.n = now;
    renderHud(row);
    timeSeries($('tsChart'), result.series, result.timeline.events, dur, simT, {});
    const past = [...$('eventLog').children];
    result.timeline.events.forEach((e, i) => past[i] && (past[i].className = e.t <= simT ? 'past' : 'future'));
  }
}

// ---------------------------------------------------------------- boot
async function boot() {
  setLang(getLang());
  relabel();
  bindInputs();
  catalog = await api('/api/fire/catalog');
  loadHash();
  buildScenario();
  relabel();
  syncInputs();
  setView('exterior'); setMode('normal');
  runSimulation();
  requestAnimationFrame(frame);
  loadSession();
  const bar = $('loadBar');
  try {
    const { Viewer } = await import('./viewer/viewer.js');
    viewer = new Viewer($('gl'), $('viewport'), $('labels'));
    window.bfx = { viewer };                      // handy for debugging in the console
    await viewer.init((p) => { bar.style.width = `${Math.round(p * 100)}%`; });
    await viewer.setEnvironment(S.environment, catalog.environments[S.environment].g_fraction);
    viewer.setMarkers(catalog.locations, (k) => label(catalog.locations[k].label).split(' (')[0], selectLocation);
    viewer.setView('exterior', true);
    if (result) viewer.setScenario(result, catalog);
    bar.style.width = '100%';
    $('loader').classList.add('done');
  } catch (e) {
    console.error(e);
    $('loader').querySelector('span').textContent = 'WebGL 2 is required for the 3D view.';
  }
}
boot();
