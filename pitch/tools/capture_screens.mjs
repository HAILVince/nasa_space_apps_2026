// Capture the deck's product screenshots from the live site at 1920 x 1080.
//
//   node pitch/tools/capture_screens.mjs lab    ->  pitch/assets/screens/lab-thermal.webp   (slide 5)
//   node pitch/tools/capture_screens.mjs ai     ->  pitch/assets/screens/ai-console.webp    (slide 7)
//
// Both drive the real lab: nothing is mocked. `ai` asks the site's own example question and needs the SI
// service to answer; if it is busy the script says so and writes nothing.
import { fileURLToPath } from 'node:url';
import { launch, sleep } from './cdp.mjs';

const SITE = process.env.SITE || 'https://blackfoxhackathon.online';
const QUESTION = 'Why does polyethylene burn on the Moon at 34% oxygen?';
const out = name => fileURLToPath(new URL(`../assets/screens/${name}`, import.meta.url));
const mode = process.argv[2];
if (mode !== 'lab' && mode !== 'ai') { console.error('usage: node capture_screens.mjs lab|ai'); process.exit(2); }

const page = await launch({ webgl: true });
const click = selector => page.eval(`document.querySelector(${JSON.stringify(selector)})?.click()`);
const clickText = (selector, text) => page.eval(`[...document.querySelectorAll(${JSON.stringify(selector)})].find(e => e.textContent.includes(${JSON.stringify(text)}))?.click()`);
const choose = (id, value) => page.eval(`(() => { const e = document.getElementById(${JSON.stringify(id)}); e.value = ${JSON.stringify(value)}; e.dispatchEvent(new Event('change', { bubbles: true })); })()`);
let code = 0;
try {
  await page.goto(`${SITE}/lab.html`, 7000);
  await click('#qsHide');                               // the "New here?" card
  await clickText('#envGrid > *', 'Lunar surface');
  await sleep(600);
  await choose('qualitySel', 'high');                   // full 3D quality (software rendering is slow, a still is fine)

  if (mode === 'lab') {
    await sleep(12000);                                 // the 3D module loads
    await click('#startBtn');
    await sleep(6000);
    await click('#viewSeg [data-v="interior"]');
    await click('#modeSeg [data-v="thermal"]');
    await sleep(2500);
    await page.eval(`(() => { const e = document.getElementById('time'); e.value = 45; e.dispatchEvent(new Event('input', { bubbles: true })); })()`);
    await sleep(5000);                                  // 45 s into the fire, paused
    await page.shot(out('lab-thermal.webp'));
    console.log('wrote', out('lab-thermal.webp'));
  } else {
    await clickText('[data-cat-tab]', 'Fire');
    await choose('location', 'galley');
    await choose('material', 'polyethylene');
    await sleep(9000);
    await click('#startBtn');
    await sleep(5000);
    await click('.ask-btn');
    await sleep(800);
    await page.eval(`(() => { document.getElementById('chatInput').value = ${JSON.stringify(QUESTION)}; document.getElementById('chatForm').requestSubmit(); })()`);
    let answer = '';
    for (let i = 0; i < 150 && !answer; i++) {
      await sleep(1000);
      answer = await page.eval(`document.querySelector('#chatLog .pending') ? '' : (document.querySelector('#chatLog .msg.assistant')?.innerText || '')`);
    }
    if (!answer || /not available|try again/i.test(answer)) {
      console.error('The SI did not answer:', answer || 'no reply within 150 s');
      code = 1;
    } else {
      await sleep(900);
      const box = await page.eval(`(() => { const r = document.getElementById('consoleDrawer').getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; })()`);
      await page.shot(out('ai-console.webp'), box);     // the console drawer only
      console.log('wrote', out('ai-console.webp'), '\n' + answer.slice(0, 400));
    }
  }
} catch (e) {
  console.error(e.message);
  code = 1;
}
await page.close();
process.exit(code);
