// Runs one of the teammate's CFD fire solvers off the page thread and streams frames to the page.
// It steps the solver exactly like the teammate's own page does: 0.25 s steps toward a wall-clock
// target (simulated seconds = wall seconds x speed), within a time budget per slice so messages keep
// flowing. The device tier only sets that budget and the grid the page asked for; the solver code is
// the teammate's file, copied unchanged (scripts/make_cfd_solvers.py).
/* global importScripts, createSolver */
let S = null, running = false, speed = 8, budget = 45, wallLast = 0, simTarget = 0, achieved = 0, lastPost = 0;
let endT = 1800, ended = false;

function geom() {
  postMessage({
    type: 'geom', info: S.info, typeArr: S.type.slice(), openId: S.openId.slice(), mat: S.mat.slice(), room: S.room.slice(),
    sup: S.sup.slice(), ret: S.ret.slice(), fuelList: S.fuelList.slice(), sclass: S.sclass ? S.sclass.slice() : null,
    ROOMS: S.ROOMS.map((r) => ({ id: r.id, name: r.name, short: r.short || r.name })),
    ITEMS: S.ITEMS.map((it) => ({ id: it.id || it.name, name: it.name, room: it.room, m: it.m })),
    MKEYS: S.MKEYS, MATN: S.MKEYS.map((k) => S.MAT[k].name),
    OPEN: S.OPEN.map((o) => ({ id: o.id, name: o.name, open: o.open })), P: { ...S.P },
  });
}

function frame() {
  const T = Float32Array.from(S.T), YS = Float32Array.from(S.YS), YO = Float32Array.from(S.YO), fst = S.fst.slice();
  postMessage({ type: 'frame', t: S.t, achieved, running, ended, stats: S.stats(), ext: S.extMode, igns: S.igns.length,
    opens: S.OPEN.map((o) => o.open), vent: S.P.vent, T, YS, YO, fst }, [T.buffer, YS.buffer, YO.buffer, fst.buffer]);
}

// the item's fuel cells (the spacecraft solver lists them; the habitat solver only counts them)
function itemCells(i) {
  const it = S.ITEMS[i];
  if (Array.isArray(it.cells)) return it.cells;
  const I = S.info, mi = S.MKEYS.indexOf(it.m), out = [];
  for (const k of S.fuelList) {
    if (S.mat[k] !== mi) continue;
    const ii = k % I.nx, j = Math.floor(k / I.nx) % I.ny, l = Math.floor(k / (I.nx * I.ny));
    const x = (ii - 0.5) * I.h, y = (j - 0.5) * I.h, z = (l - 0.5) * I.h;
    if (x >= it.x[0] - I.h && x <= it.x[1] + I.h && y >= it.y[0] - I.h && y <= it.y[1] + I.h
        && (I.DIM === 2 || (z >= it.z[0] - I.h && z <= it.z[1] + I.h))) out.push(k);
  }
  return out;
}

function igniteItem(i) {
  if (S.igniteItem) return S.igniteItem(i, 'flame');
  const cells = itemCells(i);
  if (!cells.length) return false;
  // light the cell nearest the item's centre, as a click on it does in the teammate's page
  const I = S.info, it = S.ITEMS[i], cxm = (it.x[0] + it.x[1]) / 2, cym = (it.y[0] + it.y[1]) / 2;
  let best = cells[0], bd = Infinity;
  for (const k of cells) {
    const x = ((k % I.nx) - 0.5) * I.h, y = ((Math.floor(k / I.nx) % I.ny) - 0.5) * I.h, d = (x - cxm) ** 2 + (y - cym) ** 2;
    if (d < bd) { bd = d; best = k; }
  }
  return S.ignite(best);
}

function tick() {
  if (!S) { setTimeout(tick, 50); return; }
  const now = Date.now(), el = Math.min(0.25, (now - wallLast) / 1000); wallLast = now;
  if (running && !ended) {
    simTarget += el * speed; const t0 = S.t, start = Date.now();
    while (S.t < simTarget && Date.now() - start < budget) S.step(0.25);
    if (S.t < simTarget - 2) simTarget = S.t;              // cannot keep up: run slower, never skip physics
    achieved = 0.8 * achieved + 0.2 * ((S.t - t0) / Math.max(el, 1e-3));
    if (S.t >= endT) { ended = true; running = false; }
  }
  if (now - lastPost > 140 || ended) { frame(); lastPost = now; if (ended) postMessage({ type: 'end', t: S.t }); }
  if (!ended) setTimeout(tick, running ? 0 : 60);
}

onmessage = (e) => {
  const m = e.data;
  if (m.cmd === 'init') {
    importScripts(m.solver);
    const t0 = Date.now();
    S = createSolver(Object.assign({ iters: 24 }, m.cfg));
    budget = m.budget || 45; speed = m.speed || 8; endT = m.endT || 1800;
    postMessage({ type: 'built', ms: Date.now() - t0 });
    geom();
    // the furnishing is named, not numbered, so a reordered item list in the solver cannot light the wrong one
    const item = typeof m.item === 'number' ? m.item : S.ITEMS.findIndex((it) => it.id === m.item || it.name === m.item);
    const ok = item >= 0 ? igniteItem(item) : false;
    postMessage({ type: 'ignited', ok, item });
    running = true; wallLast = Date.now(); simTarget = S.t;
    frame(); tick();
  } else if (m.cmd === 'run') { running = m.running && !ended; simTarget = S ? S.t : 0; wallLast = Date.now(); if (running) tick(); }
  else if (m.cmd === 'speed') { speed = m.speed; }
  else if (m.cmd === 'budget') { budget = m.budget; }
  else if (m.cmd === 'vent') { S.setParams({ vent: m.vent }); }             // the same call as the teammate's vent switch
  else if (m.cmd === 'toggle') { S.toggleOpening(m.oi); geom(); frame(); }
};
