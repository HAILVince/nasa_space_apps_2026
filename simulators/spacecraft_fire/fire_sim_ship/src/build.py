# Builds ../spacecraft_cabin_fire.html (3D) and ../spacecraft_cabin_fire_2d.html (2D section) from:
#   base_style.html (shared page styles) + ship_body.html (page, 3D and 2D modes)
#   fire_core/layouts.js + fire_core/engine.js (the shared v5 engine)  → solver-src
#   worker_v5.js (Web Worker driver)                                      → worker-src
#   fire_core/validation_results.json (whole-model Saffire validation, computed offline by validate_saffire.js)
import pathlib, json
here=pathlib.Path(__file__).parent
core=here.parent.parent/"fire_core"
css=(here/"base_style.html").read_text(encoding="utf-8")   # shared page styles (head + <style> up to its closing tag)
css=css.replace("<title>Habitat Fire Spread</title>","<title>Spacecraft Cabin Fire</title>")
css=css.replace("/* Layout: instrument panel. 3D/slice viewport left, controls right; tracker, validation, maps, model and sources below. */",
                "/* Layout: instrument panel. Spacecraft cutaway left, fire-origin, response and cabin controls right; crew, compartments, runs, quiz, materials, validation below. */")
extra = """
.assess{display:grid;gap:6px;font-size:13px;border:1px solid var(--line);border-radius:5px;padding:8px 10px;margin-top:6px;background:var(--hab)}
.verdict{font-family:var(--f-display);font-weight:700;font-size:16px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:1px 10px;margin:0;font-size:12px}
.kv dt{color:var(--muted)} .kv dd{margin:0;text-align:right;font-family:var(--f-mono);font-variant-numeric:tabular-nums}
#vp3d{aspect-ratio:2.2/1;background:#02040a}
.hud{position:absolute;left:10px;top:10px;font:12px/1.5 var(--f-mono);color:#dfe8f5;background:rgba(6,10,18,0.62);border:1px solid rgba(160,190,230,0.25);border-radius:5px;padding:6px 10px;pointer-events:none;max-width:60%}
.hud b{color:#ffffff;font-weight:600}
.leds{display:flex;gap:6px;margin-top:4px;flex-wrap:wrap}
.led{display:inline-flex;align-items:center;gap:4px;font-size:11px;letter-spacing:.04em}
.led::before{content:"";width:8px;height:8px;border-radius:50%;background:#56606c}
.led.on::before{background:#4cc28a;box-shadow:0 0 6px #4cc28a} .led.warn::before{background:#ffb347;box-shadow:0 0 6px #ffb347} .led.crit::before{background:#ff5a4a;box-shadow:0 0 8px #ff5a4a}
.advice{--sev:var(--accent);margin-top:12px;border:1px solid var(--line);border-left:6px solid var(--sev);border-radius:6px;padding:12px 14px;display:grid;gap:8px;background:var(--panel)}
.advice.lv-act,.advice.lv-evac{--sev:var(--crit)} .advice.lv-clear{--sev:var(--ok)} .advice.lv-info{--sev:var(--accent)}
.advice.lv-evac{background:color-mix(in srgb,var(--crit) 7%,var(--panel))}
.adv-head{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.adv-head h2{font-size:18px}
.sev{font:700 11px var(--f-mono);letter-spacing:.07em;text-transform:uppercase;padding:3px 8px;border-radius:3px;color:var(--panel);background:var(--sev)}
.adv-what{margin:0;max-width:95ch}
.advice ol{margin:0;padding-left:22px;display:grid;gap:6px}
.advice li{max-width:95ch} .advice li.warn{color:var(--crit)}
.advice li button{margin-left:6px;padding:2px 9px;font-size:12px}
.advice li button:disabled{opacity:.6;cursor:default}
.adv-notes{margin:0;padding-left:18px;display:grid;gap:4px;font-size:12.5px;color:var(--muted)}
.adv-src{margin:0;font-size:11.5px;color:var(--muted)}
.adv-src a{color:var(--accent)}
.labels span{background:rgba(10,14,22,0.7);color:#e8eef6}
.labels span.crew-l{border:1.5px solid #4cc28a;border-radius:10px;padding:0 6px;font-size:10.5px}
#timebar{border-top:1px dashed var(--line)}
#timebar button{padding:3px 9px;font-size:12px}
.crew{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
.cm{border:1px solid var(--line);border-left:5px solid var(--ok);border-radius:5px;padding:8px 10px;background:var(--hab);display:grid;gap:6px;font-size:12.5px}
.cm .nm{display:flex;justify-content:space-between;gap:8px;font-weight:600;flex-wrap:wrap} .cm .st{font:600 11.5px var(--f-mono)}
.cm dl{display:grid;grid-template-columns:auto 1fr;gap:1px 10px;margin:0} .cm dt{color:var(--muted)} .cm dd{margin:0;text-align:right;font-family:var(--f-mono);font-variant-numeric:tabular-nums}
.fedbar{position:relative;height:8px;border-radius:4px;background:color-mix(in srgb,var(--ink) 10%,transparent);overflow:hidden}
.fedbar i{position:absolute;left:0;top:0;bottom:0;border-radius:4px} .fedbar b{position:absolute;top:0;bottom:0;width:1px;background:var(--ink);opacity:.5}
.quiz #quizBody p{margin:4px 0;max-width:95ch} .quiz #quizBody .btns button{font-size:12.5px}
h3{font-family:var(--f-display);font-size:15px}
textarea{box-sizing:border-box;max-width:100%}
"""
body=(here/"ship_body.html").read_text(encoding="utf-8")
sol=(core/"layouts.js").read_text(encoding="utf-8")+"\n"+(core/"engine.js").read_text(encoding="utf-8")
wk=(here/"worker_v5.js").read_text(encoding="utf-8")
vpath=core/"validation_results.json"
val="null"
if vpath.exists():
    v=json.loads(vpath.read_text(encoding="utf-8"))
    for T in v.get("tests",[]): T["model"].pop("series",None)
    val=json.dumps(v,ensure_ascii=False)
for name,x in (("solver",sol),("worker",wk),("validation",val)): assert "</script" not in x, name
for ph in ("/*__SOLVER__*/","/*__WORKER__*/","/*__SAFFIRE__*/null"): assert ph in body, ph
assert "/*__MODE2D__*/false" in body
for fname,mode2d,title in (("spacecraft_cabin_fire.html",False,"Spacecraft Cabin Fire"),("spacecraft_cabin_fire_2d.html",True,"Spacecraft Fire 2D")):
    page=body.replace("/*__SOLVER__*/",sol).replace("/*__WORKER__*/",wk).replace("/*__SAFFIRE__*/null",val).replace("/*__MODE2D__*/false","true" if mode2d else "false")
    out=css.replace("<title>Spacecraft Cabin Fire</title>",f"<title>{title}</title>")+extra+"</style>"+chr(10)+page
    (here.parent/fname).write_text(out,encoding="utf-8")
    print("built",fname,len(out),"bytes; validation", "embedded" if val!="null" else "missing")
