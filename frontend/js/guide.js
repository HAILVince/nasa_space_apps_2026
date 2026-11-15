// "Show me": scroll to a part of the page and highlight it with one pulse.
// Used by the AI's show_on_page tool (the chat reply carries {page, url, target, note}) and by the
// lab's quick-start steps. Each target is an element with data-guide="<target>"; an element that lives
// in one of the lab's views (data-guide-view="2d|3d") switches to that view first. A target on the
// other page is remembered for this tab (sessionStorage) and shown as soon as that page has loaded.
import { t } from './i18n.js';

const KEY = 'bf_guide';
const HOLD_MS = 3800;
const here = () => (/lab\.html$/.test(location.pathname) ? 'lab' : /(^|\/)(index\.html)?$/.test(location.pathname) ? 'home' : 'other');
let timer = 0;

function find(target) {
  return document.querySelector(`[data-guide="${CSS.escape(target)}"]`);
}

// wait until the element exists and has a size (the lab builds parts of itself after loading)
function whenReady(target, ms = 6000) {
  return new Promise((resolve) => {
    const t0 = performance.now();
    const tick = () => {
      const el = find(target);
      if (el && (el.offsetWidth || el.offsetHeight || el.closest('[hidden]'))) return resolve(el);
      if (performance.now() - t0 > ms) return resolve(el);
      setTimeout(tick, 120);
    };
    tick();
  });
}

function toast(note) {
  let box = document.getElementById('guideToast');
  if (!box) {
    box = document.createElement('div');
    box.id = 'guideToast'; box.className = 'guide-toast'; box.setAttribute('role', 'status');
    document.body.append(box);
  }
  box.replaceChildren();
  const txt = document.createElement('span'); txt.textContent = note || t('guide_here');
  box.append(txt);
  if (document.getElementById('consoleDrawer')) {          // the chat lives in the lab: one tap back to it
    const back = document.createElement('button'); back.type = 'button'; back.className = 'link';
    back.textContent = t('guide_back');
    back.onclick = () => { box.hidden = true; document.querySelector('[data-tab-link="console"]')?.click(); };
    box.append(back);
  }
  box.hidden = false;
  clearTimeout(box._t); box._t = setTimeout(() => { box.hidden = true; }, HOLD_MS + 2500);
}

export async function highlight(target, note = '', fromChat = false) {
  let el = find(target);
  if (!el) return false;
  const view = el.dataset.guideView;
  if (view) document.querySelector(`#simView [data-v="${view}"]`)?.click();
  const cat = el.closest('[data-cat]')?.dataset.cat;                         // a setting in another category tab
  if (cat) document.querySelector(`[data-cat-tab="${cat}"]`)?.click();
  for (const d of document.querySelectorAll('dialog[open]')) d.close();      // nothing may cover it
  el = await whenReady(target);
  if (!el) return false;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const tall = el.getBoundingClientRect().height > innerHeight * 0.6;   // a tall part: show its top, with the outline
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: tall ? 'start' : 'center', inline: 'nearest' });
  document.querySelectorAll('.guide-hl').forEach((x) => x.classList.remove('guide-hl'));
  void el.offsetWidth;                                     // restart the pulse when the same part is shown twice
  el.classList.add('guide-hl');
  clearTimeout(timer);
  timer = setTimeout(() => el.classList.remove('guide-hl'), HOLD_MS);
  if (fromChat) toast(note);                               // the quick-start steps need no message
  return true;
}

// carry out the action of a chat reply; another page: go there and show it on arrival
export function runGuide(action) {
  if (!action || action.type !== 'show' || !action.target) return;
  if (action.page && action.page !== here()) {
    try { sessionStorage.setItem(KEY, JSON.stringify({ ...action, at: Date.now() })); } catch { /* storage blocked */ }
    location.href = action.url || (action.page === 'lab' ? './lab.html' : './');
    return;
  }
  highlight(action.target, action.note, true);
}

// on page load: show what the AI pointed at on the previous page (if it is recent)
export function resumeGuide() {
  let a = null;
  try { a = JSON.parse(sessionStorage.getItem(KEY) || 'null'); sessionStorage.removeItem(KEY); } catch { a = null; }
  if (!a || a.page !== here() || Date.now() - (a.at || 0) > 60000) return;
  setTimeout(() => highlight(a.target, a.note, true), 700);
}
