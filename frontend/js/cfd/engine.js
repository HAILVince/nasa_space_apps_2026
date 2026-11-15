// The realistic (CFD) engine of the main simulator: runs the teammate's Navier-Stokes fire solvers
// (copied unchanged into ./solver_*.js) in a Web Worker and shows them in 3D with the site's own
// three.js - in the style of the teammate's pages: interior structure, furnishings coloured by state,
// hot gas and smoke as point clouds - or as a vertical section on light devices.
//
// The device tier picks the grid (and 2D section or full 3D for the habitat). Unlike the 2D spread
// model, a finer CFD grid gives more accurate numbers, so the grid is saved with every run.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export const MODELS = {
  habitat: {
    solver: 'solver_habitat.js', label: { en: 'Two-deck habitat' },
    // lab fire source -> the furnishing lit in this geometry
    items: { galley: 'food packaging', crew_quarters: 'sleeping bag', avionics_rack: 'rack fabric', glovebox: 'paperwork' },
    grid: { low: { dim: 2, h: 0.1 }, medium: { dim: 3, h: 0.2 }, high: { dim: 3, h: 0.125 } },
  },
  living: {
    solver: 'solver_living.js', label: { en: 'Surface habitat with living quarters' },
    items: { galley: 'food packaging', crew_quarters: 'sleeping bag', avionics_rack: 'rack wire harness', glovebox: 'checklists' },
    grid: { low: { dim: 2, h: 0.1 }, medium: { dim: 3, h: 0.2 }, high: { dim: 3, h: 0.125 } },
  },
  spacecraft: {
    solver: 'solver_spacecraft.js', label: { en: 'Spacecraft (ISS-like)' },
    items: { avionics_rack: 'L1', glovebox: 'L6', galley: 'N4', crew_quarters: 'N1' },
    grid: { low: { h: 0.3 }, medium: { h: 0.25 }, high: { h: 0.15 } },
  },
};
const BUDGET = { low: 20, medium: 35, high: 45 };          // ms of solver work per worker slice
const MATCOL = { sibal: '#c9b48a', pmma: '#9fc3d6', paper: '#e2d7c0', nomex: '#b6a7c9', pe: '#d9d4c0', ptfe: '#e9ece9', kapton: '#c98a2b',
  silicone: '#9aa3ad', pc: '#a9c7d8', pu: '#d8c27a', nylon: '#cdd5df', cotton: '#e6e1d3' };
const fmtT = (s) => (s === null || s === undefined ? '—' : s < 60 ? `${s.toFixed(0)} s` : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const pointVS = `attribute vec3 aColor; attribute float aAlpha; varying vec3 vC; varying float vA; uniform float uSize; uniform float uScale;
void main(){ vC=aColor; vA=aAlpha; vec4 mv=modelViewMatrix*vec4(position,1.0); gl_PointSize=uSize*uScale/max(0.1,-mv.z); gl_Position=projectionMatrix*mv; }`;
const pointFS = `varying vec3 vC; varying float vA; void main(){ vec2 d=gl_PointCoord-0.5; float r=dot(d,d)*4.0; if(r>1.0||vA<0.004) discard; gl_FragColor=vec4(vC, vA*(1.0-r)); }`;
function heatColor(T) { const x = Math.min(1, Math.max(0, (T - 330) / 1100)); return [Math.min(1, 0.6 + x * 0.8), Math.min(1, 0.15 + x * 0.9 * x + 0.1), Math.max(0, 0.05 + (x - 0.75) * 1.6)]; }

export class CFDEngine {
  constructor(els) {
    this.els = els; this.worker = null; this.G = null; this.F = null; this.visible = false; this.mode = '3d';
    this.tier = 'medium'; this.model = 'habitat'; this.speed = 8; this.paused = false; this.started = false;
    this.renderer = null; this.dirty = false; this.lastUi = 0;
    els.canvas3d.addEventListener('pointerdown', () => { this.dirty = true; });
  }

  gridFor(model, tier) { return MODELS[model].grid[tier] || MODELS[model].grid.medium; }

  start(p, model, tier) {         // p: {g, X, Pk, U, lining, location, autoVent}
    this.stop();
    this.model = model; this.tier = tier; this.params = p;
    const M = MODELS[model], grid = this.gridFor(model, tier);
    this.track = { fire: {}, smoke: {}, Tmax: {}, Xmin: {}, vis: {}, peakHrr: 0, ventOffAt: null, everFlame: false, quietSince: null };
    this.G = null; this.F = null; this.started = true; this.paused = false; this.finished = false; this.finishedSent = false; this.builtMs = null;
    const can3d = (grid.dim || 3) === 3;        // the habitat's 2D grid is one cell deep: only a section makes sense
    this.mode = !can3d ? 'section' : this.userMode || (tier === 'low' ? 'section' : '3d');
    this.worker = new Worker(new URL('./worker.js', import.meta.url));
    this.worker.onmessage = (e) => this.onMessage(e.data);
    this.worker.postMessage({ cmd: 'init', solver: `./${M.solver}`, item: M.items[p.location] || Object.values(M.items)[0],
      cfg: { ...grid, g: p.g, X: p.X, Pk: p.Pk, U: p.U, vent: true, lining: p.lining }, speed: this.speed, budget: BUDGET[tier] || 35, endT: 900 });
    this.panels(true);
  }

  stop() { if (this.worker) { this.worker.terminate(); this.worker = null; } }

  setSpeed(s) { this.speed = s; this.worker?.postMessage({ cmd: 'speed', speed: s }); }
  setPaused(v) { this.paused = v; this.worker?.postMessage({ cmd: 'run', running: !v }); }
  setMode(m) { this.userMode = m; this.mode = this.G && this.G.info.DIM === 2 ? 'section' : m; this.ensureScene(); this.dirty = true; this.panels(true); }

  onMessage(d) {
    if (d.type === 'built') this.builtMs = d.ms;
    else if (d.type === 'geom') { this.G = d; this.scene = null; this.ensureScene(); }
    else if (d.type === 'frame') { this.F = d; this.trackFrame(d); this.dirty = true; }
    else if (d.type === 'end') { this.finished = true; }
  }

  // ---- outcome bookkeeping (what gets saved with the run) ----
  trackFrame(f) {
    const tr = this.track, G = this.G; if (!G) return;
    let flame = 0, hrr = 0;
    f.stats.forEach((r, i) => {
      const id = G.ROOMS[i].id;
      flame += r.flame; hrr += r.hrr;
      if (r.flame > 0 && tr.fire[id] === undefined) tr.fire[id] = f.t;
      if (r.ext >= 0.1 && tr.smoke[id] === undefined) tr.smoke[id] = f.t;
      tr.Tmax[id] = Math.max(tr.Tmax[id] || 0, r.Tmax); tr.Xmin[id] = Math.min(tr.Xmin[id] ?? 100, r.Xmin); tr.vis[id] = Math.min(tr.vis[id] ?? 99, r.vis);
    });
    // heat release: per metre of depth in a 2D section (the solver's convention), total in 3D
    tr.peakHrr = Math.max(tr.peakHrr, hrr / 1000);
    if (flame > 0) { tr.everFlame = true; tr.quietSince = null; } else if (tr.everFlame && tr.quietSince === null) tr.quietSince = f.t;
    // the lab's automatic vent shutdown: fans off at the first smoke alarm (the solver's own vent switch)
    if (this.params.autoVent && tr.ventOffAt === null && f.vent && f.stats.some((r) => r.ext >= 0.1)) {
      tr.ventOffAt = f.t; this.worker?.postMessage({ cmd: 'vent', vent: false });
    }
    if (!this.finished && tr.quietSince !== null && f.t - tr.quietSince > 60) { this.finished = true; this.worker?.postMessage({ cmd: 'run', running: false }); }
  }

  summary() {
    const G = this.G, F = this.F, grid = G ? { dim: G.info.DIM || 3, h: G.info.h, nx: G.info.nx, ny: G.info.ny, nz: G.info.nz } : this.gridFor(this.model, this.tier);
    const tr = this.track || { fire: {}, smoke: {}, Tmax: {}, Xmin: {}, vis: {}, peakHrr: 0, ventOffAt: null, everFlame: false };   // before the first Start
    const flame = F ? F.stats.reduce((a, r) => a + r.flame, 0) : 0;
    const status = !F ? 'running' : flame > 0 ? (this.finished ? 'time_limit' : 'running') : !tr.everFlame ? 'did_not_ignite' : F.ext ? 'went_out' : 'burnt_out';
    const r1 = (v) => (v === undefined || v === null ? null : Math.round(v * 10) / 10);
    return {
      model: `cfd_${this.model}`, status, sim_time_s: r1(F ? F.t : 0), grid, tier: this.tier, ignition: this.params ? MODELS[this.model].items[this.params.location] || null : null,
      extinction_cause: F && F.ext ? String(F.ext).slice(0, 24) : null, vent_off_s: r1(tr.ventOffAt), peak_hrr_kw: r1(tr.peakHrr),
      rooms: (G ? G.ROOMS : []).map((r) => ({ room: r.id, fire_s: r1(tr.fire[r.id]), smoke_s: r1(tr.smoke[r.id]),
        max_gas_c: tr.Tmax[r.id] ? Math.round(tr.Tmax[r.id] - 273) : null, min_o2_pct: r1(tr.Xmin[r.id]), min_visibility_m: r1(tr.vis[r.id]) })),
    };
  }

  // ---- 3D scene ----
  ensureScene() {
    if (!this.G || this.mode !== '3d' || this.scene) return;
    const G = this.G, I = G.info, cv = this.els.canvas3d;
    if (!this.renderer) {
      try {
        this.renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: this.tier === 'high', powerPreference: 'high-performance' });
      } catch { this.mode = 'section'; return; }
      this.renderer.toneMapping = THREE.ACESFilmicToneMapping; this.renderer.toneMappingExposure = 1.15;
      this.camera = new THREE.PerspectiveCamera(42, 2, 0.05, 200);
      this.controls = new OrbitControls(this.camera, cv); this.controls.enableDamping = true;
      this.controls.addEventListener('change', () => { this.dirty = true; });
      new ResizeObserver(() => this.resize()).observe(cv);
    }
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.tier === 'high' ? 2 : this.tier === 'medium' ? 1.25 : 1));
    const scene = this.scene = new THREE.Scene();
    scene.background = new THREE.Color('#05080c');
    scene.add(new THREE.HemisphereLight(0xdfe8ff, 0x1a2230, 0.9));
    const sun = new THREE.DirectionalLight(0xfff4e0, 1.2); sun.position.set(-6, 10, 8); scene.add(sun);
    const h = I.h, LX = (I.nx - 2) * h, LY = (I.ny - 2) * h, LZ = (I.nz - 2) * h;
    const wpos = (k) => { const i = k % I.nx, j = Math.floor(k / I.nx) % I.ny, l = Math.floor(k / (I.nx * I.ny)); return [(i - 0.5) * h, (j - 0.5) * h, (l - 0.5) * h]; };
    this.wpos = wpos;
    const box = new THREE.BoxGeometry(h * 0.98, h * 0.98, h * 0.98), Mx = new THREE.Matrix4(), c = new THREE.Color();
    // interior structure touching the cabin air; the front part (towards the camera) is see-through
    const SZ = I.nx * I.ny, back = [], cut = [], spacecraft = I.AXY !== undefined;
    for (let k = 0; k < I.N; k++) {
      if (G.typeArr[k] !== 1 || G.openId[k] >= 0) continue;
      let near = false; for (const o of [1, -1, I.nx, -I.nx, SZ, -SZ]) { const n = k + o; if (n >= 0 && n < I.N && G.typeArr[n] === 0) { near = true; break; } }
      if (!near) continue;
      const [x, y, z] = wpos(k);
      if (spacecraft && G.sclass && G.sclass[k] === 1 && Math.hypot(y - I.AXY, z - I.AXZ) > (x > 9.5 ? 1.05 : 1.8)) continue;   // hull: drawn as a shell
      // spacecraft: the camera looks from +z (the teammate's view); habitats: from -z, because the habitat
      // solvers line the back walls (+z) and the camera must look at them, not through them
      const front = spacecraft ? z > I.AXZ + 0.9 : z < LZ * 0.38;
      (front ? cut : back).push([k, G.sclass ? G.sclass[k] : 0]);
    }
    const mk = (list, op) => {
      const m = new THREE.InstancedMesh(box, new THREE.MeshStandardMaterial({ roughness: 0.7, metalness: 0.15, transparent: op < 1, opacity: op, depthWrite: op >= 1 }), Math.max(1, list.length));
      m.count = list.length;
      list.forEach(([k, cls], q) => { const [x, y, z] = wpos(k); Mx.makeTranslation(x, y, z); m.setMatrixAt(q, Mx); c.set(cls === 2 ? '#7f8a96' : cls === 3 ? '#aebccb' : '#c9c4b8'); m.setColorAt(q, c); });
      return m;
    };
    scene.add(mk(back, 1)); scene.add(mk(cut, 0.12));
    if (spacecraft) {           // the pressure hull of the lab module, node and airlock, as faint shells
      for (const [x0, x1, r] of [[0.3, 6.5, 2.12], [6.5, 9.5, 2.12], [9.5, 11.4, 1.32]]) {
        const shell = new THREE.Mesh(new THREE.CylinderGeometry(r, r, x1 - x0, 48, 1, true),
          new THREE.MeshStandardMaterial({ color: 0x9aa4b1, side: THREE.BackSide, metalness: 0.45, roughness: 0.45, transparent: true, opacity: 0.35 }));
        shell.rotation.z = Math.PI / 2; shell.position.set((x0 + x1) / 2, I.AXY, I.AXZ); scene.add(shell);
      }
    }
    this.fuelMesh = new THREE.InstancedMesh(box, new THREE.MeshLambertMaterial(), Math.max(1, G.fuelList.length));
    this.fuelMesh.count = G.fuelList.length;
    G.fuelList.forEach((k, q) => { const [x, y, z] = wpos(k); Mx.makeTranslation(x, y, z); this.fuelMesh.setMatrixAt(q, Mx); this.fuelMesh.setColorAt(q, c.set(MATCOL[G.MKEYS[G.mat[k]]] || '#cccccc')); });
    scene.add(this.fuelMesh);
    const gas = []; for (let k = 0; k < I.N; k++) if (G.typeArr[k] === 0) gas.push(k);
    // light devices draw every second gas cell; the physics is unaffected
    this.gasIdx = Int32Array.from(this.tier === 'low' ? gas.filter((_, i) => i % 2 === 0) : gas);
    const pts = (n, blending, size) => {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
      g.setAttribute('aColor', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
      g.setAttribute('aAlpha', new THREE.BufferAttribute(new Float32Array(n), 1));
      const p = this.gasIdx; const a = g.attributes.position.array;
      for (let q = 0; q < n; q++) { const [x, y, z] = wpos(p[q]); a[3 * q] = x; a[3 * q + 1] = y; a[3 * q + 2] = z; }
      return new THREE.Points(g, new THREE.ShaderMaterial({ vertexShader: pointVS, fragmentShader: pointFS, transparent: true, depthWrite: false, blending,
        uniforms: { uSize: { value: size }, uScale: { value: 400 } } }));
    };
    this.heatPts = pts(this.gasIdx.length, THREE.AdditiveBlending, h * 1.7); this.heatPts.renderOrder = 3;
    this.smokePts = pts(this.gasIdx.length, THREE.NormalBlending, h * 2.2); this.smokePts.renderOrder = 2;
    scene.add(this.smokePts); scene.add(this.heatPts);
    const zc = spacecraft ? LZ + Math.max(LX, LY) * 0.95 : -Math.max(LX, LY) * 0.95;
    this.camera.position.set(LX * 0.42, LY * 1.25 + 1.5, zc);
    this.controls.target.set(LX / 2, LY / 2, LZ / 2); this.controls.update();
    this.resize(); this.dirty = true;
  }

  resize() {
    if (!this.renderer) return;
    const cv = this.els.canvas3d, w = cv.clientWidth || 600, hgt = cv.clientHeight || 300;
    this.renderer.setSize(w, hgt, false); this.camera.aspect = w / hgt; this.camera.updateProjectionMatrix(); this.dirty = true;
  }

  updateScene() {
    const G = this.G, F = this.F; if (!G || !F || !this.scene) return;
    const c = new THREE.Color();
    G.fuelList.forEach((k, q) => {
      const s = F.fst[k];
      if (s === 2) { const fl = 0.85 + Math.random() * 0.15; c.setRGB(1.0 * fl, 0.45 * fl, 0.08); }
      else if (s === 4 || s === 3) c.setRGB(0.16, 0.13, 0.11);
      else { c.set(MATCOL[G.MKEYS[G.mat[k]]] || '#cccccc'); if (s === 1) c.lerp(new THREE.Color('#ff8a3d'), Math.min(1, Math.max(0, (F.T[k] - 300) / 350))); }
      this.fuelMesh.setColorAt(q, c);
    });
    this.fuelMesh.instanceColor.needsUpdate = true;
    const L = this.els.layers || {};
    this.heatPts.visible = L.heat !== false; this.smokePts.visible = L.smoke !== false;
    const hc = this.heatPts.geometry.attributes.aColor.array, ha = this.heatPts.geometry.attributes.aAlpha.array;
    const sc = this.smokePts.geometry.attributes.aColor.array, sa = this.smokePts.geometry.attributes.aAlpha.array;
    for (let q = 0; q < this.gasIdx.length; q++) {
      const k = this.gasIdx[q], T = F.T[k], [r, g, b] = heatColor(T);
      hc[3 * q] = r; hc[3 * q + 1] = g; hc[3 * q + 2] = b; ha[q] = T > 340 ? Math.min(0.85, (T - 340) / 700) : 0;
      const K = 8700 * 1.1 * F.YS[k]; sc[3 * q] = 0.62; sc[3 * q + 1] = 0.62; sc[3 * q + 2] = 0.64; sa[q] = Math.min(0.55, K * 0.35);
    }
    for (const a of ['aColor', 'aAlpha']) { this.heatPts.geometry.attributes[a].needsUpdate = true; this.smokePts.geometry.attributes[a].needsUpdate = true; }
  }

  // ---- vertical section (light devices, the habitat's 2D section, or on request) ----
  drawSection() {
    const G = this.G, F = this.F, cv = this.els.section; if (!G || !F || !cv) return;
    const I = G.info, W = I.nx - 2, H = I.ny - 2, l = I.DIM === 2 ? 1 : Math.max(1, Math.floor(I.nz / 2));
    if (!this.secImg || this.secImg.width !== W) { this.secCv = Object.assign(document.createElement('canvas'), { width: W, height: H }); this.secImg = this.secCv.getContext('2d').createImageData(W, H); }
    const d = this.secImg.data;
    for (let j = 1; j <= H; j++) for (let i = 1; i <= W; i++) {
      const k = i + I.nx * (j + I.ny * l), p = ((H - j) * W + (i - 1)) * 4, t = G.typeArr[k];
      let r = 16, g = 23, b = 30;
      if (t === 1) { r = 74; g = 88; b = 102; if (G.openId[k] >= 0) { r = 134; g = 162; b = 255; } }
      else if (t === 2) {
        const s = F.fst[k];
        if (s === 2) { r = 255; g = 150; b = 40; } else if (s >= 3) { r = 40; g = 33; b = 28; }
        else { const hx = MATCOL[G.MKEYS[G.mat[k]]] || '#cccccc'; r = parseInt(hx.slice(1, 3), 16); g = parseInt(hx.slice(3, 5), 16); b = parseInt(hx.slice(5, 7), 16); }
      } else {
        const T = F.T[k], a = T > 330 ? Math.min(0.85, (T - 330) / 700) : 0, [hr, hg, hb] = heatColor(T);
        r = r * (1 - a) + 255 * hr * a; g = g * (1 - a) + 255 * hg * a; b = b * (1 - a) + 255 * hb * a;
        const sm = Math.min(0.6, 8700 * 1.1 * F.YS[k] * 0.35); r = r * (1 - sm) + 120 * sm; g = g * (1 - sm) + 120 * sm; b = b * (1 - sm) + 126 * sm;
      }
      d[p] = r; d[p + 1] = g; d[p + 2] = b; d[p + 3] = 255;
    }
    this.secCv.getContext('2d').putImageData(this.secImg, 0, 0);
    const w = cv.clientWidth || 600, dpr = Math.min(window.devicePixelRatio || 1, this.tier === 'low' ? 1 : 1.5);
    const want = [Math.round(w * dpr), Math.round(w * H / W * dpr)];
    if (cv.width !== want[0] || cv.height !== want[1]) { cv.width = want[0]; cv.height = want[1]; }
    const x = cv.getContext('2d'); x.imageSmoothingEnabled = this.tier !== 'low'; x.drawImage(this.secCv, 0, 0, cv.width, cv.height);
  }

  // ---- per animation frame ----
  frame(now) {
    if (!this.visible) return;
    if (this.dirty) {
      this.dirty = false;
      if (this.mode === '3d' && this.scene) { this.updateScene(); }
      else this.drawSection();
    }
    if (this.mode === '3d' && this.scene) { this.controls.update(); this.renderer.render(this.scene, this.camera); }
    if (now - this.lastUi > 250) { this.lastUi = now; this.panels(); }
  }

  draw(force) { if (force) this.dirty = true; }

  panels(force) {
    if (!this.visible && !force) return;
    const e = this.els, G = this.G, F = this.F, sm = this.summary();
    e.canvas3d.hidden = this.mode !== '3d'; e.section.hidden = this.mode === '3d';
    if (e.clock) e.clock.textContent = F ? `${F.t.toFixed(1)} s` : '0.0 s';
    if (e.ach) e.ach.textContent = F && F.running && !this.paused ? `×${Math.round(F.achieved)}` : '';
    if (e.status) {
      const burning = F ? F.stats.filter((r) => r.flame > 0).length : 0;
      const [txt, cls] = !this.started ? ['Press Start', 'idle'] : !G ? ['Building the grid…', 'idle'] : burning ? [`Burning in ${burning} room${burning > 1 ? 's' : ''}`, 'burn']
        : sm.status === 'did_not_ignite' ? ['Did not take hold', 'out'] : sm.status === 'went_out' ? [`Went out${F.ext ? `: ${F.ext}` : ''}`, 'out']
          : sm.status === 'burnt_out' ? ['Burnt out', 'out'] : ['Heating', 'warn'];
      e.status.textContent = txt; e.status.className = `sp-pill ${cls}`;
    }
    if (e.grid) {
      const g = sm.grid;
      e.grid.textContent = G ? `${MODELS[this.model].label.en} · ${g.dim === 2 ? '2D section' : '3D'} · grid ${g.nx - 2}×${g.ny - 2}${g.dim === 2 ? '' : `×${g.nz - 2}`} · ${Math.round(g.h * 100)} cm cells${this.builtMs ? ` · built in ${(this.builtMs / 1000).toFixed(1)} s` : ''}`
        : `${MODELS[this.model].label.en} · ${g.dim === 2 ? '2D section' : '3D'} · ${Math.round(g.h * 100)} cm cells`;
    }
    if (e.rooms && G && F) {
      e.rooms.innerHTML = G.ROOMS.map((r, i) => {
        const s = F.stats[i], x = sm.rooms[i];
        const [lab, col] = s.flame > 0 ? ['Fire', '#ff7b70'] : s.burnt > 0 ? ['Burnt', '#93a1af'] : s.ext >= 0.1 ? ['Smoke', '#e8a53c'] : ['Clear', '#4cc28a'];
        return `<div class="sp-room" style="border-left-color:${col}"><b>${esc(r.name)}</b><i style="color:${col}">${lab}</i>
          <small>fire ${fmtT(x.fire_s)} · smoke ${fmtT(x.smoke_s)} · ${Math.round(s.Tmax - 273)} °C now · O₂ ${s.Xmin.toFixed(1)} % · visibility ${s.vis >= 99 ? '>30' : s.vis.toFixed(1)} m</small></div>`;
      }).join('');
    }
  }
}
