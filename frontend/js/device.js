// What the machine running the simulator can do, and how much simulation it should get.
//
// The profile combines what the browser reports (CPU cores, memory, screen, touch, data saver, reduced
// motion, the GPU's name) with one real measurement: how long this device takes to solve the habitat's
// ventilation flow, the heaviest step of the 2D model. The tier then sets how the simulators draw and
// how much work they do per frame. It never changes the physics: every tier gets the same numbers,
// a slow device only reaches them later in wall-clock time.

export const TIERS = {
  // load3d: start the 3D views by themselves; viewer: 3D quality preset; dpr: max canvas pixel ratio;
  // smooth: draw gas fields as smooth gradients; flames: max flame sprites per frame; budgetMs: physics
  // time per frame; uiHz: panel refreshes per second; fps: frame-rate cap; dim: dimensions for the
  // Navier-Stokes engines (2 = vertical section, 3 = full 3D)
  low: { load3d: false, viewer: 'low', dpr: 1, smooth: false, flames: 160, budgetMs: 4, uiHz: 2, fps: 30, dim: 2 },
  medium: { load3d: true, viewer: 'medium', dpr: 1.5, smooth: true, flames: 700, budgetMs: 7, uiHz: 4, fps: 60, dim: 3 },
  high: { load3d: true, viewer: 'high', dpr: 2, smooth: true, flames: 4000, budgetMs: 11, uiHz: 5, fps: 60, dim: 3 },
};
export const ORDER = ['low', 'medium', 'high'];
const KEY = 'bfx_quality';

function gpuName() {
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (!gl) return { webgl: false, gpu: '' };
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    const gpu = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    const webgl2 = typeof WebGL2RenderingContext !== 'undefined' && gl instanceof WebGL2RenderingContext;
    gl.getExtension('WEBGL_lose_context')?.loseContext();     // give the GPU context back right away
    return { webgl: true, webgl2, gpu };
  } catch { return { webgl: false, gpu: '' }; }
}

export function detect() {
  const g = gpuName();
  const conn = navigator.connection || {};
  const mm = (q) => { try { return matchMedia(q).matches; } catch { return false; } };
  return {
    cores: navigator.hardwareConcurrency || null,
    memory_gb: navigator.deviceMemory || null,             // Chromium only; null elsewhere
    dpr: Math.round((window.devicePixelRatio || 1) * 100) / 100,
    screen: [screen.width, screen.height],
    mobile: mm('(pointer: coarse)'),
    save_data: !!conn.saveData,
    reduced_motion: mm('(prefers-reduced-motion: reduce)'),
    webgl2: !!g.webgl2,
    gpu: g.gpu.slice(0, 80),
  };
}

// cpuMs: the measured flow solve. About 25-60 ms on a current laptop, several hundred on an old phone.
export function chooseTier(d, cpuMs) {
  const gpu = d.gpu.toLowerCase();
  const software = /swiftshader|llvmpipe|software|basic render/.test(gpu);
  if (software || d.save_data || (d.cores && d.cores <= 2) || (d.memory_gb && d.memory_gb <= 2) || cpuMs > 320) return 'low';
  if (!d.webgl2 || d.mobile || (d.cores && d.cores <= 4) || (d.memory_gb && d.memory_gb <= 4) || cpuMs > 110
      || /mali|adreno|powervr|apple gpu|intel\(r\) (hd|uhd) graphics [0-9]{3}\b/.test(gpu)) return 'medium';
  return 'high';
}

export function savedChoice() {
  try { const v = localStorage.getItem(KEY); return v && (v === 'auto' || TIERS[v]) ? v : 'auto'; } catch { return 'auto'; }
}
export function saveChoice(v) {
  try { localStorage.setItem(KEY, v); } catch { /* private mode: the choice lasts until reload */ }
}

// Watches frame times while a simulator is visible and moves to the next lower tier when the device
// cannot keep up (average frame over 45 ms for 2 s). It only steps down, so it cannot oscillate.
export class Governor {
  constructor(onDrop) { this.onDrop = onDrop; this.reset(); }
  reset() { this.acc = 0; this.n = 0; this.since = performance.now(); this.last = 0; }
  frame(now) {
    if (this.last && now - this.last < 1000) { this.acc += now - this.last; this.n += 1; }
    this.last = now;
    if (now - this.since < 2000 || !this.n) return;
    const avg = this.acc / this.n; this.acc = 0; this.n = 0; this.since = now;
    if (avg > 45) this.onDrop(avg);
  }
}

export function describe(d, tier, cpuMs) {
  const parts = [];
  if (d.cores) parts.push(`${d.cores} cores`);
  if (d.memory_gb) parts.push(`${d.memory_gb} GB`);
  parts.push(d.mobile ? 'touch' : 'desktop');
  if (cpuMs != null) parts.push(`flow solve ${Math.round(cpuMs)} ms`);
  return { tier, text: parts.join(' · '), gpu: d.gpu };
}
