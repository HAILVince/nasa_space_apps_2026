// End-to-end check of the lab and landing pages in a real (software-rendered) browser:
// every view, mode, environment and fire location, the controls, the chat drawer and the
// landing chapters, with any console error or blank 3D frame reported.
//   node tests/perf/e2e.cjs [base-url]
const { chromium } = require('playwright');
const BASE = process.argv[2] || 'http://127.0.0.1:8010';
const ARGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'];

(async () => {
  const browser = await chromium.launch({ args: ARGS });
  const problems = [];
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`console: ${m.text().slice(0, 200)}`); });
  const lit = async (what) => {           // the 3D frame must not be blank
    const v = await page.evaluate(() => {
      window.bfx.viewer.composer.render();      // read in the same task: the back buffer is not preserved
      const c = document.getElementById('gl'), g = c.getContext('webgl2'); const w = 32, h = 32;
      const px = new Uint8Array(w * h * 4); g.readPixels(Math.floor(c.width / 2) - 16, Math.floor(c.height / 2) - 16, w, h, g.RGBA, g.UNSIGNED_BYTE, px);
      let s = 0; for (let i = 0; i < px.length; i += 4) s += px[i] + px[i + 1] + px[i + 2]; return s / (w * h * 3);
    });
    return v;
  };
  await page.goto(`${BASE}/lab.html`);
  await page.waitForFunction(() => window.bfx?.viewer?.habitat, null, { timeout: 120000 });
  await page.waitForTimeout(3000);
  const steps = [];
  const step = async (name, fn, wait = 2500) => { await fn(); await page.waitForTimeout(wait); steps.push(name); };
  for (const v of ['cutaway', 'interior', 'fire', 'exterior']) await step(`view ${v}`, () => page.click(`#viewSeg button[data-v=${v}]`));
  for (const m of ['xray', 'thermal', 'airflow', 'normal']) await step(`mode ${m}`, () => page.click(`#modeSeg button[data-v=${m}]`));
  const envs = await page.$$eval('#envGrid button', (b) => b.map((x) => x.dataset.v));
  for (const e of envs) {
    await step(`env ${e}`, () => page.click(`#envGrid button[data-v="${e}"]`), 6000);
    const st = await page.evaluate(() => ({ env: window.bfx.viewer.envName, moon: !!window.bfx.viewer.envs.moonGlobe?.visible }));
    if (st.env !== e) problems.push(`environment ${e} not applied (viewer shows ${st.env})`);
    if (e === 'lunar_orbit' && !st.moon) problems.push('Gateway: Moon globe not visible');
  }
  // rapid switching: the last choice must win even while terrain is still loading
  await page.click('#envGrid button[data-v="mars"]'); await page.click('#envGrid button[data-v="leo"]'); await page.click('#envGrid button[data-v="moon"]');
  await page.waitForTimeout(6000);
  const last = await page.evaluate(() => window.bfx.viewer.envName);
  if (last !== 'moon') problems.push(`rapid environment switch ended on ${last}, expected moon`);
  await page.click('#envGrid button[data-v="leo"]'); await page.waitForTimeout(3000);
  const locs = await page.$$eval('#location option', (o) => o.map((x) => x.value));
  for (const l of locs) await step(`location ${l}`, () => page.selectOption('#location', l), 3000);
  await step('fire view', () => page.click('#viewSeg button[data-v=fire]'), 4000);
  const fireLit = await lit('fire');
  if (fireLit < 2) problems.push(`fire view looks blank (mean ${fireLit.toFixed(1)})`);
  await step('vent switch', () => page.click('label.switch'));
  if (await page.evaluate(() => scrollY) !== 0) problems.push('vent switch scrolled the page');
  for (const id of ['o2', 'pressure', 'temp', 'vent']) {
    await step(`slider ${id}`, () => page.$eval(`#${id}`, (el) => { el.value = Number(el.min) + (Number(el.max) - Number(el.min)) * 0.6; el.dispatchEvent(new Event('input')); }), 1500);
  }
  await step('play/pause', () => page.click('#play'));
  await step('restart', () => page.click('#restart'));
  await step('speed', () => page.click('#speed'));
  await step('time slider', () => page.$eval('#time', (el) => { el.value = 120; el.dispatchEvent(new Event('input')); }));
  const cursor = await page.$eval('#tsChart', (s) => s._cursor?.getAttribute('x1'));
  if (!cursor) problems.push('time-series cursor missing');
  const cov = await page.$$eval('#coverage .cov-row i', (x) => x.map((e) => e.className));
  if (!cov.length || cov.some((c) => c !== 'cov-ok')) problems.push(`coverage rows not all checked: ${cov}`);
  if (await page.$eval('#coverage', (b) => /not extracted|nincs kinyerve|not yet checked/.test(b.textContent))) problems.push('coverage still says not extracted / not checked');
  await step('language EN', () => page.click('[data-lang=en]'));
  await step('language HU', () => page.click('[data-lang=hu]'));
  const exterior = await lit('exterior');
  if (exterior < 1) problems.push(`lab 3D looks blank (mean ${exterior.toFixed(1)})`);
  // landing page: no WebGL; every chapter must show its own backdrop still
  await page.goto(`${BASE}/`);
  await page.waitForTimeout(1500);
  if (await page.evaluate(() => !!document.querySelector('canvas'))) problems.push('landing page still has a WebGL canvas');
  for (const s of ['ch1', 'ch2', 'ch3', 'ch4']) {
    await step(`landing ${s}`, () => page.evaluate((k) => { document.documentElement.style.scrollBehavior = 'auto'; const el = document.querySelector(`[data-scene=${k}]`); scrollTo(0, el.getBoundingClientRect().top + scrollY); }, s), 1800);
    const st = await page.evaluate((k) => {
      const img = document.querySelector(`.bg[data-bg="${k}"] img`);
      return { sec: document.body.dataset.section, shown: getComputedStyle(img.parentElement).opacity, loaded: img.complete && img.naturalWidth > 0 };
    }, s);
    if (st.sec !== s) problems.push(`landing ${s}: section is ${st.sec}`);
    if (st.shown !== '1' || !st.loaded) problems.push(`landing ${s}: backdrop not shown (${JSON.stringify(st)})`);
  }
  await browser.close();
  console.log(JSON.stringify({ steps: steps.length, problems }, null, 1));
  process.exit(problems.length ? 1 : 0);
})();
