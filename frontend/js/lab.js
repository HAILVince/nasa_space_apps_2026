// The lab page: one interactive scenario, its 3D view and the results.
import { t, label, getLang } from './i18n.js';
import { flammabilityMap, timeSeries, timeCursor } from './charts.js';
import { $, api, num, mmss, loadEvidence, bindChrome } from './common.js';
import { SpreadEngine } from './spread/engine.js';
import { CFDEngine } from './cfd/engine.js';
import { TIERS, ORDER, detect, chooseTier, savedChoice, saveChoice, Governor, describe } from './device.js';

const S = {
  environment: 'leo', location: 'avionics_rack', material: null, pressure_kpa: null, o2_pct: null, temp_c: null,
  vent_cm_s: 12, auto_vent_shutdown: true, suppression: 'co2', response_s: 60,
};
let catalog = null, result = null, viewer = null, flameCtx = { envelopes: [], pending: [], habitats: [], incidents: [], investigations: [] };
let simT = 0, playing = true, speed = 8, lastFrame = 0;
// one main simulator: the cabin model (server, 3D view) and the 2D fire-spread model run on the same
// scenario, and nothing runs until the user presses Start. Each Start is saved for the session.
let lining = 'sibal', runId = null, started = false, dirty = false, starting = false, view = '3d';
let cfd = null, cfdModel = 'habitat', cfdKey = '', cfdRun = null, lastStart = null;
let spread = null, dev = null, cpuMs = null, tier = 'medium', tierChoice = 'auto', governor = null, viewerLoading = false;
const SPEEDS = [1, 4, 8, 16, 32];
const FIXED_AGENTS = new Set(['k_aerosol', 'clean_agent', 'inert_n2']);     // discharge by themselves after the alarm
const ORBS = {
  leo: 'radial-gradient(circle at 35% 35%,#8fd0ff,#1d5fa8 55%,#0a2142)',
  lunar_orbit: 'radial-gradient(circle at 35% 35%,#e9e9e6,#8d8c88 55%,#2f2f2d)',
  moon: 'linear-gradient(180deg,#000 0 50%,#8b8985 50%)',
  mars: 'radial-gradient(circle at 35% 35%,#f0a070,#b3532a 55%,#4a1d0c)',
  earth: 'radial-gradient(circle at 35% 35%,#d9dde0,#6c757c 60%,#2b3034)',
};
const EV_COLOR = { ignition: '#f08a3c', alarm: '#e8c547', vent_off: '#5ad1e6', co2: '#5ad1e6', water_mist: '#5ad1e6', k_aerosol: '#5ad1e6', clean_agent: '#5ad1e6', inert_n2: '#5ad1e6', crew_on_scene: '#8e9aa4', extinguished: '#59d38c', self_extinguished: '#59d38c', co_smac: '#a58cff' };

const fill = (input) => input.style.setProperty('--fill', `${(input.value - input.min) / (input.max - input.min) * 100}%`);

function scenarioBody() {
  return { ...S };
}

// a setting changed: nothing runs until Start (the last run stays on screen, marked as out of date)
function changed() {
  dirty = true;
  saveHash();
  renderStartState();
  if (!started) spread?.preview(lining);
}

// Start: the server runs the cabin model and saves the starting parameters for the session (the AI can
// read them later); then the 3D playback and the 2D spread model start from the same scenario.
async function start() {
  if (starting || !catalog) return;
  starting = true; renderStartState();
  saveHash();
  let r;
  try { r = await api('/api/sim/start', { scenario: scenarioBody(), lining, device: deviceInfo() }); }
  catch (e) { console.error(e); starting = false; renderStartState(t('start_failed')); return; }
  starting = false;
  if (spread.started && !spread.finishedSent) sendSpread(true);     // the previous run, as far as it got
  runId = r.run_id; result = r.result; started = true; dirty = false;
  viewer?.setScenario(result, catalog); viewer?.setTime(0, rowAt(0), -1);
  simT = 0; playing = true;
  renderResults();
  loadEvidence(S.environment, result.inputs.material);
  const i = result.inputs, env = catalog.environments[i.environment];
  spread.start({ g: +env.g_fraction.toFixed(3), o2: i.o2_pct, p: i.pressure_kpa, u: i.vent_cm_s, lining,
    location: i.location, autoVent: i.auto_vent_shutdown });
  // the CFD model runs only while its tab is open (it is the heaviest); it starts from the same scenario
  if (cfd.started && !cfd.finishedSent) sendCfd(true);
  cfd.stop(); cfd.started = false; cfdKey = '';
  lastStart = { g: +env.g_fraction.toFixed(3), X: i.o2_pct, Pk: i.pressure_kpa, U: i.vent_cm_s, lining, location: i.location, autoVent: i.auto_vent_shutdown };
  if (view === 'cfd') ensureCfd();
  renderStartState();
}

// the 2D model's outcome joins the saved run when it ends (or, partly, when the page is left)
function sendSpread(partial) {
  if (runId === null || !spread?.started) return;
  const body = JSON.stringify({ run_id: runId, ...spread.summary() });
  if (partial && navigator.sendBeacon) { navigator.sendBeacon('/api/sim/spread', new Blob([body], { type: 'application/json' })); return; }
  fetch('/api/sim/spread', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => {});
}

function ensureCfd() {
  if (!lastStart || runId === null) return;
  const key = `${runId}:${cfdModel}`;
  if (cfdKey === key) return;
  if (cfd.started && !cfd.finishedSent) sendCfd(true);
  cfdKey = key; cfdRun = runId;
  cfd.start(lastStart, cfdModel, tier);
  $('cfdPlay').textContent = t('sp_pause');
}

function sendCfd(partial) {
  if (cfdRun === null || !cfd.started || !cfd.G) return;
  const body = JSON.stringify({ run_id: cfdRun, ...cfd.summary() });
  if (partial && navigator.sendBeacon) { navigator.sendBeacon('/api/sim/outcome', new Blob([body], { type: 'application/json' })); return; }
  fetch('/api/sim/outcome', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => {});
}

function renderStartState(msg) {
  const b = $('startBtn');
  b.disabled = starting || !catalog;
  b.querySelector('span').textContent = t(starting ? 'starting' : started ? 'start_again' : 'start');
  b.classList.toggle('attn', !started || dirty);
  $('startNote').textContent = msg || (starting ? '' : !started ? t('start_first') : dirty ? t('start_dirty') : t('start_saved'));
  $('center').classList.toggle('idle', !started);
}

function deviceInfo() {
  return { tier, chosen: tierChoice, cores: dev.cores, memory_gb: dev.memory_gb, mobile: dev.mobile, gpu: dev.gpu,
    dpr: dev.dpr, cpu_ms: cpuMs === null ? null : Math.round(cpuMs), view3d: !!viewer };
}

// ---------------------------------------------------------------- device tier and the two views
function applyTier(name) {
  tier = name;
  const q = TIERS[name];
  spread.setQuality({ dpr: q.dpr, smooth: q.smooth, flames: q.flames, budgetMs: q.budgetMs, uiHz: q.uiHz, fps: q.fps });
  if (viewer && ORDER.indexOf(q.viewer) < ORDER.indexOf(viewer.tier)) viewer.setTier(q.viewer);
  const d = describe(dev, tier, cpuMs);
  $('deviceText').textContent = `${t(`tier_${tier}`)} · ${d.text}`;
  $('deviceText').title = d.gpu;
  $('qualitySel').value = tierChoice;
}

function setSimView(v) {
  view = ['2d', 'cfd'].includes(v) ? v : '3d';
  for (const b of $('simView').children) b.setAttribute('aria-checked', String(b.dataset.v === view));
  $('center').classList.toggle('v2d', view !== '3d');
  $('spread2d').hidden = view !== '2d';
  $('cfdView').hidden = view !== 'cfd';
  spread.visible = view === '2d';
  if (spread.visible) spread.resize();
  cfd.visible = view === 'cfd';
  if (cfd.visible) { if (started) ensureCfd(); cfd.resize(); cfd.panels(true); }
  viewer?.setActive(view === '3d');
  if (view === '3d' && !viewer && !viewerLoading) $('load3d').hidden = false;
  governor?.reset();
  saveHash();
}

// ---------------------------------------------------------------- scenario panel
function buildScenario() {
  const grid = $('envGrid');
  grid.replaceChildren();
  for (const [key, env] of Object.entries(catalog.environments)) {
    const b = document.createElement('button');
    b.className = 'env'; b.setAttribute('role', 'radio'); b.dataset.v = key;
    if (key === 'moon' || key === 'mars') b.addEventListener('pointerenter', () => viewer?.envs.terrainFor(key).catch(() => {}), { once: true });
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
    c.onclick = () => { S.pressure_kpa = pr.p; S.o2_pct = pr.o; syncInputs(); changed(); };
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
  changed();
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
  $('supHint').textContent = FIXED_AGENTS.has(S.suppression) ? t('sup_fixed_hint') : '';
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
    $(id).addEventListener('input', (e) => { S[key] = conv(e.target.value); syncInputs(); changed(); });
  };
  on('pressure', 'pressure_kpa'); on('o2', 'o2_pct'); on('temp', 'temp_c'); on('vent', 'vent_cm_s'); on('respTime', 'response_s');
  $('location').onchange = (e) => selectLocation(e.target.value);
  $('material').onchange = (e) => { S.material = e.target.value; syncInputs(); changed(); };
  $('autoVent').onchange = (e) => { S.auto_vent_shutdown = e.target.checked; changed(); };
  for (const b of $('suppression').children) b.onclick = () => { S.suppression = b.dataset.v; syncInputs(); changed(); };
  $('resetAtm').onclick = () => selectEnvironment(S.environment);
  for (const b of $('viewSeg').children) b.onclick = () => setView(b.dataset.v);
  for (const b of $('modeSeg').children) b.onclick = () => setMode(b.dataset.v);
  $('play').onclick = () => { if (!started) return start(); playing = !playing; if (result && simT >= result.inputs.duration_s) simT = 0; };
  $('restart').onclick = () => { simT = 0; playing = true; viewer?.setTime(0, rowAt(0), -1); };
  $('speed').onclick = () => { speed = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length]; $('speed').textContent = `×${speed}`; };
  $('time').addEventListener('input', (e) => { const nt = Number(e.target.value); viewer?.setTime(nt, rowAt(nt), nt < simT ? -1 : nt - simT); simT = nt; playing = false; });
  $('chatForm').onsubmit = sendChat;
  $('startBtn').onclick = start;
  $('lining').onchange = (e) => { lining = e.target.value; liningHint(); changed(); };
  for (const b of $('simView').children) b.onclick = () => setSimView(b.dataset.v);
  $('load3d').onclick = () => load3D();
  $('spPlay').onclick = () => {
    if (!spread.started) return start();
    spread.paused = !spread.paused; if (!spread.paused) spread.M.running = true;
    $('spPlay').textContent = t(spread.paused ? 'sp_run' : 'sp_pause');
  };
  $('spRestart').onclick = () => { if (spread.started) { spread.restart(); $('spPlay').textContent = t('sp_pause'); } };
  $('spVent').onclick = () => { if (spread.started) spread.toggleVent(); };
  for (const b of $('spSpeeds').children) b.onclick = () => { spread.speed = Number(b.dataset.s); for (const x of $('spSpeeds').children) x.classList.toggle('on', x === b); };
  for (const id of ['heat', 'smoke', 'flow', 'rings', 'o2']) $(`ly_${id}`).onchange = (e) => { spread.layers[id] = e.target.checked; spread.draw(true); };
  for (const b of $('cfdModel').children) b.onclick = () => {
    cfdModel = b.dataset.v;
    for (const x of $('cfdModel').children) x.setAttribute('aria-checked', String(x === b));
    saveHash();
    if (started && view === 'cfd') ensureCfd();
  };
  for (const b of $('cfdMode').children) b.onclick = () => {
    for (const x of $('cfdMode').children) x.setAttribute('aria-checked', String(x === b));
    cfd.setMode(b.dataset.v);
  };
  $('cfdPlay').onclick = () => {
    if (!started) return start();
    if (!cfd.started) return ensureCfd();
    cfd.setPaused(!cfd.paused); $('cfdPlay').textContent = t(cfd.paused ? 'sp_run' : 'sp_pause');
  };
  for (const b of $('cfdSpeeds').children) b.onclick = () => { cfd.setSpeed(Number(b.dataset.s)); for (const x of $('cfdSpeeds').children) x.classList.toggle('on', x === b); };
  for (const id of ['heat', 'smoke']) $(`cfd_${id}`).onchange = (e) => { cfd.els.layers[id] = e.target.checked; cfd.draw(true); };
  $('qualitySel').onchange = (e) => {
    tierChoice = e.target.value; saveChoice(tierChoice);
    applyTier(tierChoice === 'auto' ? chooseTier(dev, cpuMs) : tierChoice);
    if (TIERS[tier].load3d && !viewer && view === '3d') load3D();
  };
  $('agent-language').addEventListener('change', (e) => { e.target.dataset.touched = '1'; });
  $('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); $('chatForm').requestSubmit(); }
  });
}

function selectLocation(key) {
  S.location = key;
  S.material = null;              // each place has its typical material; the user can change it
  syncInputs();
  changed();
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
function rowAt(time, r = result) {
  if (!r) return null;
  const s = r.series;
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
    ATM_PRESETS.slice(0, 3).map((x) => ({ p: x.p, o: x.o, label: x.label.split(' ')[0] })), { flam: t('map_flam'), nonflam: t('map_nonflam') },
    flameCtx.envelopes);
  renderCoverage();
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

// Flame in Freefall: has a microgravity experiment covered this atmosphere? (flame/data envelopes)
function renderCoverage() {
  const box = $('coverage');
  if (!box || !result) return;
  const env = catalog.environments[S.environment];
  const p = result.inputs.pressure_kpa, o = result.inputs.o2_pct;
  const micro = env.g_fraction < 0.01;
  const hits = flameCtx.envelopes.filter((e) => o >= e.o2Pct[0] - 0.5 && o <= e.o2Pct[1] + 0.5 && p >= e.pressureKPa[0] * 0.97 && p <= e.pressureKPa[1] * 1.03);
  box.replaceChildren();
  const status = document.createElement('p');
  status.className = `cov-status ${hits.length && micro ? 'ok' : 'gap'}`;
  status.textContent = !micro ? t('cov_partial') : hits.length ? t('cov_yes', { n: hits.length }) : t('cov_no');
  box.append(status);
  const fm = result.flammability;
  if (env.g_fraction < 0.99 && fm.gravity_basis) {
    const g = document.createElement('p'); g.className = 'cov-note';
    const d = `${fm.gravity_shift > 0 ? '+' : fm.gravity_shift < 0 ? '−' : '±'}${num(Math.abs(fm.gravity_shift), 1)}`;
    g.textContent = t(fm.gravity_basis === 'measured' ? 'cov_g_meas' : 'cov_g_gen', { d });
    box.append(g);
  }
  // link to the investigation's PSI record; no psiUrl, no link (records without one are skipped quietly)
  const psiLink = (inv, text) => {
    if (!inv?.psiUrl) return null;
    const a = document.createElement('a');
    a.href = inv.psiUrl; a.target = '_blank'; a.rel = 'noopener noreferrer';
    a.textContent = text; a.title = a.ariaLabel = `${t('psi_open')}: ${inv.accession}`;
    return a;
  };
  const invs = new Map((flameCtx.investigations || []).map((i) => [i.accession, i]));
  let withEarth = 0;
  // every envelope is checked against the PSI table or a quoted NASA document (flame.ingest.verify);
  // a value no source gives is shown as "not reported", with the reason on hover
  for (const e of (micro ? hits : [...flameCtx.envelopes, ...(flameCtx.pending || [])])) {
    const row = document.createElement('div'); row.className = 'cov-row';
    const b = document.createElement('b');
    const acc = psiLink(invs.get(e.accession), e.accession);
    if (acc) { acc.className = 'psi-link'; b.append(acc, ` · ${e.acronym}`); } else b.textContent = `${e.accession} · ${e.acronym}`;
    const sm = document.createElement('span');
    const span = (r, unit) => `${+r[0].toFixed(1)}${r[1] !== r[0] ? `–${+r[1].toFixed(1)}` : ''} ${unit}`;
    const nr = e.notReported || {};
    const o2 = e.o2Pct ? span(e.o2Pct, '% O₂') : `O₂: ${t('cov_nr')}`;
    const pk = e.pressureKPa ? span(e.pressureKPa, 'kPa') : `${t('cov_p')}: ${t('cov_nr')}`;
    sm.textContent = `${o2} · ${pk} · ${e.fuel}`;
    const why = Object.values(nr);
    if (why.length) sm.title = [...new Set(why)].join('\n');
    const ok = document.createElement('i'); ok.className = e.verified ? 'cov-ok' : 'cov-open';
    ok.textContent = e.verified ? t('cov_checked') : t('cov_unchecked');
    ok.title = (e.provenance || []).map((x) => x.source).filter((x, i, a) => a.indexOf(x) === i).join('\n');
    const details = document.createElement('span');
    const values = (items) => Array.isArray(items) && items.length ? items.join(', ') : t('cov_nr');
    details.textContent = `${t('cov_measured')}: ${values(e.measured)} · ${t('cov_sensors')}: ${values(e.sensors)}`;
    row.append(b, sm, details, ok);
    // NASA's own "Earth benefits" statement for this investigation, shown verbatim (not translated)
    const inv = invs.get(e.accession);
    if (inv?.earthBenefits) {
      const d = document.createElement('details'); d.className = 'cov-earth';
      const sum = document.createElement('summary'); sum.textContent = t('earth_row');
      const q = document.createElement('blockquote'); q.lang = 'en'; q.textContent = inv.earthBenefits;
      d.append(sum, q);
      const src = psiLink(inv, `${t('earth_src')} ${inv.accession}`); if (src) d.append(src);
      row.append(d); withEarth++;
    }
    box.append(row);
  }
  if (withEarth) {
    const n = document.createElement('p'); n.className = 'cov-note cov-earth-note';
    n.textContent = t('earth_block', { n: withEarth });
    box.append(n);
  }
  // Match both environment and atmosphere: lunar habitat, rover and EVA can share a body.
  const insightHabitats = {leo: ['iss'], lunar_orbit: ['orion'], moon: ['moon-base', 'rover', 'suit'], mars: ['mars-base']};
  const matching = (insightHabitats[S.environment] || []).map((id) => flameCtx.habitats.find((h) => h.id === id))
    .filter((h) => h && o >= h.o2Pct[0] - 0.5 && o <= h.o2Pct[1] + 0.5 &&
      p >= h.pressureKPa[0] - 0.5 && p <= h.pressureKPa[1] + 0.5 && (flameCtx.insights?.[h.id] || []).length);
  if (matching.length) {
    const heading = document.createElement('p'); heading.className = 'insights-title'; heading.textContent = t('insights_title'); box.append(heading);
    const sources = new Map((flameCtx.investigations || []).map((i) => [i.accession, i.psiUrl]));
    for (const incident of (flameCtx.incidents || [])) sources.set(incident.id, incident.sourceUrl);
    for (const habitat of matching) {
      const name = document.createElement('p'); name.className = 'insights-habitat'; name.textContent = habitat.name; box.append(name);
      for (const insight of flameCtx.insights[habitat.id]) {
        const paragraph = document.createElement('p'); paragraph.className = 'insight'; paragraph.lang = 'en';
        const prose = document.createElement('span'); prose.textContent = insight.text; paragraph.append(prose);
        const citations = document.createElement('span'); citations.className = 'insight-citations';
        for (const [index, cited] of insight.cited.entries()) {
          if (index) citations.append(document.createTextNode(', '));
          const ntrs = /^NTRS (\d+)$/.exec(cited);
          const url = sources.get(cited) || (ntrs ? `https://ntrs.nasa.gov/citations/${ntrs[1]}` : null);
          const link = document.createElement(url ? 'a' : 'span'); link.textContent = cited;
          if (url && /^https:\/\/(psi\.nasa\.gov|ntrs\.nasa\.gov|www\.nasa\.gov)\//.test(url)) {
            link.href = url; link.target = '_blank'; link.rel = 'noopener';
          }
          citations.append(link);
        }
        paragraph.append(citations); box.append(paragraph);
      }
    }
  }
  const near = flameCtx.habitats.filter((h) => o >= h.o2Pct[0] - 1 && o <= h.o2Pct[1] + 1 && p >= h.pressureKPa[0] - 2 && p <= h.pressureKPa[1] + 2);
  if (near.length) {
    const h = document.createElement('p'); h.className = 'cov-note';
    h.textContent = `${t('cov_habitats')}: ${near.map((x) => x.name).join(', ')}`;
    box.append(h);
  }
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
// ---------------------------------------------------------------- AI console
function chatMessage(role, text, html, snapshot) {
  const d = document.createElement('div'); d.className = `msg ${role}`;
  if (html) d.innerHTML = html;            // server-rendered, escaped Markdown
  else d.textContent = text;
  if (snapshot) { const pre = document.createElement('pre'); pre.textContent = snapshot; d.append(pre); }
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
    const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text, lang: $('agent-language').value, context: scenarioBody() }) });
    const data = await r.json().catch(() => ({}));
    pending.remove();
    if (!r.ok) { chatMessage('assistant', t(chatErrorKey(r.status, data))); return; }
    chatMessage('assistant', data.message.text, data.message.html, data.message.snapshot);
    if (data.scenario) applyScenario(data.scenario);
  } catch { pending.remove(); chatMessage('assistant', t('chat_error')); }
}

// the AI changed the scenario with its set_fire_scenario tool: show it exactly as if the user had clicked it
function applyScenario(sc) {
  const environmentChanged = sc.environment !== S.environment;
  for (const k of Object.keys(S)) if (k in sc) S[k] = sc[k];
  if (!catalog.environments[S.environment]) S.environment = 'leo';
  if (!catalog.locations[S.location]) S.location = 'avionics_rack';
  if (S.material && !catalog.materials[S.material]) S.material = null;
  syncInputs();
  if (environmentChanged) viewer?.setEnvironment(S.environment, catalog.environments[S.environment].g_fraction);
  changed();                                  // the AI sets the values; the user presses Start
}

// say what actually went wrong: too many questions, the AI key, the AI service, or the message itself
function chatErrorKey(status, data) {
  if (status === 429 || data.error === 'rate_limited') return 'chat_rate_limited';
  if (data.error === 'too_long') return 'chat_too_long';
  if (data.reason === 'auth' || data.reason === 'no_key') return 'chat_error_key';
  if (data.reason === 'unreachable') return 'chat_error_down';
  return 'chat_error';
}

async function loadSession() {
  try {
    const s = await api('/api/session');
    for (const m of s.messages.slice(-12)) chatMessage(m.role, m.text, m.role === 'assistant' ? m.html : null, m.snapshot);
  } catch { /* no session yet */ }
}

// ---------------------------------------------------------------- language, url state
function relabel() {
  $('chatInput').placeholder = t('chat_ph');
  if (!$('agent-language').dataset.touched) $('agent-language').value = getLang();   // replies follow the page language
  if (spread && dev) { renderStartState(); $('deviceText').textContent = `${t(`tier_${tier}`)} · ${describe(dev, tier, cpuMs).text}`; }
  if (!catalog) return;
  buildScenario(); syncInputs();
  viewer?.relabel((k) => label(catalog.locations[k].label).split(' (')[0]);
  if (result) renderResults();
  setMode(viewer?.mode || 'normal');
}

function saveHash() {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(S)) if (v !== null && v !== undefined) q.set(k, String(v));
  q.set('lining', lining); q.set('view', view); q.set('cfd', cfdModel);
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
  if (spread.M.MAT[q.get('lining')]) lining = q.get('lining');
  if (['2d', '3d', 'cfd'].includes(q.get('view'))) view = q.get('view');
  if (['habitat', 'living', 'spacecraft'].includes(q.get('cfd'))) cfdModel = q.get('cfd');
}

// ---------------------------------------------------------------- playback loop
function frame(now) {
  requestAnimationFrame(frame);
  const dt = lastFrame ? Math.min(0.1, (now - lastFrame) / 1000) : 0;
  lastFrame = now;
  if (spread) {
    spread.frame(now, dt);
    if (spread.visible && spread.started && !spread.paused && spread.M.running) governor?.frame(now); else governor?.reset();
    if (spread.finished && !spread.finishedSent) { spread.finishedSent = true; sendSpread(false); }
  }
  if (cfd) {
    cfd.frame(now);
    if (cfd.started && cfd.finished && !cfd.finishedSent) { cfd.finishedSent = true; sendCfd(false); }
  }
  if (!result) return;
  const dur = result.inputs.duration_s;
  let dSim = 0;
  if (playing) { dSim = dt * speed; simT = Math.min(dur, simT + dSim); if (simT >= dur) playing = false; }
  const row = rowAt(simT);
  if (viewer) viewer.calm = !playing;
  viewer?.setTime(simT, row, dSim);
  // the DOM is only written when what it shows changes (a paused lab writes nothing)
  const ui = frame.ui || (frame.ui = {});
  if (ui.t !== simT) { ui.t = simT; $('time').value = simT; fill($('time')); $('tNow').textContent = mmss(simT); }
  if (ui.playing !== playing) { ui.playing = playing; $('playIcon').setAttribute('d', playing ? 'M4 2.5h3v11H4zM9 2.5h3v11H9z' : 'M4 2.5v11l9-5.5z'); }
  if (!frame.n || now - frame.n > 120) {           // ~8 Hz for the DOM-heavy parts
    frame.n = now;
    const lang = getLang(), fresh = ui.result !== result;
    if (fresh || ui.hudT !== simT || ui.lang !== lang || ui.vent !== S.vent_cm_s) {
      ui.hudT = simT; ui.lang = lang; ui.vent = S.vent_cm_s;
      renderHud(row);
      const past = [...$('eventLog').children];
      result.timeline.events.forEach((e, i) => past[i] && (past[i].className = e.t <= simT ? 'past' : 'future'));
    }
    if (fresh) { ui.result = result; timeSeries($('tsChart'), result.series, result.timeline.events, dur, simT, {}); }
    else timeCursor($('tsChart'), simT, dur);
  }
}

// ---------------------------------------------------------------- boot
function liningHint() {
  const m = spread.M.MAT[lining];
  $('liningHint').textContent = m ? m.note : '';
}

// the 3D view: loaded at once on capable devices, on request (button) on weak ones
async function load3D() {
  if (viewer || viewerLoading) return;
  viewerLoading = true;
  $('load3d').hidden = true;
  $('loader').classList.remove('done');
  const bar = $('loadBar');
  try {
    if (!document.createElement('canvas').getContext('webgl2')) throw new Error('no WebGL 2');
    const { Viewer } = await import('./viewer/viewer.js');
    viewer = new Viewer($('gl'), $('viewport'), $('labels'), { wheelZoom: true, tier: TIERS[tier].viewer });
    window.bfx = { viewer, spread };              // handy for debugging in the console
    await viewer.init((p) => { bar.style.width = `${Math.round(p * 100)}%`; });
    await viewer.setEnvironment(S.environment, catalog.environments[S.environment].g_fraction);
    viewer.setMarkers(catalog.locations, (k) => label(catalog.locations[k].label).split(' (')[0], selectLocation);
    viewer.setInteractive(true);
    if (result) { viewer.setScenario(result, catalog); viewer.setTime(simT, rowAt(simT), -1); }
    viewer.setActive(view === '3d');
    viewer.flyIn('exterior');
    viewer.envs.prefetch();                       // Gateway globe and rocks, once the page is idle
    bar.style.width = '100%';
    setTimeout(() => $('loader').classList.add('done'), 300);
  } catch (e) {
    console.error(e);
    $('loader').querySelector('span').textContent = t('webgl');
    $('loadBar').parentElement.hidden = true;
  }
  viewerLoading = false;
}

// the settings of the visitor's last started run come back after a reload (unless the link carries its own)
async function restoreLastRun() {
  if (location.hash.length > 1) return false;
  try {
    const { runs } = await api('/api/sim/runs?limit=1');
    const last = runs && runs[0];
    if (!last) return false;
    for (const k of Object.keys(S)) if (k in last.settings) S[k] = last.settings[k];
    if (spread.M.MAT[last.settings.lining]) lining = last.settings.lining;
    return true;
  } catch { return false; }
}

async function boot() {
  // the desktop lab is a fixed full-screen app: focusing a control must never scroll the page
  addEventListener('scroll', () => { if (scrollY && !matchMedia('(max-width: 900px)').matches) scrollTo(0, 0); }, { passive: true });
  bindChrome(relabel);
  spread = new SpreadEngine({ canvas: $('spCanvas'), growth: $('spGrowth'), map: $('spMap'), mapMat: $('spMapMat'), rooms: $('spRooms'),
    log: $('spLog'), tiles: $('spTiles'), status: $('spStatus'), clock: $('spClock'), speedOut: $('spAch') });
  cfd = new CFDEngine({ canvas3d: $('cfdCanvas'), section: $('cfdSection'), rooms: $('cfdRooms'), status: $('cfdStatus'), clock: $('cfdClock'),
    ach: $('cfdAch'), grid: $('cfdGrid'), layers: { heat: true, smoke: true } });
  $('lining').replaceChildren(...spread.M.MKEYS.map((k) => new Option(spread.M.MAT[k].name, k)));
  bindInputs();
  relabel();
  // what this device can do: its reported specs plus one real measurement (the 2D model's flow solve)
  dev = detect();
  cpuMs = spread.benchmark();
  tierChoice = savedChoice();
  governor = new Governor(() => { const i = ORDER.indexOf(tier); if (tierChoice === 'auto' && i > 0) applyTier(ORDER[i - 1]); });
  catalog = await api('/api/fire/catalog');
  api('/api/flame/context').then((c) => {
    // envelopes whose ranges are not extracted yet (null) cannot be drawn or matched
    const ok = (r) => Array.isArray(r) && r.length === 2;
    flameCtx = { ...c, envelopes: c.envelopes.filter((e) => ok(e.o2Pct) && ok(e.pressureKPa)),
      pending: c.envelopes.filter((e) => !(ok(e.o2Pct) && ok(e.pressureKPa))),
      habitats: c.habitats.filter((h) => ok(h.o2Pct) && ok(h.pressureKPa)) };
    if (result) renderResults();
  }).catch(() => {});
  const restored = await restoreLastRun();
  loadHash();
  const asked = new URLSearchParams(location.search).get('view');
  if (asked === '2d' || asked === '3d') view = asked;
  applyTier(tierChoice === 'auto' ? chooseTier(dev, cpuMs) : tierChoice);
  if (!TIERS[tier].load3d && !location.hash.includes('view=')) view = asked || '2d';   // weak device: start with the 2D view
  $('lining').value = lining; liningHint();
  buildScenario();
  relabel();
  syncInputs();
  setView('exterior'); setMode('normal');
  setSimView(view);
  spread.preview(lining);
  renderStartState(restored ? t('start_restored') : undefined);
  requestAnimationFrame(frame);
  loadSession();
  addEventListener('pagehide', () => {
    if (spread.started && !spread.finishedSent) sendSpread(true);
    if (cfd.started && !cfd.finishedSent) sendCfd(true);
  });
  for (const x of $('cfdModel').children) x.setAttribute('aria-checked', String(x.dataset.v === cfdModel));
  if (TIERS[tier].load3d) load3D();
  else { $('loader').classList.add('done'); $('load3d').hidden = false; }
}
boot();


