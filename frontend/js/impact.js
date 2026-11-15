// BLACKFOX Impact, Before vs. After: the existing cabin fire model (POST /api/fire/simulate,
// blackfox/physics/fire.py) runs the identical scenario twice; only the post-ignition response differs.
// BEFORE: ventilation keeps running after the alarm and nothing is discharged. AFTER: ventilation shutdown on
// alarm + the selected extinguisher (the CO2 PFE if "none" is selected), with the same crew response time.
// Detection (smoke detector, crew) is physical and runs in both. Used by the lab and the home page.
import { t, label } from './i18n.js';
import { $, api, num, mmss } from './common.js';

const RESPONSE = ['auto_vent_shutdown', 'suppression'];

export async function runImpact(scenario) {
  const before = { ...scenario, auto_vent_shutdown: false, suppression: 'none' };
  const after = { ...scenario, auto_vent_shutdown: true, suppression: !scenario.suppression || scenario.suppression === 'none' ? 'co2' : scenario.suppression };
  const [b, a] = await Promise.all([api('/api/fire/simulate', before), api('/api/fire/simulate', after)]);
  // the engine resolves the scenario (defaults, material) itself: every input but the response must match
  if (!Object.keys(b.inputs).every((k) => RESPONSE.includes(k) || b.inputs[k] === a.inputs[k])) throw new Error('inputs differ');
  return { b, a };
}

export function renderImpact(out, note, impact) {
  if (!impact) { out.replaceChildren(); return; }
  const { b, a } = impact, smac = b.peaks.co_smac_1h_ppm;
  const minO2 = (r) => Math.min(...r.series.map((s) => s.o2_pct));
  const when = (s, r) => (s === null ? t('imp_never', { t: mmss(r.inputs.duration_s) }) : mmss(s));
  const out_ = (r) => (r.timeline.extinguished_s === null ? t('imp_burning') : mmss(r.timeline.extinguished_s));
  // [label, before, after, lower-is-better values (null: not ranked)]
  const rows = [
    ['imp_level', t(`lv_${b.verdict.level}`), t(`lv_${a.verdict.level}`), null],
    ['m_alarm', when(b.timeline.alarm_s, b), when(a.timeline.alarm_s, a), null],
    ['imp_out', out_(b), out_(a), [b.timeline.extinguished_s ?? Infinity, a.timeline.extinguished_s ?? Infinity]],
    ['m_hrr', `${num(b.peaks.hrr_kw, 2)} kW`, `${num(a.peaks.hrr_kw, 2)} kW`, [b.peaks.hrr_kw, a.peaks.hrr_kw]],
    ['imp_burned', `${num(b.peaks.burned_g, 1)} g`, `${num(a.peaks.burned_g, 1)} g`, [b.peaks.burned_g, a.peaks.burned_g]],
    ['imp_co', `${num(b.peaks.co_ppm, 1)} ppm`, `${num(a.peaks.co_ppm, 1)} ppm`, [b.peaks.co_ppm, a.peaks.co_ppm]],
    ['imp_smac', when(b.timeline.co_smac_s, b), when(a.timeline.co_smac_s, a), null],
    ['imp_smoke', `${num(b.peaks.smoke_mg_m3, 1)} mg/m³`, `${num(a.peaks.smoke_mg_m3, 1)} mg/m³`, [b.peaks.smoke_mg_m3, a.peaks.smoke_mg_m3]],
    ['imp_dp', `${num(b.peaks.dp_kpa, 2)} kPa`, `${num(a.peaks.dp_kpa, 2)} kPa`, [b.peaks.dp_kpa, a.peaks.dp_kpa]],
    ['imp_o2', `${num(minO2(b), 2)} %`, `${num(minO2(a), 2)} %`, [-minO2(b), -minO2(a)]],
  ];
  const table = document.createElement('table');
  const head = table.insertRow();
  for (const [k, sub] of [['imp_metric'], ['imp_before', 'imp_before_s'], ['imp_after', 'imp_after_s']]) {
    const th = document.createElement('th'); th.textContent = t(k);
    if (sub) { const s = document.createElement('small'); s.textContent = t(sub); th.append(s); }
    head.append(th);
  }
  for (const [k, bv, av, cmp] of rows) {
    const tr = table.insertRow();
    tr.insertCell().textContent = t(k, { smac: `${smac} ppm` });
    tr.insertCell().textContent = bv;
    const c = tr.insertCell(); c.textContent = av;
    if (cmp && cmp[1] < cmp[0] - 1e-9) c.className = 'better';
  }
  out.replaceChildren(table);
  const agent = a.inputs.suppression;
  note.textContent = [
    t('imp_note', { agent: t(`sup_${agent === 'water_mist' ? 'mist' : agent}`), resp: num(a.inputs.response_s, 0), dur: mmss(b.inputs.duration_s) }),
    b.flammability.flammable ? '' : t('imp_nonflam'),
  ].join(' ');
}

// the home page (For Businesses): pick a place and a fire location, compare with the model's default atmosphere,
// material and response; runs once when the section first comes into view
export function bindHomeImpact() {
  const form = $('impForm');
  if (!form) return () => {};
  let catalog = null, impact = null;
  const fillSelects = () => {
    if (!catalog) return;
    for (const [id, items] of [['impEnv', catalog.environments], ['impLoc', catalog.locations]]) {
      const sel = $(id), v = sel.value;
      sel.replaceChildren(...Object.entries(items).map(([k, x]) => new Option(label(x.label), k)));
      if (v) sel.value = v;
    }
  };
  const run = async () => {
    const sc = { environment: $('impEnv').value, location: $('impLoc').value };
    $('impOpen').href = `./lab.html#${new URLSearchParams(sc)}`;
    form.querySelector('button').disabled = true;
    try { impact = await runImpact(sc); } catch (e) { console.error(e); impact = null; $('impactNote').textContent = t('start_failed'); }
    form.querySelector('button').disabled = false;
    renderImpact($('impactOut'), $('impactNote'), impact);
  };
  form.addEventListener('submit', (e) => { e.preventDefault(); run(); });
  const io = new IntersectionObserver(async (es) => {
    if (!es.some((e) => e.isIntersecting)) return;
    io.disconnect();
    try { catalog = await api('/api/fire/catalog'); } catch (e) { console.error(e); return; }
    fillSelects();
    $('impEnv').value = 'moon'; $('impLoc').value = 'avionics_rack';      // a scenario where the flame spreads
    run();
  }, { rootMargin: '200px 0px' });
  io.observe(form);
  return () => { fillSelects(); renderImpact($('impactOut'), $('impactNote'), impact); };     // on a language change
}
