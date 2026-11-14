"""The 'Variables' section of the fire-spread page: one table per investigation, gaps stated, rows linked to the CSV."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPREAD = (ROOT / "frontend" / "spread.html").read_text(encoding="utf-8")
I18N = (ROOT / "frontend" / "js" / "i18n.js").read_text(encoding="utf-8")

SCRIPT = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const strip = (s) => s.replace(/^import .*$/gm, '').replace(/export /g, '');
const i18n = strip(fs.readFileSync('frontend/js/i18n.js', 'utf8'));
const sweep = strip(fs.readFileSync('frontend/js/sweep.js', 'utf8'));
const node = (tag) => ({tag, children: [], className: '', textContent: '',
  append(...xs) { this.children.push(...xs); }, replaceChildren(...xs) { this.children = xs; }});
const all = (n, f, out = []) => { if (f(n)) out.push(n); (n.children || []).forEach((c) => typeof c === 'object' && all(c, f, out)); return out; };
const text = (n) => typeof n === 'string' ? n : (n.textContent || '') + (n.children || []).map(text).join(' ');
const document = {documentElement: {}, querySelectorAll: () => [], getElementById: () => null, createElement: node};
const context = {document, localStorage: {getItem: () => 'en', setItem() {}}, location: {hostname: ''},
  navigator: {language: 'en'}, api: async () => ({}), getLang: () => 'en'};
vm.createContext(context);
vm.runInContext(i18n + '\n' + sweep + '\nthis.setLang = setLang; this.renderSweep = renderSweep;', context);

const cfg = (o) => ({config: null, rows: 129, o2_pct: [17, 21.5], pressure_kpa: null, flow_mps: [0.001, 0.05],
  unreported: {o2_pct: 0, pressure_kpa: 129, flow_mps: 4}, ignited: 100, not_ignited: 20, ignition_unreported: 9,
  kinds: {test: 129}, sources: [{table: 'PSI-25_bass-ii.csv', row_ranges: [[1, 60], [62, 130]], rows: 129}], ...o});
const withRows = {accession: 'PSI-25', acronym: 'BASS-II', title: 'Burning And Suppression of Solids II', rows: 129 + 18, gap: null,
  psi_url: 'https://psi.nasa.gov/physci/repo/search?q=PSI-25&data_source=psi&data_type=investigation',
  tables: ['PSI-25_bass-ii.csv'], configurations: [cfg({}), cfg({config: 'opposed', rows: 18, kinds: {test: 10, matrix: 8}})],
  with_rows: ['PSI-25'], without_rows: [
    {accession: 'PSI-26', acronym: 'BASS', reason: 'x', reason_code: 'no_conditions', detail: 'material and test number only', detail_code: 'material_and_test_number_only', raw_table: 'PSI-26_bass.csv'},
    {accession: 'PSI-62', acronym: 'BASS modelling', reason: 'y', reason_code: 'modeling_study', detail: null, detail_code: null, raw_table: null}]};
const gap = {...withRows, accession: 'PSI-26', acronym: 'BASS', rows: 0, configurations: [], tables: [],
  gap: withRows.without_rows[0]};

for (const [lang, heads, none, reason, open] of [
  ['en', ['Configuration', 'O₂ %', 'Pressure kPa', 'Rows', 'Ignited'], 'not specified in table',
   'material and test number only', 'Open PSI-25_bass-ii.csv at row 1 on GitHub'],
  ['hu', ['Konfiguráció', 'O₂ %', 'Nyomás kPa', 'Sorok', 'Meggyulladt'], 'a táblában nincs megadva',
   'csak anyag és mérésszám', 'PSI-25_bass-ii.csv megnyitása az 1. sornál a GitHubon']]) {
  context.setLang(lang);
  const box = node('section'); context.renderSweep(box, withRows, [{accession: 'PSI-25', acronym: 'BASS-II'}], () => {});
  const ths = all(box, (n) => n.tag === 'th').map(text);
  for (const h of heads) assert.ok(ths.includes(h), `${lang}: header ${h} in ${ths}`);
  const trs = all(box, (n) => n.tag === 'tr' && all(n, (c) => c.tag === 'td').length);
  assert.equal(trs.length, 2, 'one table row per configuration');
  assert.ok(text(trs[0]).includes(none), `${lang}: missing configuration is labelled`);
  assert.ok(text(trs[0]).includes('129') && text(trs[0]).includes('17–21.5') && text(trs[0]).includes('100'));
  assert.ok(text(trs[1]).includes('opposed') && text(trs[1]).includes('8'));
  const links = all(trs[0], (n) => n.tag === 'a');
  assert.equal(links.length, 2, 'one link per row range');
  assert.equal(links[0].href, 'https://github.com/HAILVince/nasa_space_apps_2026/blob/main/blackfox/db/knowledge/raw_data/psi_combustion/tables/PSI-25_bass-ii.csv?plain=1#L2');
  assert.ok(links[1].href.endsWith('#L63'));
  assert.equal(links[0].target, '_blank'); assert.equal(links[0].rel, 'noopener noreferrer');
  assert.equal(links[0].ariaLabel, open); assert.equal(links[0].title, open);
  const gaps = all(box, (n) => n.tag === 'details');
  assert.ok(gaps.length === 1 && text(gaps[0]).includes('PSI-26') && text(gaps[0]).includes('PSI-62'), 'other gaps are listed');

  const g = node('section'); context.renderSweep(g, gap, [{accession: 'PSI-26', acronym: 'BASS'}], () => {});
  assert.equal(all(g, (n) => n.tag === 'table').length, 0, 'no empty table for an investigation without rows');
  assert.ok(text(g).includes(reason), `${lang}: gap reason shown: ${text(g)}`);

  // a table that never says whether the flame ignited must not read as "0 ignited"
  const silent = {...withRows, configurations: [cfg({ignited: 0, not_ignited: 0, ignition_unreported: 129})]};
  const q = node('section'); context.renderSweep(q, silent, [], () => {});
  const cells = all(q, (n) => n.tag === 'td').map(text);
  assert.ok(!cells.some((c) => c.includes('0 / 129')), `${lang}: ${cells}`);
}
"""


def test_sweep_renders_table_links_and_gaps_in_both_languages():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed to execute the frontend renderer")
    r = subprocess.run([node, "-e", SCRIPT], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]


def test_spread_page_hosts_the_sweep_section():
    assert 'id="sweep"' in SPREAD and './js/sweep.js' in SPREAD
    assert len(re.findall(r"sw_title: '", I18N)) == 2          # HU and EN
