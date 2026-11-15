# Adds the space backdrop, exterior hardware, cabin lighting, flame sprites, embers, HUD and the crew-guidance card.
import pathlib
p = pathlib.Path(__file__).parent / "ship_body.html"
s = p.read_text(encoding="utf-8")

def rep(a, b, n=1):
    global s
    c = s.count(a)
    assert c == n, (c, a[:100])
    s = s.replace(a, b)

# ---------- markup ----------
rep('<div class="viewport" id="vp3d"><canvas id="three" aria-label="3D cutaway of the spacecraft"></canvas><div class="labels" id="labels"></div></div>',
    '<div class="viewport" id="vp3d"><canvas id="three" aria-label="3D cutaway of the spacecraft"></canvas><div class="labels" id="labels"></div><div class="hud" id="hud"></div></div>')
rep('      <div class="notice" id="notice" hidden></div>\n    </section>',
    '      <div class="notice" id="notice" hidden></div>\n      <div class="advice" id="advice" aria-live="polite"></div>\n    </section>')

# ---------- renderer setup: tone mapping, sun, cabin lights ----------
rep("  renderer=new THREE.WebGLRenderer({canvas:cv, antialias:true, alpha:true}); renderer.setPixelRatio(Math.min(2,window.devicePixelRatio||1));",
    "  renderer=new THREE.WebGLRenderer({canvas:cv, antialias:true}); renderer.setPixelRatio(Math.min(2,window.devicePixelRatio||1));\n  renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.05; renderer.outputEncoding=THREE.sRGBEncoding;")
rep("  scene.add(new THREE.HemisphereLight(0xffffff,0x445566,0.85)); const dl=new THREE.DirectionalLight(0xffffff,0.55); dl.position.set(3,8,6); scene.add(dl);",
    "  scene.add(new THREE.HemisphereLight(0xdfe8ff,0x1a2230,0.75)); const sun=new THREE.DirectionalLight(0xfff4e0,1.1); sun.position.set(-6,10,8); scene.add(sun);\n  const rim=new THREE.DirectionalLight(0x6fa8ff,0.35); rim.position.set(8,-4,-10); scene.add(rim);\n  fx=new THREE.Group(); scene.add(fx);")
rep("let renderer=null, scene, camera, controls, world,", "let renderer=null, scene, camera, controls, world, fx=null,")

# ---------- exterior, environment, effects ----------
rep("function render3d(){", r'''// ---------- environment: orbit above Earth, or landed on the Moon / Mars, or a ground test chamber ----------
let envGroup=null, envKey='', extGroup=null;
const envKind=()=> P.g<0.05?'orbit': P.g<0.27?'moon': P.g<0.6?'mars':'earth';
function ctex(w,h,draw){ const c=document.createElement('canvas'); c.width=w; c.height=h; draw(c.getContext('2d'),w,h); const t=new THREE.CanvasTexture(c); t.encoding=THREE.sRGBEncoding; return t; }
function rng(seed){ let x=seed>>>0||1; return ()=>((x=Math.imul(x^(x>>>15),2246822507)^Math.imul(x^(x>>>13),3266489909))>>>0)/4294967296; }
function earthTex(){ return ctex(1024,512,(c,w,h)=>{ const r=rng(42);
  const g=c.createLinearGradient(0,0,0,h); g.addColorStop(0,'#0a2d6e'); g.addColorStop(0.5,'#1259a6'); g.addColorStop(1,'#0a2d6e'); c.fillStyle=g; c.fillRect(0,0,w,h);
  for(let i=0;i<22;i++){ const cx=r()*w, cy=h*0.2+r()*h*0.6, R=30+r()*110; c.fillStyle=r()<0.6?'#3f7d3a':'#8b7a4a';
    c.beginPath(); for(let a=0;a<=24;a++){ const t=a/24*Math.PI*2, rr=R*(0.6+0.5*r()); c.lineTo(cx+Math.cos(t)*rr*1.4, cy+Math.sin(t)*rr*0.8); } c.fill(); }
  c.globalAlpha=0.55; c.strokeStyle='#ffffff'; c.lineCap='round';
  for(let i=0;i<160;i++){ c.lineWidth=2+r()*9; c.beginPath(); const x=r()*w, y=r()*h, L=40+r()*160; c.moveTo(x,y); c.bezierCurveTo(x+L*0.3,y-10*r(),x+L*0.6,y+12*r(),x+L,y+r()*8); c.stroke(); } }); }
function groundTex(kind){ return ctex(512,512,(c,w,h)=>{ const r=rng(kind==='moon'?7:kind==='mars'?11:3);
  const base= kind==='moon'?[128,128,124]: kind==='mars'?[176,96,62]:[70,74,80]; c.fillStyle=`rgb(${base})`; c.fillRect(0,0,w,h);
  for(let i=0;i<9000;i++){ const v=(r()-0.5)*40; c.fillStyle=`rgba(${base[0]+v|0},${base[1]+v|0},${base[2]+v|0},0.5)`; c.fillRect(r()*w,r()*h,2,2); }
  if(kind==='earth'){ c.strokeStyle='rgba(255,255,255,0.12)'; for(let x=0;x<w;x+=32){ c.beginPath(); c.moveTo(x,0); c.lineTo(x,h); c.stroke(); c.beginPath(); c.moveTo(0,x); c.lineTo(w,x); c.stroke(); } return; }
  for(let i=0;i<60;i++){ const x=r()*w, y=r()*h, R=3+r()*r()*40; c.strokeStyle='rgba(0,0,0,0.25)'; c.lineWidth=2; c.beginPath(); c.arc(x,y,R,0,7); c.stroke(); c.strokeStyle='rgba(255,255,255,0.12)'; c.beginPath(); c.arc(x-1,y-1,R,3.6,5.6); c.stroke(); } }); }
function solarTex(){ return ctex(256,512,(c,w,h)=>{ c.fillStyle='#0d1b3d'; c.fillRect(0,0,w,h);
  for(let y=4;y<h;y+=16) for(let x=4;x<w;x+=16){ c.fillStyle= ((x+y)/16)%2? '#16306a':'#1a3a7d'; c.fillRect(x,y,14,14); }
  c.strokeStyle='#c9a24a'; c.lineWidth=4; c.strokeRect(2,2,w-4,h-4); c.lineWidth=1.5; for(let y=0;y<h;y+=128){ c.beginPath(); c.moveTo(0,y); c.lineTo(w,y); c.stroke(); } }); }
function buildEnv(){
  const kind=envKind(); if(!scene||(kind===envKey&&envGroup)) return; envKey=kind;
  if(envGroup) scene.remove(envGroup); if(extGroup) scene.remove(extGroup);
  envGroup=new THREE.Group(); extGroup=new THREE.Group(); scene.add(envGroup); scene.add(extGroup);
  const r=rng(5), n=1800, pos=new Float32Array(n*3);
  for(let i=0;i<n;i++){ const u=r()*2-1, a=r()*Math.PI*2, q=Math.sqrt(1-u*u); pos[3*i]=110*q*Math.cos(a)+5; pos[3*i+1]=110*u; pos[3*i+2]=110*q*Math.sin(a); }
  const sg=new THREE.BufferGeometry(); sg.setAttribute('position',new THREE.BufferAttribute(pos,3));
  envGroup.add(new THREE.Points(sg,new THREE.PointsMaterial({color:0xffffff,size:1.6,sizeAttenuation:false,transparent:true,opacity:kind==='mars'?0:kind==='earth'?0.15:0.9,depthWrite:false})));
  renderer.setClearColor(kind==='mars'?0xb98a6e: kind==='earth'?0x0b0e13:0x02040a);
  const metal=new THREE.MeshStandardMaterial({color:0xb9c0c9,metalness:0.7,roughness:0.35}), white=new THREE.MeshStandardMaterial({color:0xeef0f2,metalness:0.1,roughness:0.6});
  // berthing rings at the module joints and a docking port at the aft end
  for(const [x,rr] of [[6.57,2.18],[9.57,1.38]]){ const t=new THREE.Mesh(new THREE.TorusGeometry(rr,0.07,10,64),metal); t.rotation.y=Math.PI/2; t.position.set(x,2.1,2.1); extGroup.add(t); }
  const dp=new THREE.Mesh(new THREE.CylinderGeometry(0.75,0.95,0.5,40,1,true),metal); dp.rotation.z=Math.PI/2; dp.position.set(0.05,2.1,2.1); extGroup.add(dp);
  const ring=new THREE.Mesh(new THREE.TorusGeometry(0.8,0.06,10,48),metal); ring.rotation.y=Math.PI/2; ring.position.set(-0.2,2.1,2.1); extGroup.add(ring);
  if(kind==='orbit'){
    const earth=new THREE.Mesh(new THREE.SphereGeometry(60,64,48),new THREE.MeshStandardMaterial({map:earthTex(),roughness:0.9,metalness:0}));
    earth.position.set(6,-68,-30); earth.rotation.set(0.3,0.8,0.1); envGroup.add(earth);
    const atm=new THREE.Mesh(new THREE.SphereGeometry(62.2,64,48),new THREE.MeshBasicMaterial({color:0x4aa3ff,transparent:true,opacity:0.22,side:THREE.BackSide,blending:THREE.AdditiveBlending,depthWrite:false}));
    atm.position.copy(earth.position); envGroup.add(atm);
    // truss over the modules, two solar array wings and a radiator
    const truss=new THREE.Mesh(new THREE.BoxGeometry(23,0.32,0.32),metal); truss.position.set(5.75,5.3,2.1); extGroup.add(truss);
    for(const x of [3.4,8.1]){ const mast=new THREE.Mesh(new THREE.CylinderGeometry(0.09,0.09,1.1,12),metal); mast.position.set(x,4.75,2.1); extGroup.add(mast); }
    const st=solarTex(), sm=new THREE.MeshStandardMaterial({map:st,metalness:0.4,roughness:0.35,side:THREE.DoubleSide,emissive:0x0a1430,emissiveIntensity:0.4});
    for(const x of [-3.6,15.1]) for(const dy of [-1,1]){ const w_=new THREE.Mesh(new THREE.PlaneGeometry(3.2,7.2),sm); w_.position.set(x,5.3+dy*4.0,1.0); w_.rotation.y=-0.15; extGroup.add(w_);
      const boom=new THREE.Mesh(new THREE.CylinderGeometry(0.04,0.04,8.2,8),metal); boom.position.set(x,5.3+dy*4.0,1.02); extGroup.add(boom); }
    const rad=new THREE.Mesh(new THREE.BoxGeometry(3.2,0.04,2.4),white); rad.position.set(8.1,5.55,0.4); rad.rotation.x=-0.25; extGroup.add(rad);
  } else {
    const ground=new THREE.Mesh(new THREE.PlaneGeometry(260,260),new THREE.MeshStandardMaterial({map:groundTex(kind),roughness:1,metalness:0}));
    ground.material.map.wrapS=ground.material.map.wrapT=THREE.RepeatWrapping; ground.material.map.repeat.set(26,26);
    ground.rotation.x=-Math.PI/2; ground.position.set(5.75,-1.3,2.1); envGroup.add(ground);
    if(kind==='mars'){ scene.fog=new THREE.Fog(0xb98a6e,25,120); } else scene.fog=null;
    if(kind!=='earth'){ for(const [x,z] of [[1.2,0.3],[1.2,3.9],[10.2,0.9],[10.2,3.3],[5.5,0.1],[5.5,4.1]]){
      const leg=new THREE.Mesh(new THREE.CylinderGeometry(0.06,0.08,1.8,10),metal); const top=new THREE.Vector3(x,0.6,(z<2.1?0.9:3.3)), foot=new THREE.Vector3(x,-1.25,z);
      leg.position.copy(top.clone().add(foot).multiplyScalar(0.5)); leg.lookAt(foot); leg.rotateX(Math.PI/2); leg.scale.y=top.distanceTo(foot)/1.8; extGroup.add(leg);
      const pad=new THREE.Mesh(new THREE.CylinderGeometry(0.3,0.34,0.06,20),metal); pad.position.copy(foot); extGroup.add(pad); } }
    else { const stand=new THREE.Mesh(new THREE.BoxGeometry(11.6,0.3,1.8),metal); stand.position.set(5.75,-0.6,2.1); extGroup.add(stand); }
  }
  if(kind!=='mars') scene.fog=null;
}
// ---------- cabin lights (warm aisle strips) ----------
function addCabinLights(){
  for(const [x,y,z] of [[1.6,3.0,2.1],[3.8,3.0,2.1],[5.8,3.0,2.1],[7.9,3.5,2.1],[10.5,2.9,2.1]]){ const L=new THREE.PointLight(0xfff1d8,0.45,4.5,1.6); L.position.set(x,y,z); world.add(L); }
  const strip=new THREE.MeshBasicMaterial({color:0xfff6e6});
  for(const z of [1.2,3.0]){ const s_=new THREE.Mesh(new THREE.BoxGeometry(5.8,0.03,0.08),strip); s_.position.set(3.4,3.13,z); world.add(s_); }
}
// ---------- flames (additive sprites) and embers ----------
let flameTex=null, flames=[], halos=[], emberPts=null, embers=[];
function initFx(){
  if(flames.length||!fx) return;
  flameTex=ctex(64,64,(c,w,h)=>{ const g=c.createRadialGradient(32,32,0,32,32,32); g.addColorStop(0,'rgba(255,255,235,1)'); g.addColorStop(0.22,'rgba(255,214,110,0.95)'); g.addColorStop(0.5,'rgba(255,120,30,0.5)'); g.addColorStop(1,'rgba(255,60,0,0)'); c.fillStyle=g; c.fillRect(0,0,w,h); });
  for(let i=0;i<260;i++){ const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:flameTex,blending:THREE.AdditiveBlending,depthWrite:false,transparent:true})); sp.visible=false; fx.add(sp); flames.push(sp); }
  for(let i=0;i<90;i++){ const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:flameTex,blending:THREE.AdditiveBlending,depthWrite:false,transparent:true,opacity:0.22})); sp.visible=false; fx.add(sp); halos.push(sp); }
  const n=500, g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.BufferAttribute(new Float32Array(n*3),3)); g.setAttribute('color',new THREE.BufferAttribute(new Float32Array(n*3),3));
  emberPts=new THREE.Points(g,new THREE.PointsMaterial({size:0.05,vertexColors:true,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false})); fx.add(emberPts);
  for(let i=0;i<n;i++) embers.push({life:0,x:0,y:0,z:0,vx:0,vy:0,vz:0,max:1});
}
let lastFx=performance.now();
function updateFx(){
  if(!fx||!G||!F) return; initFx();
  const now=performance.now(), dt=Math.min(0.05,(now-lastFx)/1000); lastFx=now;
  const I=G.info, hh=I.h, g=P.g, burning=[];
  for(const k of G.fuelList) if(F.fst[k]===2) burning.push(k);
  const step=Math.max(1,Math.ceil(burning.length/flames.length));
  let fi=0, hi=0;
  for(let q=0;q<burning.length;q+=step){ const k=burning[q], [x,y,z]=wpos(k);
    // local air speed sets the flame shape: round and bluish in still orbit air, tall in gravity
    let sp=0; for(const o of [1,-1,I.SY,-I.SY,I.SY*I.ny,-I.SY*I.ny]){ const n=k+o; if(G.typeArr[n]===0) sp=Math.max(sp,Math.hypot(F.u[n],F.v[n],F.w[n])); }
    const blue= g<0.05 && sp<0.12 ? 0.55 : 0, fl=0.75+Math.random()*0.5, s=hh*2.1*fl;
    const f=flames[fi++]; f.visible=true; f.position.set(x+(Math.random()-0.5)*hh*0.4, y+(g>0?s*0.35:0), z+(Math.random()-0.5)*hh*0.4);
    f.scale.set(s, g>0? s*(1.5+Math.min(1,g)*1.1) : s, 1); f.material.color.setRGB(1-blue*0.45, 1-blue*0.2, 1);
    if(hi<halos.length && Math.random()<0.6){ const H=halos[hi++]; H.visible=true; H.position.set(x,y+(g>0?s*0.5:0),z); H.scale.set(s*3.2,s*3.2*(g>0?1.3:1),1); }
    // embers
    if(Math.random()<0.6){ const e=embers.find(e=>e.life<=0); if(e){ e.x=x; e.y=y; e.z=z; e.vx=(Math.random()-0.5)*0.3; e.vy=(Math.random()-0.5)*0.3+(g>0?0.5+g*0.4:0); e.vz=(Math.random()-0.5)*0.3; e.max=e.life=1.2+Math.random()*1.8; } }
    if(fi>=flames.length) break; }
  for(let i=fi;i<flames.length;i++) flames[i].visible=false; for(let i=hi;i<halos.length;i++) halos[i].visible=false;
  const pa=emberPts.geometry.attributes.position.array, ca=emberPts.geometry.attributes.color.array;
  embers.forEach((e,i)=>{ if(e.life>0){ e.life-=dt; e.x+=e.vx*dt; e.y+=e.vy*dt; e.z+=e.vz*dt; const a=Math.max(0,e.life/e.max); pa[3*i]=e.x; pa[3*i+1]=e.y; pa[3*i+2]=e.z; ca[3*i]=1*a; ca[3*i+1]=0.55*a; ca[3*i+2]=0.15*a; } else { ca[3*i]=ca[3*i+1]=ca[3*i+2]=0; } });
  emberPts.geometry.attributes.position.needsUpdate=true; emberPts.geometry.attributes.color.needsUpdate=true;
}
// ---------- HUD ----------
function renderHud(){
  if(!G) return; const k=envKind(), place={orbit:'Low Earth orbit',moon:'Lunar surface',mars:'Mars surface',earth:'Ground test chamber'}[k];
  const mt=F?F.t:0, hms=`${String(Math.floor(mt/3600)).padStart(2,'0')}:${String(Math.floor(mt/60)%60).padStart(2,'0')}:${String(Math.floor(mt%60)).padStart(2,'0')}`;
  const fans=P.vent, pow=F&&F.qxOn&&F.qxOn.some(x=>x), fire=F&&F.stats.some(r=>r.flame>0);
  $('hud').innerHTML=`<div><b>${place}</b> · ${P.g>0?P.g.toFixed(3)+' g':'0 g'}</div><div>Cabin ${P.X.toFixed(1)}% O₂ · ${P.Pk.toFixed(1)} kPa</div><div>Time since ignition ${hms}</div>
    <div class="leds"><span class="led ${fans?'on':'off'}">Fans</span><span class="led ${pow?'warn':'off'}">Overheat</span><span class="led ${fire?'crit':'off'}">Fire</span></div>`;
}
function render3d(){''')
rep("  if(!renderer||view!=='3d') return; controls.update(); renderer.render(scene,camera);",
    "  if(!renderer||view!=='3d') return; buildEnv(); updateFx(); controls.update(); renderer.render(scene,camera); renderHud();")
rep("  heatPts.renderOrder=3; smokePts.renderOrder=2; world.add(smokePts); world.add(heatPts);",
    "  heatPts.renderOrder=3; smokePts.renderOrder=2; world.add(smokePts); world.add(heatPts); addCabinLights(); envKey='';")
# warmer, more realistic interior materials
rep("  const mk=(list,op)=>{ const m=new THREE.InstancedMesh(box,new THREE.MeshLambertMaterial({color:0xffffff,transparent:op<1,opacity:op,depthWrite:op>=1}),list.length);",
    "  const mk=(list,op)=>{ const m=new THREE.InstancedMesh(box,new THREE.MeshStandardMaterial({color:0xffffff,roughness:0.7,metalness:0.15,transparent:op<1,opacity:op,depthWrite:op>=1}),list.length);")
rep("  const shell=new THREE.Mesh(new THREE.CylinderGeometry(r,r,x1-x0,64,1,true), new THREE.MeshStandardMaterial({color:col,side:THREE.BackSide,metalness:0.35,roughness:0.55}));",
    "  const shell=new THREE.Mesh(new THREE.CylinderGeometry(r,r,x1-x0,64,1,true), new THREE.MeshStandardMaterial({color:col,side:THREE.BackSide,metalness:0.45,roughness:0.45}));\n  // outer skin: quilted MLI blanket, faint so the cabin stays visible\n  const skin=new THREE.Mesh(new THREE.CylinderGeometry(r+0.06,r+0.06,x1-x0,64,1,true), new THREE.MeshStandardMaterial({color:0xf3f1ea,transparent:true,opacity:0.07,depthWrite:false,roughness:0.9}));\n  skin.rotation.z=Math.PI/2; skin.position.set((x0+x1)/2,G.info.AXY,G.info.AXZ); g.add(skin);")

# ---------- crew guidance ----------
rep("  renderTiles(); renderRooms(); renderLog(); drawGrowth(); renderOpenings();",
    "  renderTiles(); renderRooms(); renderLog(); drawGrowth(); renderOpenings(); renderAdvice();")
rep("// ---------------- shared panels ----------------", r'''// ---------------- crew guidance ----------------
// Teaching guidance built from published NASA fire-response principles (knowledge base: ISS fire response, Mir 1997 fire,
// fire-detection and combustion-product records). It reads the live scenario and the flame model's predictions.
const MATNOTE={
  pe:'Polyethylene insulation melts, drips and burns with very sooty smoke, so visibility drops fast.',
  ptfe:'Teflon will not burn in any cabin atmosphere, but when it overheats it releases toxic acid gases such as hydrogen fluoride. Wear masks even if there is no flame.',
  kapton:'Kapton chars instead of melting and needs more than 35% O₂ to burn. Damaged Kapton wiring can arc, so keep the circuit de-energised.',
  silicone:'Silicone rubber burns slowly and leaves white silica ash. Its smoke is light, so detectors may react late.',
  pc:'Polycarbonate needs sustained heat to ignite, but once burning it gives dense, sooty smoke.',
  pu:'Foam can smoulder unseen and then flare into flame. Check inside packing after the fire is out.',
  nylon:'Nylon Velcro melts and drips burning beads. NASA burned it in 30% O₂ drop-tower tests.',
  nomex:'Nomex resists burning in normal air, but in an oxygen-enriched cabin it can sustain a flame.',
  cotton:'Cotton ignites easily and spreads quickly. Clothing and towels are common fuel in crew areas.',
  paper:'Paper and wipes catch fire easily and burn fast, but burn out quickly.',
  sibal:'This cotton-fiberglass fabric is the material NASA burned in the BASS and Saffire flight experiments.',
  pmma:'Acrylic burns steadily with little smoke, and in 0 g the flame can be dim blue and hard to see.'};
const PLACE={rack:'For a rack fire, cut power to the rack first, then discharge the extinguisher through the rack\'s fire port. The rack\'s own fan feeds the fire.',
  cqp:'Someone may be asleep inside the crew quarters. Wake them and get them out before closing the door.',
  cqs:'Someone may be asleep inside the crew quarters. Wake them and get them out before closing the door.',
  air:'The airlock can be isolated by closing its hatch, and in the worst case depressurised.',
  node:'In the galley, switch off the food warmer and water heater as well.',
  lab:'Power down nearby experiments too.'};
const isOpen=id=>{ const i=G.OPEN.findIndex(o=>o.id===id); return i<0?false:(F?F.opens[i]:G.OPEN[i].open); };
function hatchesFor(rid){ return rid==='lab'||rid==='rack'? ['H1'] : rid==='cqp'? ['C1','H1','H2'] : rid==='cqs'? ['C2','H1','H2'] : rid==='node'? ['H1','H2'] : ['H2']; }
function havenFor(rid){ return rid==='lab'||rid==='rack'? 'the Node, away from the Lab' : rid==='air'? 'the Lab' : 'the Lab, away from the Node'; }
function act(a){ if(!G) return;
  if(a==='power'){ send({cmd:'stopOverheat'}); addLog(-1,'Guidance: power cut to the overheating item'); }
  else if(a==='fans'){ if(P.vent){ P.vent=false; syncControls(); send({cmd:'set',params:Object.assign({},P)}); addLog(-1,'Guidance: fans switched off'); } }
  else if(a.startsWith('close:')){ const id=a.slice(6), oi=G.OPEN.findIndex(o=>o.id===id); if(oi>=0&&isOpen(id)){ send({cmd:'toggle',oi}); addLog(-1,`Guidance: ${G.OPEN[oi].name} closed`); } }
  renderAdvice(true); }
function advice(){
  const it=G.ITEMS[sel], mk=it.m, mat=G.MAT[mk], a=AS&&AS.assess[sel], st=F.stats;
  const rid=it.room, rname=G.ROOMS.find(r=>r.id===rid).name;
  const fireRooms=st.map((r,i)=>r.flame>0?i:-1).filter(i=>i>=0), hrr=st.reduce((s_,r)=>s_+r.hrr,0)/1000;
  const over=F.qxOn&&F.qxOn.some(x=>x), started=F.igns.length>0||over||roomFirst.some(r=>r&&r.fire!==null);
  const smoky=st.some(r=>r.vis<5), alarm=roomFirst.some(r=>r&&r.alarm!==null), hot=st.some(r=>r.Tmax>600), sealed=st.some(r=>r.pbg>50);
  const orbit=P.g<0.05, highO2=P.X>23.5, lowP=P.Pk<80;
  const hatchSteps=ids=>ids.map(id=>({t:`Close the ${G.OPEN.find(o=>o.id===id).name.toLowerCase()}.`, a:'close:'+id, done:!isOpen(id)}));
  const notes=[], steps=[]; let level, title, what;
  const fanNote= orbit ? (a&&a.noflow===false ? 'In orbit this flame lives on the fan airflow. The model predicts it cannot survive here without it, so turning the fans off should starve it.'
                                              : 'In orbit there is no rising smoke: smoke goes wherever the fans blow it, and the detectors sit in that airflow. At this oxygen level the model predicts the flame can survive even with the fans off, so you will also need the extinguisher.')
                       : 'With gravity the flame makes its own buoyant airflow, so turning the fans off slows smoke spread but will not starve the fire. Hot smoke collects overhead first.';
  if(!started){
    level='info'; title='No fire yet: check this spot';
    what= a? (a.exists? `${it.name} (${mat.name}) can burn here in this cabin air. It needs at least ${a.lim}% O₂ in the local ${a.U} cm/s airflow, and the cabin has ${P.X.toFixed(1)}%.`
                      : a.lim===null? `${it.name} (${mat.name}) cannot burn in any cabin atmosphere.` : `${it.name} (${mat.name}) will not stay alight here. It would need ${a.lim}% O₂, and the cabin has ${P.X.toFixed(1)}%.`) : '';
    steps.push({t:'Keep ignition sources away from flammable items, and fix damaged wiring promptly.'});
    if(highO2) steps.push({t:`At ${P.X.toFixed(1)}% O₂ more materials burn and flames spread faster. Use only materials that pass the flammability screening for this atmosphere.`});
    steps.push({t:'Know where the nearest extinguisher, breathing masks and smoke detectors are before anything happens.'});
  } else if(fireRooms.length===0 && over){
    level='act'; title='Overheating: smoke, no flame yet';
    what=`${it.name} in the ${rname.toLowerCase()} is being heated electrically and giving off smoke and fuel vapour. ${a&&a.exists?'If it keeps heating, it can ignite.':'In this atmosphere the model predicts it will not catch fire, but it keeps releasing toxic smoke while the power stays on.'}`;
    steps.push({t:'Cut power to the overheating equipment. This removes the heat source.', a:'power', done:false});
    steps.push({t:'Put on breathing masks. Smoke from hot insulation is toxic.'});
    steps.push({t:'Turn the module fans off so smoke and oxygen stop moving through the cabin.', a:'fans', done:!P.vent});
    steps.push({t:'Locate the source with the smoke detectors and a combustion-product monitor, and have the extinguisher ready.'});
  } else if(fireRooms.length===0){
    level='clear'; title='Flames out: make the cabin safe';
    what=`No flame is burning now${F.ext?` (it went out: ${({quenching:'airflow too weak',blowoff:'airflow too strong',oxygen:'oxygen used up'})[F.ext]||F.ext})`:''}. Smoke and combustion products remain${smoky?', and visibility is still below 5 m in at least one compartment':''}.`;
    steps.push({t:'Keep masks on until CO, HCN and acid gases are measured below safe limits.'});
    steps.push({t:'Run the atmosphere scrubbers and filters to clean the air.'});
    steps.push({t:'Check for hidden smouldering, especially in foam and wire insulation, and do not restore power to the damaged item.'});
    if(sealed) steps.push({t:'A sealed compartment is still under pressure. Equalise the pressure slowly before opening its hatch.'});
  } else if(fireRooms.length>=2 || hrr>20 || hot){
    level='evac'; title='Fire is growing: isolate and move away';
    what=`Flames in ${fireRooms.length} compartment${fireRooms.length>1?'s':''}, ${hrr.toFixed(1)} kW of heat release${hot?', and hot gas above 327 °C':''}.`;
    steps.push({t:`Move everyone to ${havenFor(rid)}, toward the crew return vehicle, and account for the whole crew.`});
    steps.push(...hatchSteps(hatchesFor(rid)));
    steps.push({t:'Turn the fans off and cut power to the affected modules.', a:'fans', done:!P.vent});
    steps.push({t:'Wear masks. If the fire cannot be controlled, prepare to depressurise the affected module or leave the vehicle.'});
  } else {
    level='act'; title='Fire: act now';
    what=`Flames on ${it.name.toLowerCase()} in the ${rname.toLowerCase()}, ${hrr.toFixed(1)} kW. ${a?`Spread about ${Math.max(a.vo,a.vc).toFixed(1)} mm/s at the origin.`:''}`;
    steps.push({t:'Alert the crew and announce the location.'});
    if(over) steps.push({t:'Cut power to the overheating equipment.', a:'power', done:false});
    steps.push({t:'Turn the module fans off.', a:'fans', done:!P.vent});
    steps.push({t:'Put on breathing masks.'});
    steps.push({t:'Discharge the extinguisher at the burning item: CO₂ on the US segment, water-based foam on the Russian segment.'});
    steps.push(...hatchSteps(hatchesFor(rid).slice(0,1)).map(s_=>({...s_, t:s_.t+' Do this if the fire is not out within a minute, after the crew is clear.'})));
  }
  if(started) notes.push(fanNote);
  notes.push(MATNOTE[mk]||''); if(started||rid==='rack'||rid==='cqp'||rid==='cqs') notes.push(PLACE[rid]||'');
  if(highO2) notes.push(`Oxygen-enriched cabin (${P.X.toFixed(1)}%): very few materials are non-flammable at these levels (NASA techport 185608).`);
  if(lowP) notes.push(`Low cabin pressure (${P.Pk.toFixed(1)} kPa): buoyant flow is weaker, and extinguisher agent behaves differently than at sea level.`);
  if(alarm&&started) notes.push('Smoke detectors have alarmed. On the ISS they sit in the ventilation return, so they detect smoke the fans carry to them.');
  return {level,title,what,steps,notes:notes.filter(Boolean)};
}
let advSig='';
function renderAdvice(force){
  if(!G||!F) return; const A=advice(); const sig=JSON.stringify([A.level,A.title,A.steps.map(s_=>s_.t+(s_.done?1:0)),A.notes.length,sel,P.vent]);
  if(sig===advSig&&!force) return; advSig=sig;
  const label={info:'Prevention',act:'Act now',evac:'Evacuate and isolate',clear:'All clear: monitor'}[A.level];
  const el=$('advice'); el.className='advice lv-'+A.level;
  el.innerHTML=`<div class="adv-head"><span class="sev">${label}</span><h2>${A.title}</h2></div><p class="adv-what">${A.what}</p>
    <ol>${A.steps.map(s_=>`<li>${s_.t}${s_.a?` <button type="button" data-act="${s_.a}" ${s_.done?'disabled':''}>${s_.done?'Done':'Do it'}</button>`:''}</li>`).join('')}</ol>
    ${A.notes.length?`<ul class="adv-notes">${A.notes.map(n=>`<li>${n}</li>`).join('')}</ul>`:''}
    <p class="adv-src">Teaching guidance based on published NASA fire-response principles: isolate power and ventilation, protect breathing, use CO₂ or water-based extinguishers, then clean the air (knowledge base: ISS fire response, Mir 1997 fire, <a href="https://ntrs.nasa.gov/citations/20170000248" target="_blank" rel="noopener">NTRS 20170000248</a>, <a href="https://ntrs.nasa.gov/citations/20140000850" target="_blank" rel="noopener">NTRS 20140000850</a>). It is not an operational procedure.</p>`;
  el.querySelectorAll('button[data-act]').forEach(b=>b.onclick=()=>act(b.dataset.act));
}

// ---------------- shared panels ----------------''')
p.write_text(s, encoding="utf-8")
print("ship_body patched", len(s))
