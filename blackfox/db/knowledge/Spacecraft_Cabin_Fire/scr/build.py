# Builds ../spacecraft_cabin_fire.html: shared styles from the 3D habitat page + ship_body.html + solver.js
import pathlib
here=pathlib.Path(__file__).parent
app=(here.parent.parent/"fire_sim"/"src"/"app.html").read_text(encoding="utf-8")
css=app[:app.index("</style>")]
css=css.replace("<title>Habitat Fire Spread</title>","<title>Spacecraft Cabin Fire</title>")
css=css.replace("/* Layout: instrument panel. 3D/slice viewport left, controls right; tracker, validation, maps, model and sources below. */",
                "/* Layout: instrument panel. Spacecraft cutaway left, fire-origin and cabin controls right; compartments, materials, validation below. */")
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
.advice li{max-width:95ch}
.advice li button{margin-left:6px;padding:2px 9px;font-size:12px}
.advice li button:disabled{opacity:.6;cursor:default}
.adv-notes{margin:0;padding-left:18px;display:grid;gap:4px;font-size:12.5px;color:var(--muted)}
.adv-src{margin:0;font-size:11.5px;color:var(--muted)}
.adv-src a{color:var(--accent)}
.labels span{background:rgba(10,14,22,0.7);color:#e8eef6}
"""
body=(here/"ship_body.html").read_text(encoding="utf-8")
sol=(here/"solver.js").read_text(encoding="utf-8")
assert "</script" not in sol
out=css+extra+"</style>"+chr(10)+body.replace("/*__SOLVER__*/",sol)
(here.parent/"spacecraft_cabin_fire.html").write_text(out,encoding="utf-8")
print("built",len(out),"bytes")
