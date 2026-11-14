// Runs the teammate's original fire-spread physics (cut out of habitat_fire_sim.html independently of the
// generator) and the main simulator's module (frontend/js/spread/model.js) side by side and requires every
// field to be bit-identical after every scenario. Prints a JSON report; exit code 1 on any difference.
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const html = readFileSync(path.join(root, 'blackfox/db/knowledge/habitat_fire_sim.html'), 'utf8');
const a = html.indexOf('// ---------- Knowledge-base references ----------');
const b = html.indexOf('// ---------- Rendering ----------');
if (a < 0 || b < a) { console.log(JSON.stringify({ ok: false, error: 'markers not found in habitat_fire_sim.html' })); process.exit(1); }
const block = html.slice(a, b);
const original = new Function(`const renderLog=()=>{}, renderRooms=()=>{}, updateStatic=()=>{}, syncPlay=()=>{};\n${block}
  return { S, OPEN, kind, isOpenCell, TH, DQ, SM, reset, ignite, step, applyFlowScale, markWallAdj, solveFlow, addLog,
    arrays: { state, prog, burnT, igT, extinct, TH, DQ, SM, ux, uy, phi, inc, bz },
    scalars: () => ({ t, done, extMode, notIgnited, everIgn, maxDist, firstIgn, uMax, uScale, running }),
    logs: () => log.map((e) => [e.t, e.r, e.text]), rooms: () => JSON.stringify(roomStat), hist: () => JSON.stringify(gHist) };`);
const { createModel } = await import(pathToFileURL(path.join(root, 'frontend/js/spread/model.js')).href);

function wrap(m) {   // the module exposes the same things through its returned object
  return { S: m.S, OPEN: m.OPEN, kind: m.kind, isOpenCell: m.isOpenCell, TH: m.TH, DQ: m.DQ, SM: m.SM, reset: m.reset, ignite: m.ignite,
    step: m.step, applyFlowScale: m.applyFlowScale, markWallAdj: m.markWallAdj, solveFlow: m.solveFlow, addLog: m.addLog,
    arrays: { state: m.state, prog: m.prog, burnT: m.burnT, igT: m.igT, extinct: m.extinct, TH: m.TH, DQ: m.DQ, SM: m.SM, ux: m.ux, uy: m.uy, phi: m.phi, bz: m.bz },
    scalars: () => ({ t: m.t, done: m.done, extMode: m.extMode, notIgnited: m.notIgnited, everIgn: m.everIgn, maxDist: m.maxDist, firstIgn: m.firstIgn, uMax: m.uMax, uScale: m.uScale, running: m.running }),
    logs: () => m.log.map((e) => [e.t, e.r, e.text]), rooms: () => JSON.stringify(m.roomStat), hist: () => JSON.stringify(m.gHist) };
}

const same = (x, y) => x.length === y.length && Buffer.compare(Buffer.from(x.buffer, x.byteOffset, x.byteLength), Buffer.from(y.buffer, y.byteOffset, y.byteLength)) === 0;
// what the main simulator does on Start: same settings, all doors open, ignite at the chosen place
const IGNITE = { galley: [44, 57], crew_quarters: [20, 20], avionics_rack: [110, 42], glovebox: [88, 54] };
const scenarios = [
  { name: 'ISS-like module', S: { g: 0, o2: 21, p: 101.3, u: 20, m: 'sibal', vent: true }, at: 'galley', steps: 800 },
  { name: '0 g, fans off', S: { g: 0, o2: 21, p: 101.3, u: 0, m: 'sibal', vent: true }, at: 'galley', steps: 800 },
  { name: 'Lunar habitat (34 % O2)', S: { g: 0.165, o2: 34, p: 56.5, u: 10, m: 'sibal', vent: true }, at: 'galley', steps: 1500 },
  { name: 'Mars habitat, Nomex', S: { g: 0.378, o2: 34, p: 56.5, u: 12, m: 'nomex', vent: true }, at: 'crew_quarters', steps: 800 },
  { name: 'Earth lab, PMMA', S: { g: 1, o2: 21, p: 101.3, u: 10, m: 'pmma', vent: true }, at: 'avionics_rack', steps: 800 },
  { name: 'Gateway air, paper', S: { g: 0, o2: 26.5, p: 70.3, u: 5, m: 'paper', vent: true }, at: 'glovebox', steps: 800 },
  // the auto vent shutdown and a closed door, applied to both models at the same step
  { name: 'Moon, vent off at the alarm, hatch closed', S: { g: 0.165, o2: 30, p: 70, u: 15, m: 'sibal', vent: true }, at: 'galley', steps: 1500, ventOffAtAlarm: true, closeDoor: 'H1' },
];

const report = []; let ok = true;
for (const sc of scenarios) {
  const runs = [original(), wrap(createModel())];
  for (const m of runs) {
    Object.assign(m.S, sc.S);
    for (const o of m.OPEN) o.open = true;
    m.reset(false);
    m.ignite(...IGNITE[sc.at], true);
  }
  let ventOffAt = null;
  for (let s = 0; s < sc.steps; s++) {
    for (const m of runs) {
      if (sc.closeDoor && s === 300) {   // what a click on a door does in the original UI
        const d = m.OPEN.find((o) => o.id === sc.closeDoor); d.open = false;
        for (const k of d.cells) { m.kind[k] = 4; m.TH[k] = 0; m.DQ[k] = 0; m.SM[k] = 0; }
        m.markWallAdj(); m.solveFlow();
      }
      m.step(0.1);
    }
    if (sc.ventOffAtAlarm && ventOffAt === null && JSON.parse(runs[0].rooms()).some((r) => r.smokeT !== null)) {
      ventOffAt = runs[0].scalars().t;
      for (const m of runs) { m.S.vent = false; m.applyFlowScale(); m.addLog(-1, 'Ventilation switched off automatically at the smoke alarm'); }
    }
  }
  const diffs = [];
  for (const k of Object.keys(runs[1].arrays)) if (!same(runs[0].arrays[k], runs[1].arrays[k])) diffs.push(k);
  if (JSON.stringify(runs[0].scalars()) !== JSON.stringify(runs[1].scalars())) diffs.push('scalars');
  for (const f of ['logs', 'rooms', 'hist']) if (JSON.stringify(runs[0][f]()) !== JSON.stringify(runs[1][f]())) diffs.push(f);
  const sc0 = runs[0].scalars(), burning = runs[0].arrays.state.reduce((n, v) => n + (v >= 2), 0);
  report.push({ scenario: sc.name, sim_time_s: +sc0.t.toFixed(1), cells_ignited: sc0.everIgn, burning_or_burnt: burning,
    vent_off_at_s: ventOffAt, events: runs[0].logs().length, identical: diffs.length === 0, differences: diffs });
  if (diffs.length) ok = false;
}
// the places the main simulator ignites must be fuel in the model's geometry
const probe = createModel(); probe.reset(false);
const fuelAt = Object.fromEntries(Object.entries(IGNITE).map(([k, [i, j]]) => [k, probe.kind[j * probe.NX + i] === probe.FUEL]));
if (!Object.values(fuelAt).every(Boolean)) ok = false;
console.log(JSON.stringify({ ok, scenarios: report, ignition_points_are_fuel: fuelAt }, null, 1));
process.exit(ok ? 0 : 1);
