# Derives the 2D page (app2d.html) from the 3D project's app.html, then the build step inlines solver.js.
# Kept as a script so both pages share panels, validation, maps and sources.
import pathlib, re
here = pathlib.Path(__file__).parent
s = (here.parent.parent / "fire_sim" / "src" / "app.html").read_text(encoding="utf-8")

def rep(a, b, count=1):
    global s
    n = s.count(a)
    assert n == count, (n, a[:90])
    s = s.replace(a, b)

def cut(start, end, new):
    global s
    i = s.index(start); j = s.index(end, i)
    s = s[:i] + new + s[j:]

rep("<title>Habitat Fire Spread</title>", "<title>Habitat Fire Section</title>")
rep('<div class="eyebrow">Black Fox knowledge base · 0 g / Moon / Mars · v4</div>\n    <h1>Habitat Fire Spread</h1>',
    '<div class="eyebrow">Black Fox knowledge base · 0 g / Moon / Mars · v4, 2D edition</div>\n    <h1>Habitat Fire Section</h1>')
cut('<p class="lede">A 3D fire model', '</p>',
    '<p class="lede">A 2D side section through a 6 m × 3 m two-deck habitat with six rooms, solved on cells down to 2.5 cm. '
    'It uses the same physics as the 3D model: variable-density Navier–Stokes with buoyancy and thermal expansion, mixing-controlled combustion, '
    'and flame spread fitted to NASA BASS-II, Saffire and ISS PMMA data, then checked against LUCI Lunar-gravity results. '
    'Each cell stands for the module\'s full 2 m depth (a depth-averaged section), so it runs faster and shows finer flame and plume detail than the 3D view.')
# viewport: single 2D canvas
cut('          <span class="chips" id="views">', '<button id="play"', '')
cut('      <div class="viewport" id="vp3d">', '      <div class="notice" id="notice" hidden></div>',
'''      <div class="viewport" id="vp2d"><canvas id="sec" aria-label="Side section of the habitat fire"></canvas></div>
      <div class="vbar">
        <span style="display:inline-flex;gap:8px;align-items:center;flex-wrap:wrap">Field
          <select id="sfield" style="width:auto"><option value="T">Temperature</option><option value="S">Smoke (visibility)</option><option value="O">Oxygen</option><option value="U">Air speed</option></select>
        </span>
        <span style="display:inline-flex;gap:12px;flex-wrap:wrap">
          <label><input type="checkbox" id="lySmoke" checked> smoke</label>
          <label><input type="checkbox" id="lyFlow"> airflow</label>
          <label><input type="checkbox" id="lyRings" checked> front rings</label>
        </span>
      </div>
      <div class="hintline foot" style="margin-top:4px">Click a furnishing or wall lining to set it alight. Click a door or hatch to close it (blue) or open it again.</div>
''')
rep('<select id="res"><option value="0.125">Coarse, 12.5 cm cells (fast)</option><option value="0.1">Medium, 10 cm cells</option><option value="0.0833">Fine, 8.3 cm cells (slow)</option></select>',
    '<select id="res"><option value="0.05">5 cm cells (fast)</option><option value="0.04">4 cm cells</option><option value="0.025">2.5 cm cells (slow, most detail)</option></select>')
# model section and limitations
rep('<p>Each step (Δt up to 0.25 s, about two cell crossings) solves these equations on the 3D grid. They follow the structure of NIST\'s Fire Dynamics Simulator, simplified where the browser needs it.</p>',
    '<p>Each step (Δt up to 0.25 s, about two cell crossings) solves these equations on a vertical x–y section with zero flux through the front and back faces. '
    'The section is depth-averaged: a furnishing narrower than the 2 m module depth releases fuel vapour in proportion to its width, and heat release is scaled to the full depth. '
    'The equations follow the structure of NIST\'s Fire Dynamics Simulator, simplified where the browser needs it.</p>')
rep('<li>It is not FDS. Cells of 8–12.5 cm cannot resolve a millimetre-thick flame, so surface flames are subgrid models fitted to the data in the validation table.</li>',
    '<li>It is 2D: every door and hatch spans the full module depth, and there is no sideways (front-to-back) flow. Use the 3D version for those effects.</li>'
    '<li>It is not FDS. Even 2.5 cm cells cannot resolve a millimetre-thick flame, so surface flames are subgrid models fitted to the data in the validation table.</li>')
# scripts: no three.js
rep('<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>\n', '')
# worker: 2D solver, finer grids, send ignition times for front rings
rep("S=createSolver(Object.assign({h:m.h,iters:m.h<0.1?24:20},m.params));", "S=createSolver(Object.assign({dim:2,h:m.h,iters:m.h<0.03?40:30},m.params));")
rep("const T=f32(S.T), YS=f32(S.YS), YO=f32(S.YO), u=f32(S.u), v=f32(S.v), w=f32(S.w), fst=S.fst.slice();",
    "const T=f32(S.T), YS=f32(S.YS), YO=f32(S.YO), u=f32(S.u), v=f32(S.v), w=f32(S.w), fst=S.fst.slice(), igT=f32(S.igT);")
rep("T,YS,YO,u,v,w,fst},[T.buffer,YS.buffer,YO.buffer,u.buffer,v.buffer,w.buffer,fst.buffer]);",
    "T,YS,YO,u,v,w,fst,igT},[T.buffer,YS.buffer,YO.buffer,u.buffer,v.buffer,w.buffer,fst.buffer,igT.buffer]);")
rep("const fi = cfg && cfg.h<0.1 ? 220 : 120;", "const fi = cfg && cfg.h<0.03 ? 200 : 110;")
# default ignition: the Galley wall lining (creeping spread up the wall and onto the ceiling)
rep("function defaultIgnite(){ const gal=S.ROOMS.findIndex(r=>r.id==='gal'), pk=S.MKEYS.indexOf('paper');\n  const c=S.fuelList.filter(k=>S.room[k]===gal&&S.mat[k]===pk); if(c.length) S.ignite(c[Math.floor(c.length/2)]); }",
    "function defaultIgnite(){ const gal=S.ROOMS.findIndex(r=>r.id==='gal'), pk=S.MKEYS.indexOf('paper');\n  const c=S.fuelList.filter(k=>S.room[k]===gal&&S.mat[k]===pk).sort((a,b)=>a-b); if(c.length) S.ignite(c[c.length-1]); }")
# main script: replace 3D scene + slice with the 2D section renderer
cut("// ---------------- 3D scene ----------------", "const xvol=y=>",
r'''// ---------------- 2D section view ----------------
const sec=$('sec'), sx=sec.getContext('2d');
let view='2d';
const HS=()=> G? 2/G.info.h : 1;      // depth-averaged: heat release of one cell × (2 m / cell depth)
function heatColor(T){ const x=Math.min(1,Math.max(0,(T-330)/1100)); return [Math.min(1,0.6+x*0.8), Math.min(1,0.15+x*0.9*x+0.1), Math.max(0,0.05+(x-0.75)*1.6)]; }
function geomBox(){ const I=G.info, W=sec.width, H=sec.height, cs=Math.min(W/I.nx,H/I.ny); return {I,W,H,cs,ox:(W-cs*I.nx)/2,oy:(H-cs*I.ny)/2}; }
function ringStep(t){ const span=Math.max(10,t); for(const d of [5,10,15,20,30,60,120,300]) if(span/d<=10) return d; return 300; }
function drawSection(){
  if(!G||!F) return;
  const {I,W,H,cs,ox,oy}=geomBox(), l=1, field=$('sfield').value, kk=(i,j)=>i+I.nx*(j+I.ny*l), Y=j=>oy+(I.ny-1-j)*cs;
  sx.fillStyle=CSS.view; sx.fillRect(0,0,W,H);
  const smoke=$('lySmoke').checked;
  for(let j=0;j<I.ny;j++) for(let i=0;i<I.nx;i++){ const k=kk(i,j), t=G.typeArr[k]; if(t!==0) continue; const X=ox+i*cs, YY=Y(j);
    let col=null;
    if(field==='T'){ const T=F.T[k]; if(T>305){ const [r,g,b]=heatColor(T); col=`rgba(${r*255|0},${g*255|0},${b*255|0},${Math.min(0.95,(T-300)/500)})`; } }
    else if(field==='O'){ const d=P.X-xvol(F.YO[k]); if(d>0.1) col=`rgba(47,111,214,${Math.min(0.85,d/10)})`; }
    else if(field==='U'){ const sp=Math.hypot(F.u[k],F.v[k]); if(sp>0.01) col=`rgba(36,69,168,${Math.min(0.8,sp/1.0)})`; }
    if(col){ sx.fillStyle=col; sx.fillRect(X,YY,cs+0.6,cs+0.6); }
    if(smoke||field==='S'){ const K=8700*1.1*F.YS[k]; if(K>0.01){ sx.fillStyle=`rgba(96,96,104,${Math.min(field==='S'?0.9:0.6,K/(field==='S'?1.5:2.5))})`; sx.fillRect(X,YY,cs+0.6,cs+0.6); } } }
  // walls, openings, fuel
  for(let j=0;j<I.ny;j++) for(let i=0;i<I.nx;i++){ const k=kk(i,j), t=G.typeArr[k], X=ox+i*cs, YY=Y(j);
    if(G.openId[k]>=0 && t!==2){ if(!F.opens[G.openId[k]]){ sx.fillStyle=CSS.accent; sx.fillRect(X,YY,cs+0.6,cs+0.6); } else { sx.fillStyle=rgba(CSS.accent,0.18); sx.fillRect(X,YY,cs+0.6,cs+0.6); } continue; }
    if(t===1){ sx.fillStyle=CSS.wall; sx.fillRect(X,YY,cs+0.6,cs+0.6); continue; }
    if(t===2){ const s=F.fst[k]; let col;
      if(s===2) col=null;
      else if(s===3||s===4){ const age=F.igT[k]>=0? F.t-F.igT[k] : 999; const e=Math.max(0,1-age/90); col=`rgb(${Math.round(43+150*e)},${Math.round(38+40*e)},${Math.round(34-10*e)})`; }
      else if(s===1){ const T=F.T[k]; const x=Math.min(1,Math.max(0,(T-300)/350)); col=`rgb(${Math.round(200+55*x)},${Math.round(170-70*x)},${Math.round(120-90*x)})`; }
      else col=MATCOL[G.MKEYS[G.mat[k]]]||'#ccc';
      if(col){ sx.fillStyle=col; sx.fillRect(X,YY,cs+0.6,cs+0.6); } } }
  // vents
  sx.fillStyle= P.vent&&P.U>0? CSS.accent : CSS.muted;
  for(let j=0;j<I.ny;j++){ if(G.sup[kk(1,j)]) sx.fillRect(ox,Y(j),cs*0.6,cs+0.6); if(G.ret[kk(I.nx-2,j)]) sx.fillRect(ox+(I.nx-0.6)*cs,Y(j),cs*0.6,cs+0.6); }
  // front rings: where the flame front was every few seconds
  if($('lyRings').checked && F.igns.length){ const dT=ringStep(F.t); sx.strokeStyle=rgba(CSS.accent,0.95); sx.lineWidth=Math.max(1,cs*0.22); sx.beginPath();
    for(let j=1;j<I.ny-1;j++) for(let i=1;i<I.nx-1;i++){ const k=kk(i,j), a=F.igT[k]; if(a<0||G.typeArr[k]!==2) continue; const b=Math.floor(a/dT);
      for(const [di,dj] of [[1,0],[0,1]]){ const n=kk(i+di,j+dj), c=F.igT[n]; if(G.typeArr[n]!==2||c<0||Math.floor(c/dT)===b) continue;
        const x=ox+(i+0.5+di*0.5)*cs, y=Y(j)+cs*0.5-dj*cs*0.5; if(di){ sx.moveTo(x,y-cs*0.6); sx.lineTo(x,y+cs*0.6); } else { sx.moveTo(x-cs*0.6,y); sx.lineTo(x+cs*0.6,y); } } }
    sx.stroke(); }
  // flames: glow stretched along the local flow and buoyancy, bluer and rounder in weak flow
  sx.globalCompositeOperation='lighter';
  for(let j=1;j<I.ny-1;j++) for(let i=1;i<I.nx-1;i++){ const k=kk(i,j); if(G.typeArr[k]!==2||F.fst[k]!==2) continue;
    let ux=0,uy=0,c=0; for(const [di,dj] of [[1,0],[-1,0],[0,1],[0,-1]]){ const n=kk(i+di,j+dj); if(G.typeArr[n]===0){ ux+=F.u[n]; uy+=F.v[n]; c++; } } if(c){ ux/=c; uy/=c; }
    const U=Math.hypot(ux,uy)*100, blue=1-Math.min(1,U/25), stretch=Math.min(3,0.8+U/12), fl=0.8+Math.random()*0.4, r=cs*2.2*fl;
    sx.save(); sx.translate(ox+(i+0.5)*cs, Y(j)+cs*0.5); if(U>0.5){ sx.rotate(Math.atan2(-uy,ux)); sx.translate(r*0.4*(stretch-0.8),0); sx.scale(stretch,1); }
    const gr=sx.createRadialGradient(0,0,0,0,0,r);
    gr.addColorStop(0,`rgba(255,${Math.round(235-50*blue)},${Math.round(170+80*blue)},${0.95-0.35*blue})`);
    gr.addColorStop(0.5,`rgba(${Math.round(255-170*blue)},${Math.round(140+10*blue)},${Math.round(30+225*blue)},${0.5-0.2*blue})`);
    gr.addColorStop(1,'rgba(0,0,0,0)'); sx.fillStyle=gr; sx.beginPath(); sx.arc(0,0,r,0,Math.PI*2); sx.fill(); sx.restore(); }
  sx.globalCompositeOperation='source-over';
  // airflow arrows
  if($('lyFlow').checked){ sx.strokeStyle=rgba(CSS.ink,0.55); sx.lineWidth=1; const st=Math.max(2,Math.round(0.25/I.h));
    for(let j=1;j<I.ny-1;j+=st) for(let i=1;i<I.nx-1;i+=st){ const k=kk(i,j); if(G.typeArr[k]!==0) continue; const u=F.u[k], v=F.v[k], s=Math.hypot(u,v); if(s<0.02) continue;
      const L=cs*st*Math.min(1.1,0.35+s*1.5), x=ox+(i+0.5)*cs, y=Y(j)+cs*0.5, a=Math.atan2(-v,u), ex=x+Math.cos(a)*L, ey=y+Math.sin(a)*L, hd=Math.max(3,cs*0.8);
      sx.beginPath(); sx.moveTo(x,y); sx.lineTo(ex,ey); sx.lineTo(ex-Math.cos(a-0.5)*hd,ey-Math.sin(a-0.5)*hd); sx.moveTo(ex,ey); sx.lineTo(ex-Math.cos(a+0.5)*hd,ey-Math.sin(a+0.5)*hd); sx.stroke(); } }
  // labels
  const fs=Math.max(11,Math.min(15,cs*2.2));
  sx.font=`600 ${fs}px IBM Plex Sans Condensed, sans-serif`; sx.textAlign='left';
  G.ROOMS.forEach((r,ri)=>{ const st=F.stats[ri]; const x=ox+(r.x0/I.h+1.6)*cs, y=oy+(I.ny-1-(r.y1/I.h))*cs+fs*1.7;
    sx.fillStyle=ROOMC[ri]; sx.fillRect(x,y-fs*0.75,fs*0.6,fs*0.6); sx.fillStyle=CSS.ink; sx.fillText(r.name,x+fs*0.9,y);
    if(st&&st.flame>0){ sx.fillStyle=CSS.crit; sx.fillText('● fire', x+fs*0.9+sx.measureText(r.name+' ').width, y); } });
  sx.font=`${Math.max(10,fs*0.8)}px IBM Plex Mono, monospace`; sx.fillStyle=CSS.muted; sx.textAlign='right';
  sx.fillText(`${P.g>0?'g ↓ '+P.g.toFixed(3):'0 g'} · ${(I.h*100).toFixed(1)} cm cells`, W-ox-cs*2, H-oy-cs*1.5);
  if($('lyRings').checked && F.igns.length) sx.fillText(`rings every ${ringStep(F.t)} s`, W-ox-cs*2, oy+cs*2+fs);
}
sec.addEventListener('click',e=>{
  if(!G) return; const {I,W,H,cs,ox,oy}=geomBox(), r=sec.getBoundingClientRect();
  const px=(e.clientX-r.left)*W/r.width, py=(e.clientY-r.top)*H/r.height, i=Math.floor((px-ox)/cs), j=I.ny-1-Math.floor((py-oy)/cs), l=1;
  if(i<0||j<0||i>=I.nx||j>=I.ny) return; const kk=(a,b)=>a+I.nx*(b+I.ny*l);
  let hitO=-1,bo=3; for(let dj=-2;dj<=2;dj++)for(let di=-2;di<=2;di++){ const k=kk(i+di,j+dj); if(k>=0&&k<I.N&&G.openId[k]>=0&&G.typeArr[k]!==2){ const d=Math.hypot(di,dj); if(d<bo){bo=d;hitO=G.openId[k];} } }
  let best=-1,bd=12; const R=Math.max(2,Math.round(0.1/I.h)); for(let dj=-R;dj<=R;dj++)for(let di=-R;di<=R;di++){ const k=kk(i+di,j+dj); if(k>=0&&k<I.N&&G.typeArr[k]===2){ const d=di*di+dj*dj; if(d<bd){bd=d;best=k;} } }
  if(hitO>=0 && (best<0 || bo*bo<=bd)){ const o=G.OPEN[hitO]; send({cmd:'toggle',oi:hitO}); addLog(-1,`${o.name} ${F.opens[hitO]?'closed':'opened'}`); return; }
  if(best>=0){ send({cmd:'ignite',k:best}); if(!running){ running=true; syncPlay(); send({cmd:'run',running,speed}); } }
});
''')
# frame handler: no 3D updates; heat release scaled to full depth
rep("  updateOpenMesh(); updateScene();\n", "")
rep("if(t-lastStatsT>=1 || t<lastStatsT){ hist.push([t,...st.map(r=>r.hrr/1000)]);", "if(t-lastStatsT>=1 || t<lastStatsT){ hist.push([t,...st.map(r=>r.hrr*HS()/1000)]);")
rep("const hrr=st.reduce((a,r)=>a+r.hrr,0)/1000,", "const hrr=st.reduce((a,r)=>a+r.hrr,0)*HS()/1000,")
rep("<dt>Heat release</dt><dd>${(R.now.hrr/1000).toFixed(1)} kW</dd>", "<dt>Heat release</dt><dd>${(R.now.hrr*HS()/1000).toFixed(1)} kW</dd>")
rep("peak_hrr_kW:R.peakHRR?+(R.peakHRR/1000).toFixed(2):null", "peak_hrr_kW:R.peakHRR?+(R.peakHRR*HS()/1000).toFixed(2):null")
rep("module:{id:'hab_2deck_3d',grid:{nx:G.info.nx,ny:G.info.ny,nz:G.info.nz,cell_cm:+(G.info.h*100).toFixed(2)}",
    "module:{id:'hab_2deck_section2d',grid:{nx:G.info.nx,ny:G.info.ny,cell_cm:+(G.info.h*100).toFixed(2),depth_averaged_m:2}")
rep("scenario_id:`blackfox_hab3d_g", "scenario_id:`blackfox_hab2d_g")
rep("assumptions:['3D LES-style solver,", "assumptions:['2D depth-averaged section (2 m module depth), LES-style solver,")
# controls: drop 3D-only handlers
rep("for(const b of $('views').children) b.onclick=()=>setView(b.dataset.v);\n", "")
cut("function setView(v){", "$('sfield').onchange=drawSlice;", "")
rep("$('sfield').onchange=drawSlice;", "$('sfield').onchange=drawSection;")
cut("  if(G){ $('sdepth').max=G.info.nz-2;", "    $('resnote').textContent=",
    "  if(G){\n")
rep("$('resnote').textContent=`${G.info.nx}×${G.info.ny}×${G.info.nz} = ${G.info.N.toLocaleString()} cells, ${G.fuelList.length.toLocaleString()} fuel surfaces.`;",
    "$('resnote').textContent=`${G.info.nx}×${G.info.ny} = ${(G.info.nx*G.info.ny).toLocaleString()} cells, ${G.fuelList.length.toLocaleString()} fuel surfaces.`;")
cut("function resize(){", "window.addEventListener('resize',resize);",
'''function resize(){
  readTokens();
  fit(sec,2); drawSection();
  fit($('growth'),4); drawMap(); drawGMap(); if(F) drawGrowth();
}
''')
rep("try{ matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{ resize(); if(G) buildScene(); }); }catch(_){}",
    "try{ matchMedia('(prefers-color-scheme: dark)').addEventListener('change',resize); }catch(_){}")
rep("new MutationObserver(()=>{ resize(); if(G) buildScene(); }).observe(", "new MutationObserver(resize).observe(")
rep("function loop(){ try{ render3d(); if(view==='slice') drawSlice(); }catch(err){", "function loop(){ try{ drawSection(); }catch(err){")
rep("  if(d.type==='geom'){ G=d; buildScene(); renderValidation();", "  if(d.type==='geom'){ G=d; resize(); renderValidation();")
rep("syncControls(); syncPlay(); initThree(); resize(); startSolver(); requestAnimationFrame(loop);",
    "syncControls(); syncPlay(); resize(); startSolver(); requestAnimationFrame(loop);")
rep("let G=null, F=null, worker=null, running=true, speed=8, h=0.125, view='3d';", "let G=null, F=null, worker=null, running=true, speed=8, h=0.05;")
rep('<span class="chips" id="speeds"><button type="button" data-s="2">×2</button><button type="button" data-s="8" class="on">×8</button><button type="button" data-s="32">×32</button></span>',
    '<span class="chips" id="speeds"><button type="button" data-s="4">×4</button><button type="button" data-s="16" class="on">×16</button><button type="button" data-s="64">×64</button></span>')
rep("let G=null, F=null, worker=null, running=true, speed=8, h=0.05;", "let G=null, F=null, worker=null, running=true, speed=16, h=0.05;")
# leftovers that referenced 3D objects
assert "THREE" not in s.split('<script>')[-1].replace("threeOK",""), "3D references remain"
(here / "app2d.html").write_text(s, encoding="utf-8")
(here / "build.py").write_text('''# Builds ../habitat_fire_section_2d.html from app2d.html + solver.js (run make_app2d.py first if the 3D app changed)
import pathlib
here=pathlib.Path(__file__).parent
app=(here/"app2d.html").read_text(encoding="utf-8"); sol=(here/"solver.js").read_text(encoding="utf-8")
assert "</script" not in sol
out=app.replace("/*__SOLVER__*/", sol)
(here.parent/"habitat_fire_section_2d.html").write_text(out, encoding="utf-8")
print("built", len(out), "bytes")
''', encoding="utf-8")
print("app2d.html written", len(s))
