"""Exercise the coverage rows with real translations and DOM-like text nodes."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_coverage_displays_measurements_and_sensor_gaps_in_both_languages():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed to execute the frontend renderer")
    script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const i18n = fs.readFileSync('frontend/js/i18n.js', 'utf8').replace(/export /g, '');
const lab = fs.readFileSync('frontend/js/lab.js', 'utf8');
const render = lab.slice(lab.indexOf('function renderCoverage()'), lab.indexOf('\nfunction renderLog()'));
const box = {children: [], replaceChildren() { this.children = []; }, append(x) { this.children.push(x); }};
const document = {documentElement: {}, querySelectorAll: () => [], createTextNode: text => ({textContent: text}), createElement: () => ({
  children: [], textContent: '', append(...xs) { this.children.push(...xs); }
})};
const context = {document, localStorage: {getItem: () => 'en', setItem() {}}, location: {hostname: ''},
  navigator: {language: 'en'}, $: () => box, catalog: {environments: {leo: {g_fraction: 0}}},
  S: {environment: 'leo'}, result: {inputs: {pressure_kpa: 100, o2_pct: 21}, flammability: {}},
  flameCtx: {habitats: [], envelopes: [
    {accession: 'PSI-1', acronym: 'ONE', o2Pct: [20, 22], pressureKPa: [99, 101], fuel: 'fuel',
     measured: ['flame appearance', 'extinction'], sensors: ['video', 'IR'], verified: true},
    {accession: 'PSI-2', acronym: 'TWO', o2Pct: [20, 22], pressureKPa: [99, 101], fuel: 'fuel',
     measured: ['growth'], sensors: [], verified: false}
  ]}, num: x => x};
vm.createContext(context);
vm.runInContext(i18n + '\n' + render + '\nthis.setLang = setLang; this.renderCoverage = renderCoverage;', context);
for (const [lang, expected, missing] of [
  ['en', 'Measured: flame appearance, extinction · Sensors: video, IR', 'Measured: growth · Sensors: not reported'],
  ['hu', 'Mért jellemzők: flame appearance, extinction · Érzékelők: video, IR', 'Mért jellemzők: growth · Érzékelők: nincs megadva']
]) {
  context.setLang(lang); context.renderCoverage();
  const rows = box.children.filter(x => x.className === 'cov-row');
  assert.equal(rows.length, 2);
  assert.equal(rows[0].children[2].textContent, expected);
  assert.equal(rows[1].children[2].textContent, missing);
}
context.catalog.environments.moon = {g_fraction: 0.165};
context.S.environment = 'moon';
context.result.inputs = {pressure_kpa: 56.5, o2_pct: 34};
context.flameCtx.habitats = [{id: 'moon-base', name: 'Lunar surface habitat', o2Pct: [30, 34], pressureKPa: [56.5, 70.3]}];
context.flameCtx.insights = {'moon-base': [{text: 'Original insight.', cited: ['PSI-25', 'NTRS 20130010991']}]};
context.flameCtx.investigations = [{accession: 'PSI-25', psiUrl: 'https://psi.nasa.gov/experiment/25'}];
context.setLang('hu'); context.renderCoverage();
assert(box.children.some(x => x.className === 'insights-title' && x.textContent === 'Mit mutatnak a kísérletek'));
const insight = box.children.find(x => x.className === 'insight');
assert.equal(insight.children[0].textContent, 'Original insight.');
assert.equal(insight.children[1].children[0].href, 'https://psi.nasa.gov/experiment/25');
assert.equal(insight.children[1].children[2].href, 'https://ntrs.nasa.gov/citations/20130010991');
context.result.inputs.o2_pct = 10; context.renderCoverage();
assert(!box.children.some(x => x.className === 'insights-title'));
"""
    subprocess.run([node, "-e", script], cwd=ROOT, check=True, capture_output=True, text=True)
