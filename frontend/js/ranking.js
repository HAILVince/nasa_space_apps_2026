// Ranking on the evidence page: the 24 investigations ordered by how close their tests came
// to the picked cabin atmosphere. The server scores (flame/rank.py); the sliders only send
// other weights. Each bar is the four weighted parts of one score, so nothing is a black box.
import { t } from './i18n.js';
import { $, api } from './common.js';

const PARTS = ['condition', 'topic', 'fuel', 'flight'];
const TOP = 8;
const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };

let habitat = null, links = new Map(), body = null, showAll = false, custom = false, asked = 0, timer = 0;

function setSliders(weights) {
  for (const p of PARTS) {
    const input = $(`evW${p}`);
    input.value = weights[p];
    input.style.setProperty('--fill', `${weights[p] * 100}%`);
    $(`evW${p}Out`).textContent = Number(weights[p]).toFixed(2);
  }
}

async function load() {
  const mine = ++asked;
  const query = custom ? `?${PARTS.map((p) => `${p}=${$(`evW${p}`).value}`).join('&')}` : '';
  try {
    const got = await api(`/api/flame/habitats/${encodeURIComponent(habitat)}/ranking${query}`);
    if (mine !== asked) return;            // a newer request is on its way
    body = got;
    if (!custom) setSliders(body.weights);  // the defaults live on the server, not in this page
    $('evRankBlock').hidden = false;
    draw();
  } catch {
    if (mine !== asked) return;
    body = null;
    $('evRankBlock').hidden = false;
    $('evRank').replaceChildren();
    $('evRankMore').hidden = true;
    $('evRankStatus').textContent = t('ev_rank_error');
  }
}

function draw() {
  if (!body) return;
  const total = PARTS.reduce((sum, p) => sum + body.weights[p], 0);
  $('evRankStatus').textContent = total ? '' : t('ev_rank_zero');
  const rows = showAll ? body.investigations : body.investigations.slice(0, TOP);
  $('evRank').replaceChildren(...rows.map((r) => {
    const name = el('a', r.acronym);
    const url = links.get(r.accession);
    if (/^https:\/\//.test(url || '')) { name.href = url; name.target = '_blank'; name.rel = 'noopener'; }
    const head = el('div', undefined, 'ev-rank-name');
    head.append(name);
    if (r.noConditionData) head.append(el('small', t('ev_rank_nocond')));
    const bar = el('span', undefined, 'ev-bar');
    bar.setAttribute('role', 'img');
    bar.setAttribute('aria-label', PARTS.map((p) => `${t(`ev_w_${p}`)} ${r.parts[p].toFixed(2)}`).join(', '));
    bar.title = bar.getAttribute('aria-label');
    for (const p of PARTS) {
      const seg = el('i', undefined, `seg-${p}`);
      seg.style.width = `${total ? (body.weights[p] * r.parts[p]) / total * 100 : 0}%`;
      bar.append(seg);
    }
    const li = el('li');
    li.append(head, bar, el('b', r.score.toFixed(3)));
    return li;
  }));
  const more = $('evRankMore');
  more.hidden = body.investigations.length <= TOP;
  more.textContent = t(showAll ? 'ev_rank_top' : 'ev_rank_all', { n: showAll ? TOP : body.investigations.length });
}

for (const p of PARTS) {
  $(`evW${p}`).addEventListener('input', (e) => {
    custom = true;
    e.target.style.setProperty('--fill', `${e.target.value * 100}%`);
    $(`evW${p}Out`).textContent = Number(e.target.value).toFixed(2);
    clearTimeout(timer);
    timer = setTimeout(load, 150);          // one request when the hand stops, not one per pixel
  });
}
$('evWreset').onclick = () => { custom = false; load(); };
$('evRankMore').onclick = () => { showAll = !showAll; draw(); };

// evidence.js calls this when the cabin or the language changes
export function showRanking(habitatId, psiLinks) {
  links = psiLinks;
  if (habitatId === habitat && body) { draw(); return; }
  habitat = habitatId;
  load();
}
