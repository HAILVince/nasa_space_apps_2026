# v5 page structure: response controls, time bar, crew, runs/compare/export, quiz, whole-model validation.
import pathlib
p=pathlib.Path(__file__).parent/'ship_body.html'
s=p.read_text(encoding='utf-8')
def rep(old,new,count=1):
    global s
    assert s.count(old)>=1, 'missing: '+old[:80]
    s=s.replace(old,new,count)

rep('<div class="eyebrow">Black Fox knowledge base · spacecraft fire safety · v4 physics</div>',
    '<div class="eyebrow">Black Fox knowledge base · spacecraft fire safety · v5 shared engine</div>')
rep("The physics is the same as the habitat model: Navier–Stokes airflow, mixing-controlled combustion and flame spread fitted to NASA BASS-II, Saffire and ISS PMMA data.</p>",
    "The engine solves Navier–Stokes airflow, mixing-controlled combustion, P1 radiation, heat conduction into thick panels, and the toxic gases CO, HCN and HF. It models CO₂ and water-mist extinguishers, venting to vacuum, and four crew members who move and breathe the smoke. It is checked against the Saffire flight fires.</p>")

# time bar under the 3D / slice bars
rep('''      <div class="notice" id="notice" hidden></div>''','''      <div class="vbar" id="timebar">
        <span class="btns" style="margin:0"><button type="button" id="ffIgn" title="Run as fast as possible until a flame appears">Skip to ignition</button><button type="button" id="ffAlarm">Skip to alarm</button><button type="button" id="ff60">+1 min</button><button type="button" id="ff300">+5 min</button><span class="foot" id="ffNote"></span></span>
        <span style="display:inline-flex;gap:8px;align-items:center;flex-wrap:wrap"><label><input type="checkbox" id="rpOn"> Replay</label><input type="range" id="rpT" min="0" max="0" step="5" value="0" disabled style="width:180px" aria-label="Replay time"><output id="rpOut" class="foot"></output></span>
      </div>
      <div class="notice" id="notice" hidden></div>''')

# slice fields
rep('<option value="U">Air speed</option></select>',
    '<option value="U">Air speed</option><option value="C">Carbon monoxide</option><option value="R">Radiation</option><option value="D">CO₂ agent</option><option value="W">Water mist</option></select>')

# response controls in the side panel (after the ignition explainer)
rep('''        <span class="sub">Open flame lights the item directly. Overheat heats it from inside at 15 kW/m² (smoulders and smokes) or 40 kW/m² (can ignite), as an overloaded wire would. Cut power stops the heating.</span>
      </div>''','''        <span class="sub">Open flame lights the item directly. Overheat heats it from inside at 15 kW/m² (smoulders and smokes) or 40 kW/m² (can ignite), as an overloaded wire would. Cut power stops the heating.</span>
      </div>
      <div class="field">
        <span class="eyebrow">Crew response</span>
        <div class="btns" style="margin-top:0">
          <button type="button" id="rsAlert">Alert crew</button>
          <button type="button" id="rsMasks">Masks on</button>
          <button type="button" id="rsCO2">CO₂ extinguisher</button>
          <button type="button" id="rsMist">Water-mist extinguisher</button>
        </div>
        <span class="sub">Extinguishers discharge at the selected fire origin: about 2.7 kg of CO₂ over 45 s, or 2 kg of fine water mist over 50 s. Masks are oxygen-supplied breathing sets that last 15 minutes.</span>
        <label for="dpRoom" style="margin-top:6px">Emergency depressurisation</label>
        <div class="btns" style="margin-top:0"><select id="dpRoom" style="width:auto"><option value="lab">Lab module</option><option value="node">Node</option><option value="air">Airlock</option></select><button type="button" id="dpGo" class="danger">Vent to vacuum</button></div>
        <span class="sub">Last resort. Close the hatches first, or the whole vehicle vents. NASA tests found venting slow and able to fan a fire before it goes out (NTRS 20260003546).</span>
      </div>''')

# crew panel after tiles
rep('''  <div class="tiles" id="tiles"></div>''','''  <div class="tiles" id="tiles"></div>

  <section class="panel">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap"><h2>Crew</h2><span class="eyebrow">fractional effective dose, ISO 13571 / Purser</span></div>
    <p class="foot" style="margin:4px 0 8px">Each crew member breathes the gas at their position. Dose adds up from CO, HCN, low O₂ partial pressure and heat, with CO₂ speeding up breathing. A dose of 0.3 marks the start of impairment and 1 marks incapacitation. After an alarm the crew move to a safe module: about 15 s to react, or 60 s if asleep. A closed hatch blocks them.</p>
    <div class="crew" id="crew"></div>
  </section>''')

# runs / compare / export / scenario + quiz, before the materials table
rep('''  <section class="panel">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap"><h2>Materials on board</h2>''','''  <div class="grid2">
    <section class="panel">
      <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap"><h2>Compare runs</h2><span class="eyebrow">recorded every second of simulated time</span></div>
      <p class="foot" style="margin:4px 0 8px">Save the current run as A or B, change the scenario, run again, and compare. Every action you take is recorded with its time, so a saved scenario replays the same response.</p>
      <div class="btns" style="margin:0 0 8px"><button type="button" id="saveA">Save run as A</button><button type="button" id="saveB">Save run as B</button><button type="button" id="clearAB">Clear</button>
        <select id="cmpMetric" style="width:auto" aria-label="Metric to compare"><option value="hrr">Heat release, kW</option><option value="co">Highest CO, ppm</option><option value="vis">Lowest visibility, m</option><option value="T">Hottest gas, °C</option><option value="o2">Lowest O₂, %</option><option value="fed">Worst crew dose (FED)</option><option value="pk">Lowest cabin pressure, kPa</option></select></div>
      <canvas id="cmp" class="chart" aria-label="Comparison of saved runs"></canvas>
      <div class="legend" id="cmpLegend"></div>
      <div class="tablewrap"><table id="cmpTab"><thead><tr><th>Run</th><th>Scenario</th><th>Peak heat</th><th>Highest CO</th><th>Lowest visibility</th><th>Worst crew dose</th><th>Fire out</th></tr></thead><tbody></tbody></table></div>
    </section>
    <section class="panel">
      <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap"><h2>Export and scenarios</h2><span class="eyebrow">CSV · JSON</span></div>
      <p class="foot" style="margin:4px 0 8px">The CSV holds one row per simulated second: heat release, gas temperature, O₂, CO, HCN, HF, CO₂, visibility and pressure for each compartment, plus each crew member's dose. A scenario file stores the atmosphere, materials, items removed, hatch states and the timed list of actions.</p>
      <div class="btns" style="margin:0 0 8px"><button type="button" id="dlCSV">Download CSV</button><button type="button" id="dlScen">Save scenario</button><span class="foot" id="dlNote"></span></div>
      <label for="itemsOff">Items on board (untick to remove a fuel)</label>
      <div class="openings" id="itemsOn"></div>
      <label for="scenText" style="margin-top:8px">Load a scenario (paste JSON or choose a file)</label>
      <textarea id="scenText" rows="4" style="width:100%;font:12px var(--f-mono);border:1px solid var(--line);border-radius:4px;background:var(--panel);color:var(--ink);padding:6px" placeholder='{"atmosphere":{...},"materials":{...},"script":[...]}'></textarea>
      <div class="btns"><input type="file" id="scenFile" accept=".json,application/json" style="max-width:220px"><button type="button" id="scenLoad">Load scenario</button><span class="foot" id="scenNote"></span></div>
    </section>
  </div>

  <section class="panel quiz" id="quizPanel">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap"><h2>Training quiz</h2><span class="eyebrow" id="quizScore">score 0 / 0</span></div>
    <p class="foot" style="margin:4px 0 8px">Each round picks a random fire origin, material and cabin, runs it fast to the moment of decision, and asks for your first action. Your choice is then applied to the live simulation so you can watch the outcome.</p>
    <div class="btns" style="margin:0 0 8px"><button type="button" id="quizStart">Start a round</button></div>
    <div id="quizBody" class="foot">No round in progress.</div>
  </section>

  <section class="panel">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap"><h2>Materials on board</h2>''')

# whole-model validation, parity plot, convergence
rep('''    <div class="tablewrap"><table id="valid"><thead><tr><th>Check</th><th>Conditions</th><th>Measured</th><th>Model</th><th>Unit</th><th>Role</th><th>Source</th></tr></thead><tbody></tbody></table></div>
  </section>''','''    <div class="tablewrap"><table id="valid"><thead><tr><th>Check</th><th>Conditions</th><th>Measured</th><th>Model</th><th>Unit</th><th>Role</th><th>Source</th></tr></thead><tbody></tbody></table></div>
    <h3 style="margin:16px 0 4px">Whole-model check: Saffire fires in a Cygnus-sized cabin</h3>
    <p class="foot" style="margin:0 0 8px">The full 3D engine runs each Saffire test. A sample sits in a 20 cm/s flow duct inside a sealed cabin of the measured free volume, and the engine predicts spread, heat release, the cabin CO rise, the pressure rise and the time to the 2 mg/m³ smoke alarm. Calibrated on IV-1: the 0 g CO and smoke yields of cotton fabrics, and the cargo heat sink. Everything else is a prediction. Computed offline with <code>fire_core/validate_saffire.js</code> on 10 cm cells.</p>
    <div class="tablewrap"><table id="saffTab"><thead><tr><th>Test</th><th>Atmosphere</th><th>Spread, mm/s</th><th>Mean heat, kW</th><th>Cabin CO rise, ppm</th><th>Pressure rise, Pa</th><th>Smoke alarm, s</th></tr></thead><tbody></tbody></table></div>
    <div class="grid2" style="margin-top:10px">
      <div><h3 style="margin:0 0 4px">Predicted vs measured</h3><canvas id="parity" class="chart" aria-label="Model against measurement for every independent check"></canvas>
        <div class="legend"><span><i class="dotk" style="background:var(--accent)"></i>flame and spread sub-model</span><span><i class="dotk" style="background:var(--crit)"></i>whole 3D model (Saffire)</span><span><i class="sw" style="background:var(--muted)"></i>±30% and ±2×</span></div></div>
      <div><h3 style="margin:0 0 4px">Grid convergence (Saffire IV-1)</h3><canvas id="conv" class="chart" aria-label="Results against cell size"></canvas><p class="foot" id="convNote" style="margin:4px 0 0"></p></div>
    </div>
  </section>''')

# model description additions
rep('''      <li><b>Electrical overheat.</b>''','''      <li><b>Radiation (P1).</b><span class="eq">−∇·(∇G / 3κ) + κG = 4κσT⁴ (or χ<sub>r</sub>q̇‴ in flames),  κ = 0.03 + 1862 f<sub>v</sub>T + κ<sub>gas</sub>,  walls: −Γ∂G/∂n = ε/(2(2−ε)) (G − 4σT<sub>w</sub>⁴)</span><p>Radiation from flames and soot heats nearby surfaces and is absorbed by walls, so far-off items can preheat.</p></li>
      <li><b>Thick panels.</b><span class="eq">ρc ∂T/∂t = k ∂²T/∂x²  (8 nodes, implicit),  burning: ṁ″ = (q̇″<sub>flame</sub> + q̇″<sub>rad</sub> − k ∂T/∂x|<sub>s</sub>)/L<sub>g</sub></span><p>PMMA, polycarbonate and silicone heat up through their depth. Concurrent spread on them follows V = k<sub>t</sub> U q̇″²/(kρc ΔT²), calibrated to Saffire VI-3.</p></li>
      <li><b>Toxic products.</b><span class="eq">Y<sub>CO</sub> = y<sub>0g</sub> + (y<sub>1g</sub> − y<sub>0g</sub>)√(g/g₀), rising toward 0.2 when the compartment runs short of O₂;  smoke ∝ P</span><p>Flames in 0 g make far more CO than on Earth. Saffire cotton fabrics gave about 0.034 kg/kg, against 0.004 in 1 g. Overheated PTFE gives off HF.</p></li>
      <li><b>Suppression and venting.</b><span class="eq">CO₂: dilutes O₂ and raises heat capacity (X<sub>eff</sub> = X/(1 + 0.6x<sub>CO₂</sub>));  mist: evaporates on available heat, wets surfaces;  vent: dP/dt = −P C<sub>d</sub>A c*/V</span></li>
      <li><b>Crew dose.</b><span class="eq">FED = Σ[2.76·10⁻⁵ CO¹·⁰³⁶ + (e<sup>HCN/43</sup>/220 − 0.0045)] v<sub>CO₂</sub> Δt + Σ Δt/e<sup>8.13−0.54(20.9−O₂)</sup> + Σ Δt/(5·10⁷ T<sup>−3.4</sup>)</span><p>Times in minutes and concentrations at sea-level-equivalent partial pressure, so a depressurised module is lethal through hypoxia.</p></li>
      <li><b>Electrical overheat.</b>''')

# limitations
rep('''        <li>Cells of 12–15 cm cannot resolve a flame. Surface flames are subgrid models, and a burning item is at least one cell in size.</li>
        <li>There is no toxic-gas chemistry (CO, HCN, HF from PTFE) and no extinguisher or depressurisation response. Smoke is soot only.</li>''','''        <li>Cells of 12–15 cm cannot resolve a flame. Surface flames are subgrid models, and a burning item is at least one cell in size. The grid-convergence check shows how far results move with cell size.</li>
        <li>Toxic gases come from fixed yields, not chemistry. Only cellulose fabrics have measured 0 g CO and smoke yields (Saffire). Other materials use 6× their 1 g CO yield and their 1 g smoke yield.</li>
        <li>Extinguisher and mist amounts are representative, not hardware specifications. The discharge is a volume source near the item, not a resolved jet.</li>
        <li>Against Saffire, the model underpredicts the IV-1 spread rate by about 40% and overpredicts cotton spread by about 70%. It sounds the smoke alarm 2–4× too early at reduced pressure.</li>
        <li>Crew behaviour is a simple rule: react, then move to the other module. Real crews follow procedures and fight the fire.</li>''')

p.write_text(s,encoding='utf-8'); print('html patched', len(s))
