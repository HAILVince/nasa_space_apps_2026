// A very small Chrome DevTools Protocol client for a headless Chromium browser (Brave, Chrome or Chromium).
// No npm packages: Node 22 has WebSocket and fetch built in. Used to capture screenshots, and later the PDF.
//
//   import { launch, sleep } from './cdp.mjs';
//   const page = await launch();              // 1920 x 1080
//   await page.goto('https://example.org');
//   await page.shot('out.webp');
//   await page.close();
//
// Set BROWSER=/path/to/chrome if `brave-browser` is not the browser on this machine.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export const sleep = ms => new Promise(r => setTimeout(r, ms));

export async function launch({ width = 1920, height = 1080, port = 9334, webgl = false } = {}) {
  const profile = mkdtempSync(join(tmpdir(), 'deck-browser-'));
  const args = ['--headless=new', '--no-first-run', '--no-default-browser-check', '--hide-scrollbars',
    `--user-data-dir=${profile}`, `--remote-debugging-port=${port}`, `--window-size=${width},${height}`];
  if (webgl) args.push('--ignore-gpu-blocklist', '--enable-unsafe-swiftshader');   // software WebGL for the 3D lab
  const proc = spawn(process.env.BROWSER || 'brave-browser', [...args, 'about:blank'], { stdio: 'ignore' });

  let target;
  for (let i = 0; i < 80 && !target; i++) {
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page'); } catch { /* not up yet */ }
    if (!target) await sleep(250);
  }
  if (!target) { proc.kill(); throw new Error('the browser did not start'); }

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let id = 0;
  const pending = new Map(), errors = [];
  ws.onmessage = m => {
    const d = JSON.parse(m.data);
    if (d.id && pending.has(d.id)) {
      const { resolve, reject } = pending.get(d.id);
      pending.delete(d.id);
      d.error ? reject(new Error(d.error.message)) : resolve(d.result);
    } else if (d.method === 'Runtime.exceptionThrown') {
      errors.push(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text);
    }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });

  return {
    send, errors,
    async goto(url, wait = 1200) { await send('Page.navigate', { url }); await sleep(wait); },
    async eval(expression) {
      const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
      return r.result.value;
    },
    // file type from the extension (.png or .webp); clip = {x, y, width, height} in page pixels
    async shot(file, clip) {
      const format = file.endsWith('.webp') ? 'webp' : 'png';
      const r = await send('Page.captureScreenshot', { format, quality: 90, ...(clip ? { clip: { ...clip, scale: 1 } } : {}) });
      writeFileSync(file, Buffer.from(r.data, 'base64'));
    },
    async key(key, code = key, keyCode = 0) {
      for (const type of ['keyDown', 'keyUp']) await send('Input.dispatchKeyEvent', { type, key, code, windowsVirtualKeyCode: keyCode });
    },
    async close() {
      try { await send('Browser.close'); } catch { /* already gone */ }
      await new Promise(done => {                        // let the browser exit before removing its profile
        if (proc.exitCode !== null) return done();
        proc.once('exit', done);
        setTimeout(() => { proc.kill(); done(); }, 3000);
      });
      try { rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* a temp folder; leave it */ }
    },
  };
}
