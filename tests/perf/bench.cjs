// Performance and visual-regression harness for the Black Fox pages (not run in CI: needs a
// browser). Two modes, against a running server (uvicorn app.main:app --port 8010):
//
//   node tests/perf/bench.cjs measure <out.json>   load time, transfer, frame time, CPU, heap, draw calls
//   node tests/perf/bench.cjs shots <out-dir>      deterministic screenshots of every view and mode
//
// `shots` freezes time (Playwright fake clock) and seeds Math.random, so the same code renders
// the same pixels: run it before and after a change and compare with tests/perf/diff.py.
// Software rendering (SwiftShader) is used so results do not depend on the host GPU; absolute
// frame rates are therefore far below a real GPU and only before/after ratios are meaningful.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.BFX_URL || 'http://127.0.0.1:8010';
const ARGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--js-flags=--expose-gc'];
const SEED = `(() => { let s = 1234567; window.__seed = (v) => { s = v >>> 0; }; Math.random = () => ((s = (s * 1103515245 + 12345) >>> 0) / 4294967296); })();`;

async function waitFor(page, fn, ms = 120000, tick = null) {
  const t0 = Date.now();
  for (;;) {
    if (await page.evaluate(fn).catch(() => false)) return Date.now() - t0;
    if (Date.now() - t0 > ms) throw new Error(`timeout waiting for ${fn}`);
    if (tick) await tick(); else await page.waitForTimeout(100);
  }
}

// ------------------------------------------------------------------ measure
async function measurePage(browser, url, { viewport = { width: 1366, height: 768 }, interact } = {}) {
  const ctx = await browser.newContext({ viewport });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Network.enable'); await cdp.send('Performance.enable');
  const reqs = new Map(); let bytes = 0; const byType = {};
  cdp.on('Network.responseReceived', (e) => reqs.set(e.requestId, { url: e.response.url, type: e.type }));
  cdp.on('Network.loadingFinished', (e) => {
    const r = reqs.get(e.requestId); bytes += e.encodedDataLength;
    if (r) { const k = /\.glb$/.test(r.url) ? 'model' : r.type; byType[k] = (byType[k] || 0) + e.encodedDataLength; }
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
  await page.addInitScript(() => {
    window.__lcp = 0; window.__cls = 0; window.__frames = [];
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
    const f = (t) => { window.__frames.push(t); requestAnimationFrame(f); }; requestAnimationFrame(f);
  });
  const t0 = Date.now();
  await page.goto(BASE + url, { waitUntil: 'load' });
  const loadMs = Date.now() - t0;
  const readyMs = await waitFor(page, () => !!(window.bfx?.viewer?.habitat)) + loadMs;
  await page.waitForTimeout(2500);                         // first frames: shader compile, uploads
  if (interact) await interact(page);
  const gc = () => page.evaluate(() => window.gc && window.gc());
  // steady state: 10 s window
  await page.evaluate(() => { window.__frames = []; });
  const m0 = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  await page.waitForTimeout(10000);
  const m1 = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
  const frames = await page.evaluate(() => window.__frames);
  const gaps = frames.slice(1).map((t, i) => t - frames[i]).sort((a, b) => a - b);
  const avg = gaps.reduce((a, b) => a + b, 0) / Math.max(1, gaps.length);
  const p99 = gaps[Math.floor(gaps.length * 0.99)] || 0;
  await gc();
  const info = await page.evaluate(() => {
    const v = window.bfx.viewer, r = v.renderer;
    return { tier: v.tier, calls: r.info.render.calls, triangles: r.info.render.triangles, geometries: r.info.memory.geometries,
             textures: r.info.memory.textures, programs: r.info.programs?.length, heap: performance.memory?.usedJSHeapSize,
             lcp: window.__lcp, cls: window.__cls };
  });
  await ctx.close();
  return { url, viewport, loadMs, readyMs, requests: reqs.size, transferBytes: bytes, byType,
           fpsAvg: 1000 / avg, frameMsAvg: avg, frameMsP99: p99, fps1Low: p99 ? 1000 / p99 : 0,
           cpuBusyPct: 100 * (m1.TaskDuration - m0.TaskDuration) / 10, scriptPct: 100 * (m1.ScriptDuration - m0.ScriptDuration) / 10,
           ...info, errors };
}

async function measure(out) {
  const browser = await chromium.launch({ args: ARGS });
  const res = {};
  res.landing = await measurePage(browser, '/');
  res.lab = await measurePage(browser, '/lab.html');
  res.labFire = await measurePage(browser, '/lab.html', { interact: async (p) => { await p.click('#viewSeg button[data-v=fire]'); await p.waitForTimeout(4000); } });
  // memory: switch environment and location many times, then compare the heap after GC
  {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const page = await ctx.newPage();
    await page.goto(BASE + '/lab.html');
    await waitFor(page, () => !!(window.bfx?.viewer?.habitat));
    await page.waitForTimeout(3000);
    const heap = async () => { await page.evaluate(() => window.gc && window.gc()); return page.evaluate(() => ({ heap: performance.memory.usedJSHeapSize, geo: window.bfx.viewer.renderer.info.memory.geometries, tex: window.bfx.viewer.renderer.info.memory.textures })); };
    const before = await heap();
    const envs = await page.$$eval('#envGrid button', (b) => b.map((x) => x.dataset.v));
    const locs = await page.$$eval('#location option', (o) => o.map((x) => x.value));
    for (let k = 0; k < 3; k++) {
      for (const e of envs) { await page.click(`#envGrid button[data-v="${e}"]`); await page.waitForTimeout(1200); }
      for (const l of locs) { await page.selectOption('#location', l); await page.waitForTimeout(1200); }
    }
    await page.waitForTimeout(2000);
    res.memory = { envs, locs, before, after: await heap() };
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(out, JSON.stringify(res, null, 1));
  console.log(JSON.stringify(res, null, 1));
}

// ------------------------------------------------------------------ deterministic screenshots
async function shots(dir) {
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch({ args: ARGS });
  const run = async (name, url, viewport, setup) => {
    const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.addInitScript(SEED);
    // CSS transitions run on the compositor's real clock: switch them off so overlays are settled
    await page.addInitScript(() => addEventListener('DOMContentLoaded', () => {
      const st = document.createElement('style');
      st.textContent = '*,*::before,*::after{transition:none!important;animation:none!important}';
      document.head.append(st);
    }));
    await page.clock.install({ time: new Date('2026-11-14T12:00:00Z') });
    await page.goto(BASE + url);
    await page.clock.pauseAt(new Date('2026-11-14T12:00:01Z'));       // time moves only when we say so
    const tick = async () => { await page.clock.runFor(17); await page.waitForTimeout(40); };
    await waitFor(page, () => !!(window.bfx?.viewer?.habitat) && !!window.bfx.viewer.result, 180000, tick);
    await page.clock.fastForward(1500);                    // page timers (loader fade-out) fire, no extra frames
    for (let i = 0; i < 6; i++) await tick();
    if (setup) await setup(page, tick);
    // pin everything that integrates over frames, then render a fixed sequence of frames from a
    // fixed absolute time: the result no longer depends on how long the assets took to load
    await page.evaluate(() => {
      const v = window.bfx.viewer;
      v.setView(v.view, true); v.tween = null; v.baseDist = null;
      v.controls.autoRotate = false;
      v.shift = v.shiftTarget; v.shiftY = v.shiftYTarget; v.ptr.x = v.ptr.tx; v.ptr.y = v.ptr.ty;
      v.mixer?.setTime(0);
      if (v.envs.earth) v.envs.earth.rotation.y = 0;
      window.__seed(42);                                   // before anything below draws random numbers
      const tm = document.getElementById('time');
      if (tm) { tm.value = 0; tm.dispatchEvent(new Event('input')); tm.value = 40; tm.dispatchEvent(new Event('input')); }
      const st = window.bfx.story;                         // landing page playback
      if (st?.result) { st.t = st.from; v.setTime(st.t, null, -1); }
      // flame: jump the time smoothing to its target and restart the puffing phase
      if (v.fire.params) { v.fire.setState(v.row, 0, v.camera, 1e6); v.fire.phase = 0; }
      v._shadowT = 0; v.shadowsDirty();                     // shadow map refreshes on the first frame
    });
    const now = await page.evaluate(() => performance.now());
    await page.clock.fastForward(Math.max(0, 600000 - now));
    for (let i = 0; i < 12; i++) await page.clock.runFor(1000 / 60);
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(dir, `${name}-ui.png`), timeout: 240000 });
    // the HTML marker labels snap to half pixels; the 3D image alone must match exactly
    await page.addStyleTag({ content: '.labels{visibility:hidden!important}' });
    await page.screenshot({ path: path.join(dir, `${name}.png`), timeout: 240000 });
    if (errors.length) console.log(name, 'ERRORS', errors);
    console.log('shot', name);
    await ctx.close();
  };
  const D = { width: 1366, height: 768 }, M = { width: 390, height: 844 }, T = { width: 768, height: 1024 };
  const lab = (fn) => async (p, tick) => { await fn(p, tick); for (let i = 0; i < 20; i++) await tick(); };
  const only = (process.env.SHOTS || '').split(',').filter(Boolean);
  const list = [
    ['lab-exterior', '/lab.html?q=high&fps=60', D],
    ['lab-fire', '/lab.html?q=high&fps=60', D, lab(async (p) => p.click('#viewSeg button[data-v=fire]'))],
    ['lab-thermal', '/lab.html?q=high&fps=60', D, lab(async (p) => { await p.click('#viewSeg button[data-v=cutaway]'); await p.click('#modeSeg button[data-v=thermal]'); })],
    ['lab-xray', '/lab.html?q=high&fps=60', D, lab(async (p) => p.click('#modeSeg button[data-v=xray]'))],
    ['lab-airflow', '/lab.html?q=high&fps=60', D, lab(async (p) => { await p.click('#viewSeg button[data-v=cutaway]'); await p.click('#modeSeg button[data-v=airflow]'); })],
    ['lab-interior', '/lab.html?q=high&fps=60', D, lab(async (p) => p.click('#viewSeg button[data-v=interior]'))],
    ['lab-moon', '/lab.html?q=high&fps=60#environment=moon', D],
    ['lab-mars', '/lab.html?q=high&fps=60#environment=mars', D],
    ['lab-earth', '/lab.html?q=high&fps=60#environment=earth', D],
    ['lab-gateway', '/lab.html?q=high&fps=60#environment=lunar_orbit', D],
    ['lab-galley-fire-low', '/lab.html?q=low&fps=60#location=galley', D, lab(async (p) => p.click('#viewSeg button[data-v=fire]'))],
    ['lab-fire-galley-high', '/lab.html?q=high&fps=60#location=galley', D, lab(async (p) => p.click('#viewSeg button[data-v=fire]'))],
    ['lab-fire-mars-high', '/lab.html?q=high&fps=60#environment=mars&location=galley', D, lab(async (p) => p.click('#viewSeg button[data-v=fire]'))],
    ['lab-fire-glovebox-medium', '/lab.html?q=medium&fps=60#location=glovebox', D, lab(async (p) => p.click('#viewSeg button[data-v=fire]'))],
    ['lab-mobile', '/lab.html?fps=60', M],
    ['lab-tablet', '/lab.html?fps=60', T],
    ['landing-hero', '/?q=high&fps=60', D],
    ['landing-mobile', '/?fps=60', M],
  ].filter((s) => !only.length || only.includes(s[0]));
  for (const s of list) await run(...s);
  await browser.close();
}

const [mode, out] = process.argv.slice(2);
(mode === 'shots' ? shots(out) : measure(out)).catch((e) => { console.error(e); process.exit(1); });
