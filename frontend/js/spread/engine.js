// The 2D fire-spread engine of the main simulator: drives the teammate's exact physics (./model.js,
// generated from habitat_fire_sim.html) with the lab's scenario and draws it.
//
// Physics: the model always advances in its own fixed 0.1 s steps, so every device computes the same
// numbers. The device tier only decides how many of those steps fit into one frame (budgetMs) and how
// the result is drawn. When a device cannot keep up with the chosen speed, the run gets slower in
// wall-clock time instead of skipping physics.
// Drawing: the gas fields (heat, smoke, oxygen) and the solid cells are written into two 120x60 images
// once per frame and scaled up (smoothly for the gas on capable devices), and flames are pre-rendered
// sprites - instead of one fillRect per cell and one new radial gradient per burning cell per frame.
import { createModel } from './model.js';

// where the lab's fire-source locations start the fire in the two-deck habitat (all fuel cells; tested)
export const IGNITE = { galley: [44, 57], crew_quarters: [20, 20], avionics_rack: [110, 42], glovebox: [88, 54] };
const C = { hab: '#10171e', wall: '#4a5866', accent: '#86a2ff', muted: '#93a1af', ink: '#e4ebf2', crit: '#ff7b70',
  panel: '#0c0f12', line: 'rgba(255,255,255,.09)' };
const rgb = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const HAB = rgb(C.hab), WALL = rgb(C.wall), ACC = rgb(C.accent);
const fmtT = (s) => (s === null || s === undefined ? '—' : s < 60 ? `${s.toFixed(0)} s` : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function flameSprite(blue) {      // the original's three colour stops, rendered once per blueness level
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const x = c.getContext('2d'), g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, `rgba(255,${Math.round(235 - 50 * blue)},${Math.round(170 + 80 * blue)},${0.95 - 0.35 * blue})`);
  g.addColorStop(0.5, `rgba(${Math.round(255 - 170 * blue)},${Math.round(140 + 10 * blue)},${Math.round(30 + 225 * blue)},${0.55 - 0.2 * blue})`);
  g.addColorStop(1, 'rgba(0,0,0,0)');
  x.fillStyle = g; x.fillRect(0, 0, 64, 64);
  return c;
}

export class SpreadEngine {
  constructor(els) {
    this.els = els;
    this.M = createModel({ onLog: () => { this.logDirty = true; } });
    const M = this.M;
    this.q = { dpr: 1.5, smooth: true, flames: 700, budgetMs: 7, uiHz: 4, fps: 60 };
    this.speed = 16; this.acc = 0; this.started = false; this.paused = false; this.visible = false;
    this.layers = { heat: true, smoke: true, flow: false, rings: true, o2: false };
    this.gasCv = Object.assign(document.createElement('canvas'), { width: M.NX, height: M.NY });
    this.solCv = Object.assign(document.createElement('canvas'), { width: M.NX, height: M.NY });
    this.gasImg = this.gasCv.getContext('2d').createImageData(M.NX, M.NY);
    this.solImg = this.solCv.getContext('2d').createImageData(M.NX, M.NY);
    this.sprites = Array.from({ length: 6 }, (_, i) => flameSprite(i / 5));
    this.matRGB = M.MKEYS.map((k) => rgb(M.MAT[k].fill));
    this.ctx = els.canvas.getContext('2d');
    this.lastUi = 0; this.lastDraw = 0; this.achieved = 0;
    els.canvas.addEventListener('click', (e) => this.click(e));
    new ResizeObserver(() => this.resize()).observe(els.canvas);
  }

  setQuality(q) { this.q = { ...this.q, ...q }; this.resize(); }

  // ---- lifecycle --------------------------------------------------------------------------
  benchmark() {          // the full reset (geometry + 1800-iteration flow solve) on this device, in ms
    const t0 = performance.now(); this.M.reset(false); return performance.now() - t0;
  }

  preview(lining) {      // before Start: show the habitat with the chosen wall lining, no fire
    const M = this.M;
    if (this.started) return;
    M.S.m = lining; M.build(); M.markWallAdj(); M.state.fill(0); M.TH.fill(0); M.SM.fill(0); M.DQ.fill(0);
    this.draw(true); this.panels(true);
  }

  start(p) {             // p: {g, o2, p, u, lining, location, autoVent}
    const M = this.M;
    Object.assign(M.S, { g: p.g, o2: p.o2, p: p.p, u: p.u, m: p.lining, vent: true });
    for (const o of M.OPEN) o.open = true;
    M.reset(false);
    M.ignite(...(IGNITE[p.location] || IGNITE.galley), true);
    M.running = true;
    this.params = p; this.autoVent = !!p.autoVent; this.ventOffAt = null;
    this.acc = 0; this.started = true; this.paused = false; this.finishedSent = false; this.achieved = 0;
    this.draw(true); this.panels(true);
  }

  restart() { if (this.params) this.start(this.params); }

  get finished() { const M = this.M; return this.started && (M.done || !M.running); }

  // one animation frame: advance the physics within this device's time budget
  tick(dtWall) {
    const M = this.M;
    if (!this.started || this.paused || !M.running) { this.achieved = 0; return; }
    this.acc += dtWall * this.speed;
    const t0 = performance.now(); let n = 0;
    while (this.acc >= 0.1 && performance.now() - t0 < this.q.budgetMs) {
      M.step(0.1); this.acc -= 0.1; n++;
      this.autoVentCheck();
      if (!M.running) break;
    }
    if (this.acc > 1) this.acc %= 0.1;           // cannot keep up: run slower, never skip physics
    const now = dtWall > 0 ? (n * 0.1) / dtWall : 0;
    this.achieved = this.achieved ? this.achieved * 0.9 + now * 0.1 : now;
  }

  // the lab's "automatic ventilation shutdown": the crew switches the fans off at the first smoke
  // alarm - the same operation as the original page's Ventilation off button, at that step
  autoVentCheck() {
    const M = this.M;
    if (!this.autoVent || this.ventOffAt !== null || !M.S.vent) return;
    if (M.roomStat.some((r) => r.smokeT !== null)) {
      M.S.vent = false; M.applyFlowScale();
      M.addLog(-1, 'Ventilation switched off automatically at the smoke alarm');
      this.ventOffAt = M.t;
    }
  }

  toggleVent() {
    const M = this.M; M.S.vent = !M.S.vent; M.applyFlowScale();
    M.addLog(-1, M.S.vent ? 'Ventilation switched on' : 'Ventilation switched off');
  }

  // a click on the habitat: toggle a door or hatch, or light a furnishing (the original's rules)
  click(e) {
    const M = this.M;
    if (!this.started) return;
    const cv = this.els.canvas, r = cv.getBoundingClientRect();
    const fi = (e.clientX - r.left) / r.width * M.NX, fj = (e.clientY - r.top) / r.height * M.NY;
    let hit = null, hd = 2.2;
    for (const o of M.OPEN) for (const k of o.cells) { const d = Math.hypot((k % M.NX) + 0.5 - fi, ((k / M.NX) | 0) + 0.5 - fj); if (d < hd) { hd = d; hit = o; } }
    if (hit) {
      hit.open = !hit.open;
      for (const k of hit.cells) { if (hit.open) M.kind[k] = M.AIR; else { M.kind[k] = M.WALL; M.TH[k] = 0; M.DQ[k] = 0; M.SM[k] = 0; } }
      M.markWallAdj(); M.solveFlow(); M.addLog(-1, `${hit.name} ${hit.open ? 'opened' : 'closed'}`);
      return;
    }
    const i = Math.floor(fi), j = Math.floor(fj);
    let best = null, bd = 10;
    for (let dj = -3; dj <= 3; dj++) for (let di = -3; di <= 3; di++) {
      const ii = i + di, jj = j + dj; if (ii < 1 || jj < 1 || ii >= M.NX - 1 || jj >= M.NY - 1) continue;
      const k = M.idx(ii, jj); if (M.kind[k] === M.FUEL && M.state[k] < 2) { const d = di * di + dj * dj; if (d < bd) { bd = d; best = [ii, jj]; } }
    }
    if (best) { M.ignite(best[0], best[1]); M.running = true; this.paused = false; }
  }

  // ---- what gets saved for the session and read by the SI ----------------------------------
  summary() {
    const M = this.M;
    let burning = 0, burnt = 0, tmax = M.T0, ymin = M.S.o2;
    for (let k = 0; k < M.N; k++) {
      if (M.state[k] === 2) burning++; else if (M.state[k] === 3) burnt++;
      if (M.kind[k] !== M.WALL) { if (M.TH[k] + M.T0 > tmax) tmax = M.TH[k] + M.T0; const y = M.S.o2 - M.DQ[k]; if (y < ymin) ymin = y; }
    }
    const alarms = M.roomStat.map((s) => s.smokeT).filter((v) => v !== null);
    const status = !this.started ? 'not_started' : M.notIgnited ? 'did_not_ignite' : M.done ? (M.extMode ? 'went_out' : 'burnt_out')
      : !M.running ? 'time_limit' : 'running';
    const r1 = (v) => (v === null || v === undefined ? null : Math.round(v * 10) / 10);
    return {
      status, sim_time_s: r1(M.t), extinction_cause: M.extMode, lining: M.S.m,
      rooms_reached: M.roomStat.filter((s) => s.fireT !== null).length,
      first_alarm_s: alarms.length ? r1(Math.min(...alarms)) : null,
      area_burning_cm2: burning * M.DX * M.DX, area_burned_cm2: burnt * M.DX * M.DX,
      hottest_gas_c: Math.round(tmax - 273), lowest_o2_pct: r1(ymin), vent_off_s: r1(this.ventOffAt),
      ignitions: M.igns.length, doors_closed: M.OPEN.filter((o) => !o.open).map((o) => o.id),
      rooms: M.ROOMS.map((r, i) => {
        const s = M.roomStat[i] || { fireT: null, smokeT: null, tmax: M.T0, ymin: M.S.o2 };   // before the first Start
        return { room: r.id, fire_s: r1(s.fireT), smoke_s: r1(s.smokeT), max_gas_c: Math.round(s.tmax - 273), min_o2_pct: r1(s.ymin) };
      }),
    };
  }

  // ---- drawing -----------------------------------------------------------------------------
  resize() {
    const cv = this.els.canvas, w = cv.clientWidth || 600, dpr = Math.min(this.q.dpr, window.devicePixelRatio || 1);
    cv.width = Math.max(10, Math.round(w * dpr)); cv.height = Math.max(10, Math.round(w / 2 * dpr));
    for (const [c, ar] of [[this.els.map, 1.6], [this.els.growth, 3.2]]) {
      if (!c) continue; const cw = c.clientWidth || 300;
      c.width = Math.max(10, Math.round(cw * dpr)); c.height = Math.max(10, Math.round(cw / ar * dpr));
    }
    this.draw(true); this.panels(true);
  }

  frame(now, dtWall) {           // called by the page every animation frame
    this.tick(dtWall);
    if (!this.visible) return;
    if (now - this.lastDraw >= 1000 / this.q.fps - 2) { this.lastDraw = now; this.draw(); }
    if (now - this.lastUi >= 1000 / this.q.uiHz) { this.lastUi = now; this.panels(); }
  }

  fields() {
    const M = this.M, N = M.N, g = this.gasImg.data, s = this.solImg.data, L = this.layers;
    for (let k = 0; k < N; k++) {
      const p = k * 4;
      // gas: hot gas, smoke, oxygen depletion composited "over" transparent, as the original layers them
      let r = 0, gg = 0, b = 0, a = 0;
      if (M.kind[k] !== M.WALL) {
        const over = (cr, cg, cb, ca) => { const na = ca + a * (1 - ca); if (na > 0) { r = (cr * ca + r * a * (1 - ca)) / na; gg = (cg * ca + gg * a * (1 - ca)) / na; b = (cb * ca + b * a * (1 - ca)) / na; } a = na; };
        const th = M.TH[k];
        if (L.heat && th > 15) over(th > 350 ? 255 : 235, Math.round(150 - 90 * Math.min(1, th / 600)), 40, Math.min(0.7, th / 700));
        if (L.smoke && M.SM[k] > 0.004) over(105, 105, 112, Math.min(0.6, M.SM[k] / 0.3));
        if (L.o2 && M.DQ[k] > 0.05) over(47, 111, 214, Math.min(0.6, M.DQ[k] / 6));
      }
      g[p] = r; g[p + 1] = gg; g[p + 2] = b; g[p + 3] = a * 255;
      // solids: walls, closed doors, fuel by state (burning cells are drawn as flames instead)
      let c = null;
      if (M.kind[k] === M.WALL) c = M.isOpenCell[k] ? ACC : WALL;
      else if (M.kind[k] === M.FUEL) {
        const st = M.state[k];
        if (st === 1) { const q = Math.min(1, M.prog[k]); c = [200 + 55 * q, 170 - 70 * q, 120 - 90 * q]; }
        else if (st === 3) {
          if (M.extinct[k] === 1) c = [0x6b, 0x5e, 0x52];
          else { const e = 1 - Math.min(1, Math.max(0, (M.t - M.igT[k] - 15) / 60)); c = [43 + 150 * e, 38 + 40 * e, 34 - 10 * e]; }
        } else if (st === 0) c = this.matRGB[M.mat[k]];
      }
      if (c) { s[p] = c[0]; s[p + 1] = c[1]; s[p + 2] = c[2]; s[p + 3] = 255; } else s[p + 3] = 0;
    }
    this.gasCv.getContext('2d').putImageData(this.gasImg, 0, 0);
    this.solCv.getContext('2d').putImageData(this.solImg, 0, 0);
  }

  draw(force) {
    if (!this.visible && !force) return;
    const M = this.M, x = this.ctx, cv = this.els.canvas, W = cv.width, H = cv.height, cs = W / M.NX, ub = M.Ub();
    this.fields();
    x.setTransform(1, 0, 0, 1, 0, 0);
    x.fillStyle = C.hab; x.fillRect(0, 0, W, H);
    x.imageSmoothingEnabled = this.q.smooth; x.imageSmoothingQuality = 'high';
    x.drawImage(this.gasCv, 0, 0, W, H);
    x.imageSmoothingEnabled = false;
    x.drawImage(this.solCv, 0, 0, W, H);
    // open doors and hatches: dashed outline
    x.strokeStyle = 'rgba(74,88,102,.9)'; x.setLineDash([cs * 0.6, cs * 0.6]); x.lineWidth = Math.max(1, cs * 0.15);
    for (const o of M.OPEN) {
      if (!o.open) continue;
      let i0 = 1e9, i1 = -1, j0 = 1e9, j1 = -1;
      for (const k of o.cells) { const i = k % M.NX, j = (k / M.NX) | 0; if (i < i0) i0 = i; if (i > i1) i1 = i; if (j < j0) j0 = j; if (j > j1) j1 = j; }
      x.strokeRect(i0 * cs + 0.5, j0 * cs + 0.5, (i1 + 1 - i0) * cs - 1, (j1 + 1 - j0) * cs - 1);
    }
    x.setLineDash([]);
    x.fillStyle = M.S.vent && M.S.u > 0 ? C.accent : C.muted;            // supply and return grilles
    x.fillRect(0, 3 * cs, cs, 8 * cs); x.fillRect(W - cs, 50 * cs, cs, 8 * cs);
    if (this.layers.rings && M.igns.length) this.rings(cs);
    this.flames(cs, ub);
    if (this.layers.flow) this.arrows(cs);
    x.strokeStyle = C.ink; x.lineWidth = Math.max(1, cs * 0.2);
    for (const [i, j] of M.igns) { const px = (i + 0.5) * cs, py = (j + 0.5) * cs, r = cs * 0.9; x.beginPath(); x.moveTo(px - r, py - r); x.lineTo(px + r, py + r); x.moveTo(px + r, py - r); x.lineTo(px - r, py + r); x.stroke(); }
    x.font = `600 ${Math.max(10, cs * 1.7)}px system-ui, sans-serif`; x.textAlign = 'left';
    M.ROOMS.forEach((r, ri) => {
      const st = M.roomStat[ri], px = (r.x0 + 1.3) * cs, py = (r.y1 - 0.6) * cs;
      x.fillStyle = r.c; x.fillRect(px, py - cs * 1.3, cs * 0.9, cs * 0.9);
      x.fillStyle = C.ink; x.fillText(r.name, px + cs * 1.4, py - cs * 0.4);
      if (st && st.burning > 0) { x.fillStyle = C.crit; x.fillText('● fire', px + cs * 1.4 + x.measureText(r.name + ' ').width, py - cs * 0.4); }
    });
    x.font = `${Math.max(9, cs * 1.5)}px ui-monospace, monospace`; x.fillStyle = C.muted; x.textAlign = 'right';
    x.fillText(M.S.g > 0 ? `g ↓ ${M.S.g.toFixed(3)}` : '0 g', W - cs * 2, cs * 2.8);
    x.textAlign = 'left'; x.fillText('supply →', cs * 1.6, cs * 2.4);
    x.textAlign = 'right'; x.fillText('→ return', W - cs * 1.6, 49 * cs);
  }

  rings(cs) {                     // flame-front isochrones, as in the original
    const M = this.M, x = this.ctx, span = Math.max(10, M.t);
    let dT = 300; for (const d of [5, 10, 15, 20, 30, 60, 120, 300]) if (span / d <= 10) { dT = d; break; }
    x.strokeStyle = 'rgba(134,162,255,.95)'; x.lineWidth = Math.max(1, cs * 0.18); x.beginPath();
    for (let j = 1; j < M.NY - 1; j++) for (let i = 1; i < M.NX - 1; i++) {
      const k = j * M.NX + i, a = M.igT[k]; if (a < 0) continue; const b = Math.floor(a / dT);
      const r = M.igT[k + 1], d = M.igT[k + M.NX];
      if (r >= 0 && Math.floor(r / dT) !== b) { x.moveTo((i + 1) * cs, j * cs); x.lineTo((i + 1) * cs, (j + 1) * cs); }
      if (d >= 0 && Math.floor(d / dT) !== b) { x.moveTo(i * cs, (j + 1) * cs); x.lineTo((i + 1) * cs, (j + 1) * cs); }
    }
    x.stroke();
  }

  flames(cs, ub) {                // stretched along local flow + buoyancy, bluer and rounder in weak flow
    const M = this.M, x = this.ctx, list = [];
    for (let k = 0; k < M.N; k++) if (M.state[k] === 2) list.push(k);
    if (!list.length) return;
    const stride = Math.max(1, Math.ceil(list.length / this.q.flames)), grow = Math.sqrt(stride);
    x.globalCompositeOperation = 'lighter';
    for (let n = 0; n < list.length; n += stride) {
      const k = list[n], i = k % M.NX, j = (k / M.NX) | 0;
      const wx = M.ux[k], wy = M.uy[k] - ub, U = Math.hypot(wx, wy), blue = 1 - Math.min(1, U / 25), stretch = Math.min(3, 0.7 + U / 10);
      const r = cs * 1.5 * (0.8 + Math.random() * 0.4) * grow;
      let cos = 1, sin = 0, sx = 1, off = 0;
      if (U > 0.5) { const a = Math.atan2(wy, wx); cos = Math.cos(a); sin = Math.sin(a); sx = stretch; off = r * 0.45 * (stretch - 0.7); }
      const cx = (i + 0.5) * cs + cos * off, cy = (j + 0.5) * cs + sin * off;
      x.setTransform(cos * sx, sin * sx, -sin, cos, cx, cy);
      x.drawImage(this.sprites[Math.round(blue * 5)], -r, -r, 2 * r, 2 * r);
    }
    x.setTransform(1, 0, 0, 1, 0, 0);
    x.globalCompositeOperation = 'source-over';
  }

  arrows(cs) {
    const M = this.M, x = this.ctx;
    x.strokeStyle = 'rgba(134,162,255,.8)'; x.lineWidth = Math.max(1, cs * 0.12); x.beginPath();
    for (let j = 3; j < M.NY - 1; j += 5) for (let i = 3; i < M.NX - 1; i += 5) {
      const k = M.idx(i, j); if (!M.fluid(k)) continue;
      const vx = M.ux[k], vy = M.uy[k] + M.bz[k], v = Math.hypot(vx, vy); if (v < 0.2) continue;
      const L = cs * Math.min(4, 0.8 + Math.log1p(v) * 0.9), px = (i + 0.5) * cs, py = (j + 0.5) * cs, a = Math.atan2(vy, vx);
      const ex = px + Math.cos(a) * L, ey = py + Math.sin(a) * L;
      x.moveTo(px, py); x.lineTo(ex, ey);
      x.lineTo(ex - Math.cos(a - 0.5) * cs * 0.8, ey - Math.sin(a - 0.5) * cs * 0.8);
      x.moveTo(ex, ey); x.lineTo(ex - Math.cos(a + 0.5) * cs * 0.8, ey - Math.sin(a + 0.5) * cs * 0.8);
    }
    x.stroke();
  }

  // ---- panels: status, tiles, rooms, events, growth chart, flammability map -----------------
  panels(force) {
    if (!this.visible && !force) return;
    const M = this.M, e = this.els, sm = this.summary();
    if (e.clock) e.clock.textContent = `${M.t.toFixed(1)} s`;
    if (e.speedOut) e.speedOut.textContent = this.started && !this.paused && M.running ? `×${Math.round(this.achieved)}` : '';
    if (e.status) {
      const nb = sm.area_burning_cm2 / (M.DX * M.DX), on = M.roomStat.filter((s) => s.burning > 0).length;
      const [txt, cls] = !this.started ? ['Press Start', 'idle'] : nb > 0 ? [`Burning in ${on} room${on > 1 ? 's' : ''}`, 'burn']
        : M.notIgnited ? [`Did not ignite: ${M.WHY[M.extMode || 'oxygen']}`, 'out'] : M.done ? [M.extMode ? `Went out: ${M.WHY[M.extMode]}` : 'Burnt out', 'out'] : ['Smouldering', 'warn'];
      e.status.textContent = txt; e.status.className = `sp-pill ${cls}`;
    }
    if (e.tiles) {
      const m = M.MAT[M.S.m], U0 = M.firstIgn !== null ? M.UeffAt(M.firstIgn) : Math.hypot(M.S.vent ? M.S.u : 0, M.Ub()), mg = M.S.o2 - M.limit(m.con, U0);
      const tiles = [['Rooms reached', `${sm.rooms_reached} / ${M.ROOMS.length}`], ['Area burning', `${sm.area_burning_cm2.toLocaleString()} cm²`],
        ['Area burned', `${sm.area_burned_cm2.toLocaleString()} cm²`], ['Hottest gas', `${sm.hottest_gas_c} °C`], ['Lowest O₂', `${sm.lowest_o2_pct} %`],
        ['First smoke alarm', fmtT(sm.first_alarm_s)], ['Lining O₂ margin', `${mg >= 0 ? '+' : ''}${mg.toFixed(1)} pts`]];
      e.tiles.innerHTML = tiles.map(([k, v]) => `<div class="sp-tile"><span>${k}</span><b>${v}</b></div>`).join('');
    }
    if (e.rooms) {
      e.rooms.innerHTML = M.ROOMS.map((r, i) => {
        const s = M.roomStat[i] || {}, [lab, col] = s.burning > 0 ? ['Fire', C.crit] : s.fireT !== null && s.fireT !== undefined ? ['Burnt out', C.muted]
          : s.smokeT !== null && s.smokeT !== undefined ? ['Smoke', '#e8a53c'] : ['Clear', '#4cc28a'];
        return `<div class="sp-room" style="border-left-color:${r.c}"><b>${esc(r.name)}</b><i style="color:${col}">${lab}</i>
          <small>fire ${fmtT(s.fireT)} · alarm ${fmtT(s.smokeT)} · ${s.tmax ? Math.round(s.tmax - 273) : '—'} °C · O₂ ${s.ymin !== undefined ? s.ymin.toFixed(1) : '—'} %</small></div>`;
      }).join('');
    }
    if (e.log && (this.logDirty || force)) {
      this.logDirty = false;
      e.log.innerHTML = M.log.length ? M.log.slice(0, 40).map((x) => `<li><time>${fmtT(x.t)}</time><i style="background:${x.r >= 0 ? M.ROOMS[x.r].c : C.muted}"></i><span>${esc(x.text)}</span></li>`).join('')
        : `<li><time>—</time><i></i><span>${this.started ? 'No events yet.' : 'Set up the scenario, then press Start.'}</span></li>`;
    }
    this.growth(); this.map();
  }

  growth() {
    const c = this.els.growth; if (!c) return;
    const M = this.M, x = c.getContext('2d'), W = c.width, H = c.height, d = W / (c.clientWidth || W);
    x.fillStyle = C.panel; x.fillRect(0, 0, W, H);
    const L = 46 * d, R = 8 * d, T = 8 * d, B = 18 * d, unit = M.DX * M.DX;
    let top = 4; for (const h of M.gHist) for (let r = 1; r < h.length; r++) if (h[r] > top) top = h[r];
    const tmax = Math.max(60, M.t), ymax = top * unit * 1.15, X = (v) => L + (W - L - R) * v / tmax, Y = (v) => T + (H - T - B) * (1 - v / ymax);
    x.font = `${10 * d}px ui-monospace, monospace`; x.strokeStyle = C.line; x.lineWidth = 1; x.fillStyle = C.muted;
    for (let q = 0; q <= 2; q++) { const v = top * unit * q / 2; x.beginPath(); x.moveTo(L, Y(v)); x.lineTo(W - R, Y(v)); x.stroke(); x.textAlign = 'right'; x.fillText(Math.round(v).toLocaleString(), L - 5 * d, Y(v) + 3 * d); }
    x.textAlign = 'center'; for (let q = 0; q <= 4; q++) { const v = tmax * q / 4; x.fillText(`${Math.round(v)} s`, X(v), H - 4 * d); }
    M.ROOMS.forEach((r, ri) => {
      if (M.gHist.length < 2 || !M.gHist.some((h) => h[ri + 1] > 0)) return;
      x.beginPath(); M.gHist.forEach((h, n) => { const px = X(h[0]), py = Y(h[ri + 1] * unit); n ? x.lineTo(px, py) : x.moveTo(px, py); });
      x.strokeStyle = r.c; x.lineWidth = 2 * d; x.stroke();
    });
  }

  map() {                         // oxygen vs effective flow: where the wall lining burns
    const c = this.els.map; if (!c) return;
    const M = this.M, x = c.getContext('2d'), W = c.width, H = c.height, d = W / (c.clientWidth || W), m = M.MAT[M.S.m];
    if (this.els.mapMat) this.els.mapMat.textContent = m.name;
    const L = 40 * d, R = 10 * d, T = 10 * d, B = 30 * d, umax = 50, ymin = 10, ymax = 40;
    const X = (u) => L + (W - L - R) * u / umax, Y = (o) => T + (H - T - B) * (1 - (o - ymin) / (ymax - ymin));
    x.fillStyle = C.panel; x.fillRect(0, 0, W, H);
    x.font = `${10 * d}px ui-monospace, monospace`; x.fillStyle = C.muted; x.strokeStyle = C.line; x.lineWidth = 1;
    for (let o = 10; o <= 40; o += 10) { x.beginPath(); x.moveTo(L, Y(o)); x.lineTo(W - R, Y(o)); x.stroke(); x.textAlign = 'right'; x.fillText(`${o}%`, L - 5 * d, Y(o) + 4 * d); }
    x.textAlign = 'center'; for (let u = 0; u <= 50; u += 10) x.fillText(u, X(u), H - B + 14 * d);
    x.fillText('effective flow, cm/s', L + (W - L - R) / 2, H - 3 * d);
    x.fillStyle = 'rgba(134,162,255,.14)'; x.fillRect(X(0.2), Y(22.2), X(40) - X(0.2), Y(15) - Y(22.2));
    const curve = (cc, col) => { x.beginPath(); let first = true; for (let u = 0.5; u <= umax; u += 0.5) { const o = Math.min(ymax + 5, M.limit(cc, u)); first ? x.moveTo(X(u), Y(o)) : x.lineTo(X(u), Y(o)); first = false; } x.strokeStyle = col; x.lineWidth = 2 * d; x.stroke(); };
    x.save(); x.beginPath(); x.rect(L, T, W - L - R, H - T - B); x.clip(); curve(m.con, C.crit); curve(m.opp, '#e8a53c'); x.restore();
    const U = Math.min(umax, M.firstIgn !== null ? M.UeffAt(M.firstIgn) : Math.hypot(M.S.vent ? M.S.u : 0, M.Ub())), o = Math.max(ymin, Math.min(ymax, M.S.o2));
    x.fillStyle = C.ink; x.beginPath(); x.arc(X(U), Y(o), 5 * d, 0, Math.PI * 2); x.fill();
  }
}
