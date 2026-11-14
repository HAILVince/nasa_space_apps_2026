// Runs frontend/js/cfd/worker.js in Node with both copied solvers, the way the page drives it, and
// prints what came back. Usage: node cfd_worker_check.mjs <solver file> <item index> <seconds> '<cfg json>'
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'frontend', 'js', 'cfd');
const [solver, item, secs, cfgJson] = process.argv.slice(2);
const itemArg = /^\d+$/.test(item) ? Number(item) : item;
const msgs = [];
const ctx = { console, Date, Math, Float32Array, Float64Array, Uint8Array, Int8Array, Int32Array, Uint32Array, Array, Object, JSON, Number, Set, Map, Infinity, isFinite,
  setTimeout, clearTimeout, postMessage: (m) => msgs.push(m) };
ctx.importScripts = (p) => vm.runInContext(readFileSync(path.join(dir, p), 'utf8'), ctx);
vm.createContext(ctx);
vm.runInContext(readFileSync(path.join(dir, 'worker.js'), 'utf8'), ctx);
ctx.onmessage({ data: { cmd: 'init', solver, cfg: JSON.parse(cfgJson), item: itemArg, speed: 64, budget: 40, endT: Number(secs) } });
const t0 = Date.now();
await new Promise((res) => { const w = () => (msgs.some((m) => m.type === 'end') || Date.now() - t0 > 240000 ? res() : setTimeout(w, 50)); w(); });
const geom = msgs.find((m) => m.type === 'geom'), frames = msgs.filter((m) => m.type === 'frame'), last = frames.at(-1);
const flame = last.stats.reduce((a, r) => a + r.flame, 0), burnt = last.stats.reduce((a, r) => a + r.burnt, 0);
console.log(JSON.stringify({ solver, grid: [geom.info.nx, geom.info.ny, geom.info.nz], dim: geom.info.DIM || 3, rooms: geom.ROOMS.map((r) => r.short),
  item: (geom.ITEMS[msgs.find((m) => m.type === 'ignited').item] || {}).name, built_ms: msgs.find((m) => m.type === 'built').ms, ignited: msgs.find((m) => m.type === 'ignited').ok,
  sim_t: +last.t.toFixed(1), wall_s: (Date.now() - t0) / 1000, frames: frames.length, flame_cells: flame, burnt_cells: burnt,
  hottest_C: Math.round(Math.max(...last.stats.map((r) => r.Tmax)) - 273), rooms_with_smoke: last.stats.filter((r) => r.ext >= 0.1).length,
  field_lengths_ok: last.T.length === geom.info.N && last.fst.length === geom.info.N }));
process.exit(0);
