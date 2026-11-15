# Adds a 2D mode to ship_body.html: build.py sets MODE2D=true for the 2D page (layout 'ship2d', section view, crew drawn on the section).
import pathlib
p=pathlib.Path(__file__).parent/'ship_body.html'
s=p.read_text(encoding='utf-8')
def rep(a,b):
    global s
    assert a in s, 'missing: '+a[:80]
    s=s.replace(a,b,1)
rep('          Port ↔ starboard <input type="range" id="sdepth"','          <span id="sdLbl">Port ↔ starboard</span> <input type="range" id="sdepth"')
rep("const P={g:0, X:21, Pk:101.3, U:40, vent:true};",
"""const MODE2D=/*__MODE2D__*/false;
const P={g:0, X:21, Pk:101.3, U:40, vent:true};""")
rep("speed=8, h=0.15, view='3d',","speed=8, h=MODE2D?0.075:0.15, view=MODE2D?'slice':'3d',")
rep("  worker.postMessage({cmd:'init', h, params:Object.assign({},P), mats,","  worker.postMessage({cmd:'init', h, params:Object.assign({},P,{layout:MODE2D?'ship2d':'ship'}), mats,")
rep("function initThree(){\n","""function initThree(){
  if(MODE2D){ threeOK=false; $('views').hidden=true; setView('slice'); return; }
""")
rep("  if(view==='slice'){ fit(sc_,LXR); drawSlice(); }","  if(view==='slice'){ fit(sc_, MODE2D&&G? G.info.nx/G.info.ny : LXR); drawSlice(); }")
rep("tile('Heat release now',`${hrr.toFixed(1)} kW`)","tile(MODE2D?'Heat release (slice)':'Heat release now',`${hrr.toFixed(MODE2D?2:1)} kW`)")
rep("auto.flameSprites=flames.filter(f=>f.visible).length;","auto.flameSprites=MODE2D? G.fuelList.filter(k=>F.fst[k]===2).length : flames.filter(f=>f.visible).length;")
# crew and vent valves drawn on the section
rep("  sx.font=`600 ${Math.max(10,cs*0.9)}px IBM Plex Sans Condensed, sans-serif`; sx.fillStyle=CSS.ink; sx.textAlign='center';",
"""  const zc=(l-0.5)*I.h;
  if(F.valves) G.VALVES.forEach((vl,vi)=>{ if(!F.valves[vi]) return; for(const k of vl.cells){ const i=k%I.nx, j=Math.floor(k/I.nx)%I.ny, ll=Math.floor(k/(I.nx*I.ny)); if(ll!==l) continue;
    sx.strokeStyle='#ff3b30'; sx.lineWidth=2; sx.strokeRect(ox+i*cs+1,oy+(I.ny-1-j)*cs+1,cs-2,cs-2); } });
  if(F.crew) for(const c of F.crew){ if(!MODE2D&&Math.abs(c.pos[2]-zc)>0.6) continue; const X=ox+(c.pos[0]/I.h+1)*cs, Y=oy+(I.ny-1-c.pos[1]/I.h)*cs, r=Math.max(5,cs*1.4);
    sx.beginPath(); sx.arc(X,Y,r,0,7); sx.fillStyle=crewColor(c); sx.fill(); sx.lineWidth=1.5; sx.strokeStyle=CSS.ink; sx.stroke();
    if(c.state==='incapacitated'){ sx.beginPath(); sx.moveTo(X-r*0.6,Y-r*0.6); sx.lineTo(X+r*0.6,Y+r*0.6); sx.moveTo(X+r*0.6,Y-r*0.6); sx.lineTo(X-r*0.6,Y+r*0.6); sx.strokeStyle='#fff'; sx.lineWidth=2; sx.stroke(); }
    sx.font=`600 ${Math.max(9,cs*1.2)}px IBM Plex Mono, monospace`; sx.fillStyle=CSS.ink; sx.textAlign='center'; sx.fillText(c.id+(c.mask?' ◍':''),X,Y-r-3); }
  sx.font=`600 ${Math.max(10,cs*0.9)}px IBM Plex Sans Condensed, sans-serif`; sx.fillStyle=CSS.ink; sx.textAlign='center';""")
# texts and controls specific to the 2D page
rep("pre.children[0].classList.add('on');","""pre.children[0].classList.add('on');
if(MODE2D){ document.querySelector('h1').textContent='Spacecraft Cabin Fire · 2D section';
  document.querySelector('.lede').textContent='A 2D vertical section along the spacecraft: the Lab module aisle with the avionics rack bay under the deck, the Node with two crew quarters and a galley, and the Airlock. It uses the same engine as the 3D model: Navier–Stokes airflow, mixing-controlled combustion, P1 radiation, heat conduction into thick panels, CO, HCN and HF, CO₂ and water-mist extinguishers, venting to vacuum, and four crew members who move and breathe the smoke. The slice is one cell deep and every item spans it, so heat release is per slice. The finer 7.5 cm cells show flame spread in more detail than the 3D model.';
  $('res').innerHTML='<option value="0.075">7.5 cm cells (fast)</option><option value="0.05">5 cm cells (finer)</option>';
  for(const id of ['sdLbl','sdepth','sdepthOut']) $(id).hidden=true;
  $('barSlice').querySelector('span:last-child').textContent='Click an item to ignite it, or a hatch or door to close or open it. Circles are the crew.'; }""")
p.write_text(s,encoding='utf-8'); print('2D mode patched')
