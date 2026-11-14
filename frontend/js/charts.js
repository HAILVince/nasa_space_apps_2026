// Hand-built SVG charts (crisp at any size, no library). Inputs come from the API untouched.
const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs = {}, text) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}
const fmt = (v, d = 0) => Number(v).toFixed(d);

export function flammabilityMap(svg, data, current, presets, labels, envelopes = []) {
  svg.replaceChildren();
  const W = 320, H = 196, L = 30, R = 8, T = 8, B = 24;
  const x0 = 20, x1 = 110, y0 = 15, y1 = 50;
  const X = (p) => L + (p - x0) / (x1 - x0) * (W - L - R);
  const Y = (o) => T + (1 - (Math.min(Math.max(o, y0), y1) - y0) / (y1 - y0)) * (H - T - B);
  const g = el('g');
  for (let p = 20; p <= 110; p += 10) {
    g.append(el('line', { x1: X(p), x2: X(p), y1: T, y2: H - B, class: 'grid' }));
    if (p % 20 === 0) g.append(el('text', { x: X(p), y: H - B + 12, 'text-anchor': 'middle' }, p));
  }
  for (let o = 15; o <= 50; o += 5) {
    g.append(el('line', { x1: L, x2: W - R, y1: Y(o), y2: Y(o), class: 'grid' }));
    g.append(el('text', { x: L - 5, y: Y(o) + 3, 'text-anchor': 'end' }, o));
  }
  g.append(el('text', { x: W - R, y: H - 2, 'text-anchor': 'end' }, 'kPa'));
  g.append(el('text', { x: L + 4, y: H - B - 4 }, '% O₂'));
  svg.append(g);
  // PSI microgravity test envelopes (oxygen x pressure); a single tested pressure is a short bar
  for (const e of envelopes) {
    const [p0, p1] = e.pressureKPa, [o0, o1] = e.o2Pct;
    const xa = X(Math.max(p0, x0)), xb = X(Math.min(p1, x1));
    if (xb < L || xa > W - R) continue;
    const w = Math.max(xb - xa, 4), x = p1 - p0 < 1 ? xa - 2 : xa;
    svg.append(el('rect', { x, y: Y(o1), width: w, height: Math.max(Y(o0) - Y(o1), 2), fill: 'rgba(111,214,232,.10)', stroke: 'rgba(111,214,232,.55)', 'stroke-width': 1, 'stroke-dasharray': e.verified ? '' : '3 2' }));
    svg.append(el('text', { x: x + 3, y: Y(o1) + 9, fill: '#6fd6e8' }, e.acronym));
  }
  const ps = data.pressure_kpa;
  const path = (arr) => ps.map((p, i) => `${i ? 'L' : 'M'}${X(p).toFixed(1)},${Y(arr[i]).toFixed(1)}`).join('');
  // flammable region above the corrected limit
  const area = `${path(data.moc_eff)}L${X(ps.at(-1))},${T}L${X(ps[0])},${T}Z`;
  svg.append(el('path', { d: area, fill: 'rgba(255,77,77,.09)' }));
  svg.append(el('path', { d: path(data.normoxic), fill: 'none', stroke: '#5ad1e6', 'stroke-width': 1, 'stroke-dasharray': '1.5 3', opacity: 0.8 }));
  svg.append(el('path', { d: path(data.moc_1g), fill: 'none', stroke: '#8e9aa4', 'stroke-width': 1.2, 'stroke-dasharray': '4 3' }));
  svg.append(el('path', { d: path(data.moc_eff), fill: 'none', stroke: '#f08a3c', 'stroke-width': 2 }));
  for (const m of data.measured) svg.append(el('circle', { cx: X(m.pressure_kpa), cy: Y(m.moc_pct), r: 2.6, fill: '#0a0d10', stroke: '#e6ebee', 'stroke-width': 1.2 }));
  for (const pr of presets) {
    svg.append(el('rect', { x: X(pr.p) - 2.2, y: Y(pr.o) - 2.2, width: 4.4, height: 4.4, fill: '#5f6b75', transform: `rotate(45 ${X(pr.p)} ${Y(pr.o)})` }));
    svg.append(el('text', { x: X(pr.p) + 5, y: Y(pr.o) - 4, fill: '#6f7c86' }, pr.label));
  }
  const ok = current.flammable;
  const cx = X(Math.min(Math.max(current.p, x0), x1)), cy = Y(current.o);
  svg.append(el('circle', { cx, cy, r: 9, fill: ok ? 'rgba(255,77,77,.18)' : 'rgba(89,211,140,.18)' }));
  svg.append(el('circle', { cx, cy, r: 4.2, fill: ok ? '#ff4d4d' : '#59d38c', stroke: '#fff', 'stroke-width': 1.3 }));
  svg.append(el('text', { x: L + 6, y: T + 13, fill: '#ff7b7b', 'font-weight': 600 }, labels.flam));
  svg.append(el('text', { x: W - R - 6, y: H - B - 6, fill: '#59d38c', 'text-anchor': 'end', 'font-weight': 600 }, labels.nonflam));
}

const TS = { W: 320, H: 150, L: 8, R: 8, T: 10, B: 18 };
const tsX = (s, duration) => TS.L + s / duration * (TS.W - TS.L - TS.R);

// playback only moves the time cursor: the rest of the chart depends on the result alone
export function timeCursor(svg, t, duration) {
  if (!svg._cursor) return;
  const x = tsX(t, duration);
  svg._cursor.setAttribute('x1', x); svg._cursor.setAttribute('x2', x);
}

export function timeSeries(svg, series, events, duration, t, labels) {
  svg.replaceChildren();
  const { W, H, L, R, T, B } = TS;
  const X = (s) => tsX(s, duration);
  const maxH = Math.max(0.05, ...series.map((r) => r.hrr_kw));
  const maxC = Math.max(1, ...series.map((r) => r.co_ppm));
  const maxS = Math.max(1.2, ...series.map((r) => r.smoke_detector));
  const Y = (v, m) => T + (1 - v / m) * (H - T - B);
  for (let s = 0; s <= duration; s += 60) {
    svg.append(el('line', { x1: X(s), x2: X(s), y1: T, y2: H - B, class: 'grid' }));
    svg.append(el('text', { x: X(s), y: H - 5, 'text-anchor': 'middle' }, `${s / 60}′`));
  }
  const line = (key, m) => series.map((r, i) => `${i ? 'L' : 'M'}${X(r.t).toFixed(1)},${Y(r[key], m).toFixed(1)}`).join('');
  svg.append(el('path', { d: `${line('hrr_kw', maxH)}L${X(series.at(-1).t)},${H - B}L${X(0)},${H - B}Z`, fill: 'rgba(240,138,60,.22)' }));
  svg.append(el('path', { d: line('hrr_kw', maxH), fill: 'none', stroke: '#f08a3c', 'stroke-width': 1.6 }));
  svg.append(el('path', { d: line('smoke_detector', maxS), fill: 'none', stroke: '#9aa5ad', 'stroke-width': 1.1 }));
  svg.append(el('line', { x1: L, x2: W - R, y1: Y(1, maxS), y2: Y(1, maxS), stroke: '#9aa5ad', 'stroke-dasharray': '2 3', opacity: 0.6 }));
  svg.append(el('path', { d: line('co_ppm', maxC), fill: 'none', stroke: '#a58cff', 'stroke-width': 1.4 }));
  for (const e of events) {
    if (!['alarm', 'vent_off', 'co2', 'water_mist', 'k_aerosol', 'clean_agent', 'inert_n2', 'extinguished', 'self_extinguished'].includes(e.key) || e.t > duration) continue;
    svg.append(el('line', { x1: X(e.t), x2: X(e.t), y1: T, y2: H - B, stroke: e.key === 'alarm' ? '#e8c547' : e.key.includes('extinguished') ? '#59d38c' : '#5ad1e6', 'stroke-width': 1, opacity: 0.8 }));
  }
  svg._cursor = el('line', { x1: X(t), x2: X(t), y1: T - 4, y2: H - B, stroke: '#fff', 'stroke-width': 1 });
  svg.append(svg._cursor);
  svg.append(el('text', { x: L + 2, y: T + 2, fill: '#f08a3c' }, `${fmt(maxH, maxH < 1 ? 2 : 1)} kW`));
  svg.append(el('text', { x: W - R - 2, y: T + 2, fill: '#a58cff', 'text-anchor': 'end' }, `${fmt(maxC, maxC < 10 ? 1 : 0)} ppm`));
  return labels;
}

// ---- gap map: where PSI experiments burned things (pressure x oxygen), and what they left untested ----
// All of it comes from GET /api/flame/gapmap (flame/gapmap.py decides what is on the map; this only draws it):
// one box per envelope, the planned cabin atmospheres as dashed boxes, historic cabin fires as crosses and
// the constant-oxygen-partial-pressure curves. Nothing is dropped: a box that runs past the axis gets an
// arrow and is returned in `offscale`; a single tested value gets a minimum-size mark.
export const KPA_PER_PSI = 6.894757;
export const PHASE_COLOR = { solid: '#f08a3c', liquid: '#6fd6e8', gas: '#a58cff', aerosol: '#9aa5ad' };
export const HABITAT_COLOR = ['#e8c547', '#59d38c', '#ff7b7b', '#7fb2ff', '#e58cff', '#ffb04a'];
const rangeText = (r, d = 1) => (r[0] === r[1] ? `${+Number(r[0]).toFixed(d)}` : `${+Number(r[0]).toFixed(d)}–${+Number(r[1]).toFixed(d)}`);
export const gapRange = rangeText;

export function gapMap(svg, data, labels) {
  svg.replaceChildren();
  const W = 320, H = 340, L = 30, R = 10, T = 10, B = 44;
  const [x0, x1] = data.axes.pressureKPa, [y0, y1] = data.axes.o2Pct;
  const cl = (v, a, b) => Math.min(Math.max(v, a), b);
  const X = (p) => L + (cl(p, x0, x1) - x0) / (x1 - x0) * (W - L - R);
  const Y = (o) => T + (1 - (cl(o, y0, y1) - y0) / (y1 - y0)) * (H - T - B);
  const g = el('g');
  for (let p = x0; p <= x1; p += 20) {
    g.append(el('line', { x1: X(p), x2: X(p), y1: T, y2: H - B, class: 'grid' }));
    g.append(el('text', { x: X(p), y: H - B + 11, 'text-anchor': 'middle' }, p));
  }
  for (let o = y0; o <= y1; o += 20) {
    g.append(el('line', { x1: L, x2: W - R, y1: Y(o), y2: Y(o), class: 'grid' }));
    g.append(el('text', { x: L - 4, y: Y(o) + 3, 'text-anchor': 'end' }, o));
  }
  // the same pressure axis in psia: every pressure is shown in kPa and in psi
  for (let psi = 0; psi * KPA_PER_PSI <= x1; psi += 5) {
    g.append(el('text', { x: X(psi * KPA_PER_PSI), y: H - B + 22, 'text-anchor': 'middle', fill: '#5d666e' }, psi));
  }
  g.append(el('text', { x: W - R, y: H - 17, 'text-anchor': 'end' }, labels.x));
  g.append(el('text', { x: W - R, y: H - 4, 'text-anchor': 'end', fill: '#5d666e' }, labels.psi));
  g.append(el('text', { x: L + 4, y: T + 9 }, labels.y));
  svg.append(g);

  // constant oxygen partial pressure
  data.isoPo2.forEach((c, i) => {
    const d = c.points.map(([p, o], j) => `${j ? 'L' : 'M'}${X(p).toFixed(1)},${Y(o).toFixed(1)}`).join('');
    const path = el('path', { d, fill: 'none', stroke: '#6fd6e8', 'stroke-width': 0.9, 'stroke-dasharray': '1.5 3', opacity: 0.6 });
    path.append(el('title', {}, `${labels.iso(c)} · ${+c.po2KPa.toFixed(1)} kPa O₂`));
    svg.append(path);
    // labelled in the empty top of the chart (no experiment burned above ~85 % O2), staggered, with a dark halo
    const target = y1 - 5 - 9 * i;
    const [lp, lo] = c.points.find(([, o]) => o <= target) || c.points.at(-1);
    svg.append(el('text', { x: X(lp) + 4, y: Y(lo) + 3, fill: '#6fd6e8', 'paint-order': 'stroke', stroke: '#0a0d10', 'stroke-width': 3,
      'stroke-linejoin': 'round' }, labels.iso(c)));
  });

  // envelopes, big boxes first so the small ones stay visible on top
  const area = (r) => (r.pressureKPa[1] - r.pressureKPa[0] + 1) * (r.o2Pct[1] - r.o2Pct[0] + 1);
  const offscale = [];
  for (const r of [...data.rectangles].sort((a, b) => area(b) - area(a))) {
    const [p0, p1] = r.pressureKPa, [o0, o1] = r.o2Pct, color = PHASE_COLOR[r.fuelPhase] || '#cccccc';
    if (p0 > x1) { offscale.push(r); continue; }
    const xa = X(p0), xb = X(p1), w = Math.max(xb - xa, 3), h = Math.max(Y(o0) - Y(o1), 3);
    const x = xb - xa < 3 ? xa - 1.5 : xa, y = Y(o1) - (Y(o0) - Y(o1) < 3 ? 1.5 : 0);
    const box = el('rect', { x, y, width: w, height: h, fill: color, 'fill-opacity': 0.16, stroke: color, 'stroke-width': 1,
      'stroke-opacity': 0.85, class: 'gap-env' });
    box.append(el('title', {}, labels.envTitle(r)));
    svg.append(box);
    if (p1 > x1) {          // runs past the end of the axis: an arrow instead of a silently clipped box
      svg.append(el('path', { d: `M${W - R - 1},${y + h / 2 - 3}l4,3l-4,3z`, fill: color }));
      offscale.push(r);
    }
  }

  // planned cabin atmospheres: dashed boxes (a single value is a diamond), numbered like the list below
  const same = {};
  data.habitats.forEach((hb, i) => {
    const color = HABITAT_COLOR[i % HABITAT_COLOR.length], [p0, p1] = hb.pressureKPa, [o0, o1] = hb.o2Pct;
    const key = `${p0}|${p1}|${o0}|${o1}`, slot = same[key] = (same[key] ?? -1) + 1;
    const xa = X(p0), xb = X(p1), ya = Y(o1), yb = Y(o0);
    const point = xb - xa < 3 && yb - ya < 3;
    const mark = point
      ? el('rect', { x: xa - 3, y: ya - 3, width: 6, height: 6, fill: 'none', stroke: color, 'stroke-width': 1.4, transform: `rotate(45 ${xa} ${ya})` })
      : el('rect', { x: xa - (xb - xa < 3 ? 1.5 : 0), y: ya - (yb - ya < 3 ? 1.5 : 0), width: Math.max(xb - xa, 3), height: Math.max(yb - ya, 3),
        fill: color, 'fill-opacity': 0.08, stroke: color, 'stroke-width': 1.4, 'stroke-dasharray': '4 2' });
    mark.append(el('title', {}, labels.habTitle(hb)));
    mark.setAttribute('data-hab', hb.id);      // lets a page pick one habitat out (evidence.html)
    svg.append(mark);
    const bx = xa + 4 + slot * 12, by = ya - 6;
    svg.append(el('circle', { cx: bx, cy: by, r: 5, fill: '#0a0d10', stroke: color, 'stroke-width': 1, 'data-hab': hb.id }));
    svg.append(el('text', { x: bx, y: by + 3, 'text-anchor': 'middle', fill: color, 'font-weight': 700, 'data-hab': hb.id }, i + 1));
  });

  // historic cabin fires
  for (const inc of data.incidents) {
    const cx = X(inc.pressureKPa), cy = Y(inc.o2Pct), r = 3.4;
    const mark = el('path', { d: `M${cx - r},${cy - r}L${cx + r},${cy + r}M${cx + r},${cy - r}L${cx - r},${cy + r}`, stroke: '#ff4d4d', 'stroke-width': 1.8, fill: 'none' });
    mark.append(el('title', {}, `${inc.name} (${inc.year}) · ${rangeText([inc.o2Pct, inc.o2Pct])} % O₂ · ${rangeText([inc.pressureKPa, inc.pressureKPa])} kPa`));
    svg.append(mark);
    svg.append(el('text', { x: cx - 6, y: cy + 11, fill: '#ff7b7b', 'text-anchor': 'end' }, `${inc.name} ${inc.year}`));
  }
  return { offscale };
}
