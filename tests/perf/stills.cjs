// Renders the landing page backdrops (frontend/assets/img/bg-*.webp source PNGs) from the real
// 3D scene: each chapter's camera, environment, mode and simulated fire, at high quality, with
// time frozen so the picture is reproducible. The landing page shows these stills instead of
// running WebGL, so it scrolls smoothly on any machine.
//   node tests/perf/stills.cjs <out-dir>      (site running on BFX_URL, default :8010)
// Needs the 3D landing scene (site.js before the switch to stills, e.g. commit c617a5a).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.BFX_URL || 'http://127.0.0.1:8010';
const ARGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'];
const SEED = `(() => { let s = 1234567; window.__seed = (v) => { s = v >>> 0; }; Math.random = () => ((s = (s * 1103515245 + 12345) >>> 0) / 4294967296); })();`;
// chapter, simulated time shown (s): the flame is grown, the smoke has started
const CHAPTERS = [['hero', 0], ['ch1', 24], ['ch2', 20], ['ch3', 14], ['ch4', 0]];
const SIZES = [['desktop', { width: 1600, height: 900 }, 2], ['mobile', { width: 414, height: 896 }, 2]];

async function still(browser, dir, key, T, sizeName, viewport, dsf) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: dsf, isMobile: sizeName === 'mobile', hasTouch: sizeName === 'mobile' });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log(key, 'pageerror', e.message));
  await page.addInitScript(SEED);
  await page.addInitScript(() => addEventListener('DOMContentLoaded', () => {
    const st = document.createElement('style');
    st.textContent = '*,*::before,*::after{transition:none!important;animation:none!important}';
    document.head.append(st);
  }));
  await page.clock.install({ time: new Date('2026-11-14T12:00:00Z') });
  await page.goto(`${BASE}/?q=high&fps=60`);
  await page.clock.pauseAt(new Date('2026-11-14T12:01:00Z'));
  const tick = async () => { await page.clock.runFor(17); await page.waitForTimeout(40); };
  const until = async (fn, arg = null, ms = 240000) => { const t0 = Date.now(); while (!(await page.evaluate(fn, arg).catch(() => false))) { if (Date.now() - t0 > ms) throw new Error(`timeout ${key}`); await tick(); } };
  await until(() => !!window.bfx?.viewer?.habitat);
  await page.clock.fastForward(1500);
  await page.evaluate((k) => { document.documentElement.style.scrollBehavior = 'auto'; const el = document.querySelector(`[data-scene=${k}]`); scrollTo(0, el.getBoundingClientRect().top + scrollY); }, key);
  await until((k) => document.body.dataset.section === k && window.bfx.story.key === k && !!window.bfx.story.result, key);
  const env = { hero: 'leo', ch1: 'leo', ch2: 'moon', ch3: 'leo', ch4: 'mars' }[key];
  await until((e) => window.bfx.viewer.envName === e, env);
  for (let i = 0; i < 8; i++) await tick();
  await page.evaluate((T) => {
    const v = window.bfx.viewer, st = window.bfx.story;
    v.setView(v.view, true); v.tween = null; v.baseDist = null; v.controls.autoRotate = false;
    v.shift = v.shiftTarget; v.shiftY = v.shiftYTarget; v.ptr.x = v.ptr.tx = 0; v.ptr.y = v.ptr.ty = 0;
    v.mixer?.setTime(0); if (v.envs.earth) v.envs.earth.rotation.y = 0;
    window.__seed(7);
    st.t = Math.max(0, T - 2); v.setTime(st.t, null, -1);
    v._shadowT = 0; v.shadowsDirty();
  }, T);
  const now = await page.evaluate(() => performance.now());
  await page.clock.fastForward(Math.max(0, 600000 - now));
  await page.clock.runFor(1000 / 60);
  await page.evaluate(() => { const v = window.bfx.viewer; if (v.fire.params) { v.fire.setState(v.row, 0, v.camera, 1e6); v.fire.phase = 0; } });
  for (let i = 0; i < 20; i++) await page.clock.runFor(1000 / 60);          // 2 s of simulated smoke
  await page.addStyleTag({ content: '.nav,main,.skip,.labels,.vignette,.poster,footer{visibility:hidden!important}' });
  await page.waitForTimeout(300);
  const file = path.join(dir, `bg-${key}-${sizeName}.png`);
  await page.screenshot({ path: file, timeout: 300000 });
  console.log('still', file);
  await ctx.close();
}

(async () => {
  const dir = process.argv[2];
  fs.mkdirSync(dir, { recursive: true });
  const only = (process.env.ONLY || '').split(',').filter(Boolean);
  const browser = await chromium.launch({ args: ARGS });
  for (const [sizeName, viewport, dsf] of SIZES) {
    for (const [key, T] of CHAPTERS) {
      if (only.length && !only.includes(`${key}-${sizeName}`)) continue;
      await still(browser, dir, key, T, sizeName, viewport, dsf);
    }
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
