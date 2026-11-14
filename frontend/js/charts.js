// Hand-built SVG charts (crisp at any size, no library). Inputs come from the API untouched.
const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs = {}, text) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}
const fmt = (v, d = 0) => Number(v).toFixed(d);

export function flammabilityMap(svg, data, current, presets, labels) {
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

export function timeSeries(svg, series, events, duration, t, labels) {
  svg.replaceChildren();
  const W = 320, H = 150, L = 8, R = 8, T = 10, B = 18;
  const X = (s) => L + s / duration * (W - L - R);
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
    if (!['alarm', 'vent_off', 'co2', 'water_mist', 'extinguished', 'self_extinguished'].includes(e.key) || e.t > duration) continue;
    svg.append(el('line', { x1: X(e.t), x2: X(e.t), y1: T, y2: H - B, stroke: e.key === 'alarm' ? '#e8c547' : e.key.includes('extinguished') ? '#59d38c' : '#5ad1e6', 'stroke-width': 1, opacity: 0.8 }));
  }
  svg.append(el('line', { x1: X(t), x2: X(t), y1: T - 4, y2: H - B, stroke: '#fff', 'stroke-width': 1 }));
  svg.append(el('text', { x: L + 2, y: T + 2, fill: '#f08a3c' }, `${fmt(maxH, maxH < 1 ? 2 : 1)} kW`));
  svg.append(el('text', { x: W - R - 2, y: T + 2, fill: '#a58cff', 'text-anchor': 'end' }, `${fmt(maxC, maxC < 10 ? 1 : 0)} ppm`));
  return labels;
}
