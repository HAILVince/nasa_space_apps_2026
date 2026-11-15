# v5 page script: logged commands, crew, suppression, fast-forward, replay, compare, export, scenarios, quiz, validation plots.
import pathlib, re
p=pathlib.Path(__file__).parent/'ship_body.html'
s=p.read_text(encoding='utf-8')
def rep(old,new,count=1):
    global s
    assert s.count(old)>=1, 'missing: '+old[:90]
    s=s.replace(old,new,count)

# ---- worker source comes from worker_v5.js at build time
i0=s.index('<script type="text/plain" id="worker-src">'); i1=s.index('</script>',i0)
s=s[:i0]+'<script type="text/plain" id="worker-src">/*__WORKER__*/'+s[i1:]
rep('<label for="itemsOff">Items on board (untick to remove a fuel)</label>','<span class="eyebrow">Items on board (untick to remove a fuel)</span>')

# ---- logged commands
rep("send({cmd:'ignite',k}); addLog(G.room[k]","send({cmd:'do',c:{do:'ignite',k}}); addLog(G.room[k]")
rep("if(best>=0){ send({cmd:'ignite',k:best}); resume(); }","if(best>=0){ send({cmd:'do',c:{do:'ignite',k:best}}); resume(); }")
rep("if(G.openId[k]>=0&&G.typeArr[k]!==2){ send({cmd:'toggle',oi:G.openId[k]}); return; }","if(G.openId[k]>=0&&G.typeArr[k]!==2){ toggleOpen(G.openId[k]); return; }")
rep("const ig=mode=>()=>{ if(!G) return; send({cmd:'igniteItem',i:sel,mode});","const ig=mode=>()=>{ if(!G) return; send({cmd:'do',c:{do:'igniteItem',i:sel,mode}});")
rep("$('igStop').onclick=()=>{ send({cmd:'stopOverheat'});","$('igStop').onclick=()=>{ send({cmd:'do',c:{do:'power'}});")
rep("b.onclick=()=>{ send({cmd:'toggle',oi}); addLog(-1,`${o.name} ${open?'closed':'opened'}`); }; el.appendChild(b); }); }",
    "b.onclick=()=>{ toggleOpen(oi); addLog(-1,`${o.name} ${open?'closed':'opened'}`); }; el.appendChild(b); }); }\nfunction toggleOpen(oi){ const open=F?F.opens[oi]:G.OPEN[oi].open; send({cmd:'do',c:{do:'opening',id:G.OPEN[oi].id,open:!open}}); }")
rep("$('ventoff').onclick=()=>{ P.vent=!P.vent; syncControls(); send({cmd:'set',params:Object.assign({},P)});","$('ventoff').onclick=()=>{ P.vent=!P.vent; syncControls(); send({cmd:'do',c:{do:'fans',on:P.vent}});")
rep("""  if(a==='power'){ send({cmd:'stopOverheat'}); addLog(-1,'Guidance: power cut to the overheating item'); }
  else if(a==='fans'){ if(P.vent){ P.vent=false; syncControls(); send({cmd:'set',params:Object.assign({},P)}); addLog(-1,'Guidance: fans switched off'); } }
  else if(a.startsWith('close:')){ const id=a.slice(6), oi=G.OPEN.findIndex(o=>o.id===id); if(oi>=0&&isOpen(id)){ send({cmd:'toggle',oi}); addLog(-1,`Guidance: ${G.OPEN[oi].name} closed`); } }""",
"""  if(a==='power'){ send({cmd:'do',c:{do:'power'}}); addLog(-1,'Guidance: power cut to the overheating item'); }
  else if(a==='fans'){ if(P.vent){ P.vent=false; syncControls(); send({cmd:'do',c:{do:'fans',on:false}}); addLog(-1,'Guidance: fans switched off'); } }
  else if(a.startsWith('close:')){ const id=a.slice(6), oi=G.OPEN.findIndex(o=>o.id===id); if(oi>=0&&isOpen(id)){ toggleOpen(oi); addLog(-1,`Guidance: ${G.OPEN[oi].name} closed`); } }
  else respond(a,'Guidance: ');""")

# ---- messages from the worker
rep("""  else if(d.type==='frame'){ F=d; onFrame(); }""","""  else if(d.type==='frame'){ F=d; onFrame(); }
  else if(d.type==='ffdone'){ onFFDone(d); }
  else if(d.type==='rec'){ onRec(d); }""")
rep("""  worker.postMessage({cmd:'init', h, params:Object.assign({},P), mats, selMat: mats? mats[sel] : 'pe'});""",
    """  worker.postMessage({cmd:'init', h, params:Object.assign({},P), mats, off:itemsOff, selMat: mats? mats[sel] : 'pe'});""")
rep("let G=null, F=null, AS=null, worker=null, running=true, speed=8, h=0.15, view='3d', sel=0, mats=null;",
    "let G=null, F=null, AS=null, worker=null, running=true, speed=8, h=0.15, view='3d', sel=0, mats=null, itemsOff=null, ffOn=false, replayMode=false;")
rep("  if(d.type==='geom'){ G=d; mats=G.ITEMS.map(i=>i.m); buildScene(); renderValidation(); renderOrigins(); renderOpenings(); syncControls(); }",
    "  if(d.type==='geom'){ G=d; mats=G.ITEMS.map(i=>i.m); itemsOff=G.ITEMS.map(i=>!i.on); buildScene(); renderValidation(); renderOrigins(); renderOpenings(); renderItemsOn(); syncControls(); }")

# ---- 3D: crew markers, extinguishing agent cloud, vent valves
rep("""  heatPts.renderOrder=3; smokePts.renderOrder=2; world.add(smokePts); world.add(heatPts); addCabinLights(); envKey='';""",
"""  heatPts.renderOrder=3; smokePts.renderOrder=2; world.add(smokePts); world.add(heatPts); addCabinLights(); envKey='';
  agentPts=pts(gas.length,THREE.NormalBlending,hh*2.4); { const a=agentPts.geometry.attributes.position.array, b=heatPts.geometry.attributes.position.array; a.set(b); agentPts.geometry.attributes.position.needsUpdate=true; } agentPts.renderOrder=2; world.add(agentPts);
  crewMeshes=[]; valveMeshes=G.VALVES.map(vl=>{ let sx=0,sy=0,sz=0; for(const k of vl.cells){ const [x,y,z]=wpos(k); sx+=x; sy+=y; sz+=z; } const n=vl.cells.length||1;
    const m=new THREE.Mesh(new THREE.TorusGeometry(0.16,0.035,8,24),new THREE.MeshBasicMaterial({color:0xff3b30})); m.position.set(sx/n,sy/n,sz/n); m.visible=false; world.add(m); return m; });""")
rep("let renderer=null, scene, camera, controls, world, fx=null,","let agentPts=null, crewMeshes=[], valveMeshes=[];\nlet renderer=null, scene, camera, controls, world, fx=null,")
rep("""  for(const a of ['aColor','aAlpha']){ heatPts.geometry.attributes[a].needsUpdate=true; smokePts.geometry.attributes[a].needsUpdate=true; }
}""","""  for(const a of ['aColor','aAlpha']){ heatPts.geometry.attributes[a].needsUpdate=true; smokePts.geometry.attributes[a].needsUpdate=true; }
  // CO₂ cloud (white) and water mist (pale blue)
  if(agentPts&&F.YD){ const ac=agentPts.geometry.attributes.aColor.array, aa=agentPts.geometry.attributes.aAlpha.array; let any=false;
    for(let q=0;q<gasIdx.length;q++){ const k=gasIdx[q], d=F.YD[k], wv=F.YW[k]; if(d<1e-3&&wv<2e-5){ aa[q]=0; continue; } any=true;
      if(wv*40>d){ ac[3*q]=0.62; ac[3*q+1]=0.82; ac[3*q+2]=1.0; aa[q]=Math.min(0.6,wv*900); } else { ac[3*q]=0.95; ac[3*q+1]=0.97; ac[3*q+2]=1.0; aa[q]=Math.min(0.5,d*1.6); } }
    agentPts.visible=any; agentPts.geometry.attributes.aColor.needsUpdate=true; agentPts.geometry.attributes.aAlpha.needsUpdate=true; }
  // crew
  if(F.crew){ while(crewMeshes.length<F.crew.length){ const g=new THREE.Group(); const body=new THREE.Mesh(new THREE.CapsuleGeometry? new THREE.CapsuleGeometry(0.11,0.42,4,8) : new THREE.CylinderGeometry(0.11,0.11,0.62,10),new THREE.MeshStandardMaterial({color:0xffffff,roughness:0.6})); body.name='body'; g.add(body);
      const head=new THREE.Mesh(new THREE.SphereGeometry(0.1,14,10),new THREE.MeshStandardMaterial({color:0xf2f2f2,roughness:0.4})); head.position.y=0.4; g.add(head); world.add(g); crewMeshes.push(g); }
    F.crew.forEach((c,i)=>{ const g=crewMeshes[i]; g.position.set(c.pos[0],c.pos[1]-0.3,c.pos[2]); g.children[0].material.color.set(crewColor(c)); g.rotation.z= c.state==='incapacitated'? Math.PI/2 : 0; }); }
  valveMeshes.forEach((m,i)=>{ m.visible=!!(F.valves&&F.valves[i]); if(m.visible) m.rotation.y+=0.08; });
}
function crewColor(c){ return c.state==='incapacitated'? '#ff3b30' : c.fed>=0.3? '#ffb347' : c.state==='blocked'? '#ffb347' : c.state==='moving'? '#5aa9ff' : '#4cc28a'; }""")
# crew labels in the 3D view
rep("""  const it=G.ITEMS[sel], el=$('lblO'); if(it&&it.cells.length&&el){""","""  if(F&&F.crew){ const box=$('labels'); F.crew.forEach((c,i)=>{ let e=$('lblC'+i); if(!e){ e=document.createElement('span'); e.id='lblC'+i; e.className='crew-l'; box.appendChild(e); }
    place(e,c.pos[0],c.pos[1]+0.32,c.pos[2]); e.textContent=c.id+(c.state==='incapacitated'?' ✕':c.state==='blocked'?' ⚠':c.mask?' ◍':''); e.style.borderColor=crewColor(c); }); }
  const it=G.ITEMS[sel], el=$('lblO'); if(it&&it.cells.length&&el){""")
rep("""  $('labels').innerHTML=G.ROOMS.map((r,ri)=>`<span id="lbl${ri}">${r.short}</span>`).join('')+'<span id="lblO" class="fire"></span>';""",
    """  $('labels').innerHTML=G.ROOMS.map((r,ri)=>`<span id="lbl${ri}">${r.short}</span>`).join('')+'<span id="lblO" class="fire"></span>';""")

# ---- slice fields
rep("""      else { const sp=Math.hypot(F.u[k],F.v[k],F.w[k]); if(sp>0.01) col=`rgba(36,69,168,${Math.min(0.8,sp/0.6)})`; } }""",
"""      else if(field==='C'){ const c=F.YC[k]*28.8/28*1e6; if(c>5) col=`rgba(150,60,170,${Math.min(0.9,Math.log10(c)/4)})`; }
      else if(field==='R'){ const q=(F.G[k]/4-5.67e-8*295**4)/1000; if(q>0.05) col=`rgba(255,120,40,${Math.min(0.9,q/5)})`; }
      else if(field==='D'){ const d=F.YD[k]; if(d>2e-3) col=`rgba(120,140,160,${Math.min(0.9,d*1.5)})`; }
      else if(field==='W'){ const wv=F.YW[k]; if(wv>1e-5) col=`rgba(80,160,255,${Math.min(0.9,wv*800)})`; }
      else { const sp=Math.hypot(F.u[k],F.v[k],F.w[k]); if(sp>0.01) col=`rgba(36,69,168,${Math.min(0.8,sp/0.6)})`; } }""")

# ---- HUD
rep("""    <div class="leds"><span class="led ${fans?'on':'off'}">Fans</span><span class="led ${pow?'warn':'off'}">Overheat</span><span class="led ${fire?'crit':'off'}">Fire</span></div>`;""",
"""    <div class="leds"><span class="led ${fans?'on':'off'}">Fans</span><span class="led ${pow?'warn':'off'}">Overheat</span><span class="led ${fire?'crit':'off'}">Fire</span><span class="led ${F&&F.alarmT>=0?'warn':'off'}">Alarm</span><span class="led ${F&&F.sprays&&F.sprays.some(s_=>s_.active)?'on':'off'}">Extinguisher</span><span class="led ${F&&F.valves&&F.valves.some(x=>x)?'crit':'off'}">Venting</span></div>
    ${F&&F.replay?'<div><b>REPLAY</b> · recorded frame</div>':''}${ffOn?'<div><b>FAST-FORWARD</b></div>':''}`;""")

# ---- tiles
rep("""tile('Pressure rise (sealed)',`${dp.toFixed(0)} Pa`)+tile('Solver speed',`×${(F.achieved||0).toFixed(1)}`);""",
"""tile('Pressure rise (sealed)',`${dp.toFixed(0)} Pa`)+tile('Highest CO',`${Math.round(Math.max(...st.map(r=>r.co)))} ppm`)+tile('Worst crew dose',F.crew&&F.crew.length?`${Math.max(...F.crew.map(c=>c.fed)).toFixed(2)} FED`:'—')+tile('Solver speed',F.replay?'replay':`×${(F.achieved||0).toFixed(1)}`);""")

# ---- per-frame hooks
rep("""  renderTiles(); renderRooms(); renderLog(); drawGrowth(); renderOpenings(); renderAdvice();""",
    """  renderTiles(); renderRooms(); renderLog(); drawGrowth(); renderOpenings(); renderAdvice(); renderCrew(); syncResponse(); quizTick(); autoTick();
  if(!F.replay){ const rp=$('rpT'); rp.max=Math.floor(F.recT||0); rp.disabled=!(F.recT>0); if(!$('rpOn').checked) rp.value=rp.max; $('rpOut').textContent=$('rpOn').checked? fmtT(+rp.value)+' / '+fmtT(F.recT||0) : (F.recT>0? 'recorded '+fmtT(F.recT):''); }""")
# events from replay frames should not be logged again
rep("""  if(!G) return; updateOpenMesh(); updateScene();
  const st=F.stats, t=F.t;""","""  if(!G) return; updateOpenMesh(); updateScene();
  const st=F.stats, t=F.t;
  if(F.replay){ $('clock').innerHTML=`${t.toFixed(1)} <small>s · replay</small>`; renderTiles(); renderCrew(); return; }""")
rep("""  if(nb>0) setStatus(`Burning in ${on} compartment${on>1?'s':''}`,'s-burn');""","""  if(ffOn) setStatus('Fast-forwarding…','s-idle');
  else if(nb>0) setStatus(`Burning in ${on} compartment${on>1?'s':''}`,'s-burn');""")
rep("""  else setStatus(F.ext? `Out: ${({quenching:'airflow too weak (quenching)',blowoff:'airflow too strong (blowoff)',oxygen:'oxygen used up'})[F.ext]||F.ext}` : 'Burnt out','s-out');""",
    """  else setStatus(F.ext? `Out: ${EXTN[F.ext]||F.ext}` : 'Burnt out','s-out');""")
rep("""    what=`No flame is burning now${F.ext?` (it went out: ${({quenching:'airflow too weak',blowoff:'airflow too strong',oxygen:'oxygen used up'})[F.ext]||F.ext})`:''}.""",
    """    what=`No flame is burning now${F.ext?` (it went out: ${EXTN[F.ext]||F.ext})`:''}.""")
rep("""const fmtT=s=>""","""const EXTN={quenching:'airflow too weak (quenching)',blowoff:'airflow too strong (blowoff)',oxygen:'oxygen used up',co2:'CO₂ extinguisher',mist:'water mist',pressure:'cabin pressure too low'};
const fmtT=s=>""")

# ---- advice: richer steps with response actions
rep("""    steps.push({t:'Cut power to the overheating equipment. This removes the heat source.', a:'power', done:false});
    steps.push({t:'Put on breathing masks. Smoke from hot insulation is toxic.'});""","""    steps.push({t:'Cut power to the overheating equipment. This removes the heat source.', a:'power', done:false});
    steps.push({t:'Put on breathing masks. Smoke from hot insulation is toxic.', a:'masks', done:masksOn});""")
rep("""    steps.push({t:'Alert the crew and announce the location.'});
    if(over) steps.push({t:'Cut power to the overheating equipment.', a:'power', done:false});
    steps.push({t:'Turn the module fans off.', a:'fans', done:!P.vent});
    steps.push({t:'Put on breathing masks.'});
    steps.push({t:'Discharge the extinguisher at the burning item: CO₂ on the US segment, water-based foam on the Russian segment.'});""","""    steps.push({t:'Alert the crew and announce the location.', a:'alert', done:alerted});
    if(over) steps.push({t:'Cut power to the overheating equipment.', a:'power', done:false});
    steps.push({t:'Turn the module fans off.', a:'fans', done:!P.vent});
    steps.push({t:'Put on breathing masks.', a:'masks', done:masksOn});
    steps.push({t:`Discharge an extinguisher at the ${it.name.toLowerCase()}. Water mist leaves the air breathable. CO₂ works fast, but only with everyone on oxygen masks: it makes the air unbreatheable (NTRS 20110012896).`, acts:[['Water mist','mist',sprayed('mist')],['CO₂','co2',sprayed('co2')]]});""")
rep("""    steps.push({t:'Wear masks. If the fire cannot be controlled, prepare to depressurise the affected module or leave the vehicle.'});""",
"""    steps.push({t:'Put on breathing masks.', a:'masks', done:masksOn});
    const mod=MAINM[rid]||rid, inside=(F.crew||[]).filter(c=>(MAINM[c.room]||c.room)===mod&&c.state!=='incapacitated');
    steps.push({t:`Last resort: vent the ${({lab:'Lab module',node:'Node',air:'Airlock'})[mod]} to vacuum. Do it only after everyone is out and its hatches are closed.${inside.length?` ${inside.map(c=>c.name).join(', ')} ${inside.length>1?'are':'is'} still inside.`:''} Venting is slow and can fan the fire before it goes out (NTRS 20260003546).`, a:'depress:'+mod, done:valveOn(mod), warn:inside.length>0});""")
rep("""  if(alarm&&started) notes.push('Smoke detectors have alarmed. On the ISS they sit in the ventilation return, so they detect smoke the fans carry to them.');""",
"""  if(alarm&&started) notes.push('Smoke detectors have alarmed. On the ISS they sit in the ventilation return, so they detect smoke the fans carry to them.');
  for(const c of (F.crew||[])){ if(c.state==='blocked') notes.unshift(`⚠ ${c.name} is blocked by a closed hatch in the ${G.ROOMS.find(r=>r.id===c.room).name.toLowerCase()}. Open it or they cannot reach safety.`);
    else if(c.state==='incapacitated') notes.unshift(`✕ ${c.name} is incapacitated (${c.why}, dose ${c.fed.toFixed(2)}).`); else if(c.fed>=0.3) notes.unshift(`${c.name} is impaired (dose ${c.fed.toFixed(2)}). Get them to clean air.`); }
  const coMax=Math.max(...st.map(r=>r.co)); if(coMax>425) notes.push(`CO has reached ${Math.round(coMax)} ppm, above the 1-hour spacecraft limit of 425 ppm. Keep masks on.`);
  if(F.valves&&F.valves.some(x=>x)) notes.push('A module is venting. Repressurise it before anyone goes back in.');""")
rep("""function advice(){
  const it=G.ITEMS[sel], mk=it.m, mat=G.MAT[mk], a=AS&&AS.assess[sel], st=F.stats;""","""const MAINM={lab:'lab',rack:'lab',node:'node',cqp:'node',cqs:'node',air:'air'};
const sprayed=k=>!!(F&&F.sprays&&F.sprays.some(s_=>s_.kind===k));
const valveOn=mod=>{ const i=G.VALVES.findIndex(v_=>v_.room===mod); return i>=0&&F&&F.valves&&F.valves[i]; };
function advice(){
  const it=G.ITEMS[sel], mk=it.m, mat=G.MAT[mk], a=AS&&AS.assess[sel], st=F.stats;
  const masksOn=!!(F.crew&&F.crew.some(c=>c.mask)), alerted=!!(F.actions&&F.actions.some(x=>x.do==='alert'));""")
rep("""    <ol>${A.steps.map(s_=>`<li>${s_.t}${s_.a?` <button type="button" data-act="${s_.a}" ${s_.done?'disabled':''}>${s_.done?'Done':'Do it'}</button>`:''}</li>`).join('')}</ol>""",
    """    <ol>${A.steps.map(s_=>`<li${s_.warn?' class="warn"':''}>${s_.t}${s_.a?` <button type="button" data-act="${s_.a}" ${s_.done?'disabled':''}>${s_.done?'Done':'Do it'}</button>`:''}${(s_.acts||[]).map(([l,a_,d_])=>` <button type="button" data-act="${a_}" ${d_?'disabled':''}>${d_?l+' ✓':l}</button>`).join('')}</li>`).join('')}</ol>""")
rep("""  if(sig===advSig&&!force) return; advSig=sig;""","""  if(sig===advSig&&!force) return; advSig=sig;
  if(quiz&&quiz.state==='ask'){ $('advice').className='advice lv-info'; $('advice').innerHTML='<div class="adv-head"><span class="sev">Quiz</span><h2>Guidance hidden while you answer</h2></div><p class="adv-what">Choose your first action in the training quiz below the tracker.</p>'; return; }""")
rep("""const sig=JSON.stringify([A.level,A.title,A.what,A.steps.map(s_=>s_.t+(s_.done?1:0)),A.notes,sel,P.vent,P.X,P.Pk,P.g]);""",
    """const sig=JSON.stringify([A.level,A.title,A.what,A.steps.map(s_=>s_.t+(s_.done?1:0)+(s_.acts||[]).map(x=>x[2]?1:0).join('')),A.notes,sel,P.vent,P.X,P.Pk,P.g,quiz&&quiz.state]);""")

# ---- new functions (before the controls section)
NEW=r'''
// ---------------- crew response ----------------
function respond(a,prefix){ if(!G) return; prefix=prefix||''; const it=G.ITEMS[sel];
  if(a==='alert'){ send({cmd:'do',c:{do:'alert'}}); addLog(-1,prefix+'crew alerted'); }
  else if(a==='masks'){ send({cmd:'do',c:{do:'masks'}}); addLog(-1,prefix+'crew putting on oxygen masks'); }
  else if(a==='co2'||a==='mist'){ send({cmd:'do',c:{do:a,i:sel}}); addLog(G.ROOMS.findIndex(r=>r.id===it.room),`${prefix}${a==='co2'?'CO₂':'water-mist'} extinguisher discharged at the ${it.name.toLowerCase()}`); }
  else if(a.startsWith('depress:')){ const room=a.slice(8), on=!valveOn(room); send({cmd:'do',c:{do:'depress',room,on}}); addLog(G.ROOMS.findIndex(r=>r.id===room),`${prefix}${on?'venting':'vent valve closed:'} ${G.ROOMS.find(r=>r.id===room).name}`); }
  resume(); }
$('rsAlert').onclick=()=>respond('alert'); $('rsMasks').onclick=()=>respond('masks'); $('rsCO2').onclick=()=>respond('co2'); $('rsMist').onclick=()=>respond('mist');
$('dpGo').onclick=()=>respond('depress:'+$('dpRoom').value);
$('dpRoom').onchange=syncResponse;
function syncResponse(){ if(!G||!F) return; const on=valveOn($('dpRoom').value); $('dpGo').textContent= on? 'Close vent valve' : 'Vent to vacuum'; $('dpGo').classList.toggle('on',on);
  $('rsMasks').disabled=!!(F.crew&&F.crew.some(c=>c.mask)); $('rsCO2').classList.toggle('on',sprayed('co2')); $('rsMist').classList.toggle('on',sprayed('mist')); }
function renderCrew(){ if(!F||!F.crew) return; const el=$('crew');
  el.innerHTML=F.crew.map(c=>{ const st={normal:'at post',moving:'moving to '+(c.goal?G.ROOMS.find(r=>r.id===c.goal).short:'safety'),safe:'safe',blocked:'blocked by a closed hatch',incapacitated:'incapacitated: '+c.why}[c.state]||c.state;
    const w=Math.min(100,c.fed*100), n=c.now||{};
    return `<div class="cm" style="border-left-color:${crewColor(c)}"><div class="nm"><span>${c.name}${c.asleep?' <span class="foot">(was asleep)</span>':''}</span><span class="st" style="color:${crewColor(c)}">${st}</span></div>
      <div class="fedbar" role="img" aria-label="dose ${c.fed.toFixed(2)}"><i style="width:${w}%;background:${crewColor(c)}"></i><b style="left:30%"></b></div>
      <dl><dt>Where</dt><dd>${G.ROOMS.find(r=>r.id===c.room).short}</dd><dt>Dose (FED)</dt><dd>${c.fed.toFixed(3)}</dd><dt>CO / HCN / heat / low O₂</dt><dd>${c.fedCO.toFixed(2)} / ${c.fedCN.toFixed(2)} / ${c.fedHeat.toFixed(2)} / ${c.fedO.toFixed(2)}</dd>
      <dt>Breathing now</dt><dd>${n.masked?'oxygen mask':`CO ${n.co??0} ppm · O₂ ${n.o2??'—'}%`}</dd><dt>Visibility here</dt><dd>${n.vis>=99?'clear':(n.vis??'—')+' m'}</dd></dl></div>`; }).join(''); }

// ---------------- fast-forward and replay ----------------
function ffGo(until,secs){ if(!G) return; if(ffOn){ send({cmd:'ffStop'}); return; } if($('rpOn').checked){ $('rpOn').checked=false; send({cmd:'replay',on:false}); }
  ffOn=true; $('ffNote').textContent= until==='ignition'?'running until a flame appears…': until==='alarm'?'running until a smoke alarm…' : `running ${secs/60} min…`; send({cmd:'ff',until,secs}); renderHud(); }
$('ffIgn').onclick=()=>ffGo('ignition',900); $('ffAlarm').onclick=()=>ffGo('alarm',900); $('ff60').onclick=()=>ffGo('time',60); $('ff300').onclick=()=>ffGo('time',300);
function onFFDone(d){ ffOn=false; $('ffNote').textContent= d.reason==='flame'? `flame at ${fmtT(d.t)}` : d.reason==='alarm'? `alarm at ${fmtT(d.t)}` : d.reason==='limit'? `nothing happened in 15 min` : d.reason==='stopped'?'stopped':`now ${fmtT(d.t)}`;
  if(quiz&&quiz.state==='run') quizAsk(); if(auto) auto.onff&&auto.onff(d); }
$('rpOn').onchange=e=>{ replayMode=e.target.checked; send({cmd:'replay',on:replayMode,t:+$('rpT').value}); if(replayMode&&running){ running=false; syncPlay(); send({cmd:'run',running,speed}); } };
$('rpT').oninput=e=>{ if(!$('rpOn').checked){ $('rpOn').checked=true; replayMode=true; if(running){ running=false; syncPlay(); send({cmd:'run',running,speed}); } } send({cmd:'replay',on:true,t:+e.target.value}); $('rpOut').textContent=fmtT(+e.target.value)+' / '+fmtT(F?F.recT:0); };

// ---------------- compare runs ----------------
const runs={}; let recWait=null;
function scenLabel(){ const it=G.ITEMS[sel]; return `${it.name} (${G.MAT[it.m].name.split(' (')[0]}) · ${P.X.toFixed(1)}% · ${P.Pk.toFixed(1)} kPa · ${P.g>0?P.g+' g':'0 g'}`; }
function onRec(d){ if(d.tag==='csv'){ downloadCSV(d); return; } if(d.tag==='scen'){ downloadScenario(d); return; }
  runs[d.tag]={label:scenLabel(), series:d.series, actions:d.actions}; drawCmp(); }
$('saveA').onclick=()=>send({cmd:'getRec',tag:'A'}); $('saveB').onclick=()=>send({cmd:'getRec',tag:'B'}); $('clearAB').onclick=()=>{ delete runs.A; delete runs.B; drawCmp(); };
$('cmpMetric').onchange=()=>drawCmp();
const MET={hrr:r=>r.rooms.reduce((a,x)=>a+x.hrr,0), co:r=>Math.max(...r.rooms.map(x=>x.co)), vis:r=>Math.min(...r.rooms.map(x=>x.vis)), T:r=>Math.max(...r.rooms.map(x=>x.T)), o2:r=>Math.min(...r.rooms.map(x=>x.o2)), fed:r=>r.crew.length?Math.max(...r.crew.map(c=>c.fed)):0, pk:r=>Math.min(...r.rooms.map(x=>x.pk))};
function runSummary(R){ const s_=R.series; if(!s_.length) return null; const pk=Math.max(...s_.map(MET.hrr)), co=Math.max(...s_.map(MET.co)), vis=Math.min(...s_.map(MET.vis)), fed=Math.max(...s_.map(MET.fed));
  let out=null; const on=s_.map(r=>r.rooms.some(x=>x.flame>0)); for(let i=on.length-1;i>0;i--){ if(on[i-1]&&!on[i]){ out=s_[i].t; break; } if(on[i]) break; }
  return {pk,co,vis,fed,out,end:s_[s_.length-1].t}; }
function drawCmp(){ const c=$('cmp'), ctx=c.getContext('2d'); fit(c,1.9); const W=c.width,H=c.height, dpr=W/(c.clientWidth||W), mk=$('cmpMetric').value, f=MET[mk];
  const sets=[['A','#2f6fd6'],['B','#d9822b']].filter(([k])=>runs[k]);
  let tmax=60, ymax=0.1, ymin=0; for(const [k] of sets){ for(const r of runs[k].series){ tmax=Math.max(tmax,r.t); const v=f(r); if(v>ymax) ymax=v; } }
  if(mk==='vis'){ ymax=Math.min(99,Math.max(10,ymax)); } if(mk==='o2'){ ymin=Math.max(0,Math.floor(Math.min(...sets.flatMap(([k])=>runs[k].series.map(f)),P.X)-1)); ymax=Math.max(ymax,P.X+1); }
  if(mk==='pk'){ ymin=0; ymax=Math.max(ymax,110); }
  const yt=[ymin,+(ymin+(ymax-ymin)/2).toFixed(2),+ymax.toFixed(2)];
  const {X,Y}=axes(ctx,W,H,48*dpr,8*dpr,8*dpr,30*dpr,tmax,ymin,ymax*1.05,'simulated time, s','',[0,Math.round(tmax/4),Math.round(tmax/2),Math.round(3*tmax/4),Math.round(tmax)],yt);
  for(const [k,col] of sets){ ctx.beginPath(); runs[k].series.forEach((r,i)=>{ const v=Math.min(ymax*1.05,f(r)); i?ctx.lineTo(X(r.t),Y(v)):ctx.moveTo(X(r.t),Y(v)); }); ctx.strokeStyle=col; ctx.lineWidth=2*dpr; ctx.stroke(); }
  if(!sets.length){ ctx.fillStyle=CSS.muted; ctx.textAlign='center'; ctx.fillText('Save a run as A or B to compare.',W/2,H/2); }
  $('cmpLegend').innerHTML=sets.map(([k,col])=>`<span><i class="sw" style="background:${col}"></i>${k}: ${runs[k].label}</span>`).join('');
  $('cmpTab').querySelector('tbody').innerHTML=sets.map(([k])=>{ const S_=runSummary(runs[k]); if(!S_) return ''; return `<tr><td><b>${k}</b></td><td class="foot">${runs[k].label}<br>${runs[k].actions.map(a_=>`${fmtT(a_.t)} ${a_.do}${a_.id?' '+a_.id:''}${a_.room?' '+a_.room:''}`).join(' · ')}</td><td class="num">${S_.pk.toFixed(1)} kW</td><td class="num">${Math.round(S_.co)} ppm</td><td class="num">${S_.vis>=99?'clear':S_.vis.toFixed(1)+' m'}</td><td class="num">${S_.fed.toFixed(2)}</td><td class="num">${S_.out===null?'—':fmtT(S_.out)}</td></tr>`; }).join(''); }

// ---------------- export and scenarios ----------------
async function saveFile(name,data,note){ const el=$(note||'dlNote');
  try{ const dl=window.claude&&window.claude.use? await window.claude.use('downloads') : null;
    if(dl){ await dl.save({filename:name,data}); el.textContent='Saved '+name; return; } }
  catch(e){ if(e&&e.code==='declined'){ el.textContent='Cancelled'; return; } if(e&&e.code==='rate_limited'){ el.textContent='Another save is waiting for confirmation'; return; } }
  try{ const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([data],{type:name.endsWith('.csv')?'text/csv':'application/json'})); a.download=name; document.body.appendChild(a); a.click(); setTimeout(()=>{ URL.revokeObjectURL(a.href); a.remove(); },500); el.textContent='Downloaded '+name; }
  catch(_){ el.textContent='Downloads are not available in this view.'; } }
$('dlCSV').onclick=()=>send({cmd:'getRec',tag:'csv'}); $('dlScen').onclick=()=>send({cmd:'getRec',tag:'scen'});
function downloadCSV(d){ if(!d.series.length){ $('dlNote').textContent='Nothing recorded yet.'; return; }
  const head=['t_s']; d.rooms.forEach(r=>{ for(const q of ['hrr_kW','Tmax_C','O2min_pct','CO_ppm','HCN_ppm','HF_ppm','CO2_pct','visibility_m','pressure_kPa','dp_Pa','flame_cells']) head.push(r+'_'+q); }); d.crew.forEach(c=>{ head.push(c+'_FED',c+'_state',c+'_room'); });
  const rows=[head.join(',')]; for(const r of d.series){ const a=[r.t]; for(const x of r.rooms) a.push(x.hrr,x.T,x.o2,x.co,x.hcn,x.hf,x.co2,x.vis,x.pk,x.dp,x.flame); for(const c of r.crew) a.push(c.fed,c.state,c.room); rows.push(a.join(',')); }
  saveFile(`spacecraft_fire_${G.ITEMS[sel].id}_${Date.now().toString(36)}.csv`,rows.join('\n')); }
function scenarioObj(actions){ return {format:'blackfox-spacecraft-scenario/1', label:scenLabel(), grid_cell_m:h,
  atmosphere:{gravity_g:P.g,o2_pct:P.X,pressure_kpa:P.Pk,diffuser_cm_s:P.U,fans:true},
  materials:Object.fromEntries(G.ITEMS.map(i=>[i.id,i.m])), removed:G.ITEMS.filter((i,ii)=>itemsOff&&itemsOff[ii]).map(i=>i.id), closed:[], origin:G.ITEMS[sel].id,
  script:(actions||[]).map(a_=>{ const o=Object.assign({},a_); return o; })}; }
function downloadScenario(d){ saveFile(`spacecraft_fire_scenario_${G.ITEMS[sel].id}.json`, JSON.stringify(scenarioObj(d.actions),null,2)); }
$('scenFile').onchange=e=>{ const f=e.target.files[0]; if(!f) return; const r=new FileReader(); r.onload=()=>{ $('scenText').value=r.result; $('scenNote').textContent='File read. Press Load scenario.'; }; r.readAsText(f); };
$('scenLoad').onclick=()=>{ let sc; try{ sc=JSON.parse($('scenText').value); }catch(e){ $('scenNote').textContent='That is not valid JSON: '+e.message; return; } loadScenario(sc); };
function loadScenario(sc){ if(!G) return; const a=sc.atmosphere||{};
  Object.assign(P,{g:a.gravity_g??P.g,X:a.o2_pct??P.X,Pk:a.pressure_kpa??P.Pk,U:a.diffuser_cm_s??P.U,vent:true}); clearPreset();
  if(sc.origin){ const i=G.ITEMS.findIndex(x=>x.id===sc.origin); if(i>=0) sel=i; }
  log=[]; roomFirst=[]; hist=[]; send({cmd:'scenario',sc}); running=true; syncPlay(); send({cmd:'run',running,speed}); syncControls();
  $('scenNote').textContent=`Loaded: ${(sc.script||[]).length} timed action${(sc.script||[]).length===1?'':'s'}.`; }
function renderItemsOn(){ if(!G) return; const el=$('itemsOn'); el.innerHTML='';
  G.ITEMS.forEach((it,i)=>{ const b=document.createElement('button'); b.type='button'; const on=!(itemsOff&&itemsOff[i]); b.className=on?'':'closed'; b.textContent=(on?'On board · ':'Removed · ')+it.name;
    b.onclick=()=>{ itemsOff[i]=on; log=[]; roomFirst=[]; hist=[]; send({cmd:'itemOn',i,on:!on}); setStatus('Rebuilding…','s-idle'); }; el.appendChild(b); }); }

// ---------------- training quiz ----------------
let quiz=null, quizScore=[0,0];
const QOPTS=[['power','Cut power to the item'],['fans','Turn the fans off'],['mist','Water-mist extinguisher at the item'],['co2','CO₂ extinguisher at the item'],['evac','Close the hatch and move the crew away'],['depress','Vent the module to vacuum'],['open','Open hatches to clear the smoke']];
const QPRE=[{t:'ISS cabin',g:0,X:21,Pk:101.3},{t:'Exploration atmosphere',g:0,X:34,Pk:56.5},{t:'Mars transit',g:0,X:26.5,Pk:70.3},{t:'Lunar lander',g:0.165,X:34,Pk:56.5}];
$('quizStart').onclick=()=>{ if(!G) return; const r=Math.random, it=G.ITEMS[Math.floor(r()*G.ITEMS.length)], ii=G.ITEMS.indexOf(it), mat=it.opts[Math.floor(r()*it.opts.length)], at=QPRE[Math.floor(r()*QPRE.length)];
  const mode= ['L1','L7'].includes(it.id)? (r()<0.6?'severe':'overheat') : r()<0.25? 'severe' : 'flame';
  sel=ii; quiz={state:'run', item:ii, mat, at, mode, t0:0, answer:null};
  Object.assign(P,{g:at.g,X:at.X,Pk:at.Pk,U:40,vent:true}); clearPreset(); syncControls();
  log=[]; roomFirst=[]; hist=[]; send({cmd:'scenario',sc:{atmosphere:{gravity_g:at.g,o2_pct:at.X,pressure_kpa:at.Pk,diffuser_cm_s:40},materials:{[it.id]:mat},script:[{t:0.5,do:'igniteItem',i:ii,mode}]}});
  running=false; syncPlay(); send({cmd:'run',running,speed}); setTimeout(()=>{ ffOn=true; send({cmd:'ff',until:'alarm',secs:600}); },300);
  $('quizBody').innerHTML=`<p><b>Scenario:</b> ${mode==='flame'?'open flame on':mode==='severe'?'severe electrical overheat of':'electrical overheat of'} the ${it.name.toLowerCase()} (${G.MAT[mat].name}), ${at.t.toLowerCase()}. Running until the smoke alarm…</p>`; };
function quizAsk(){ quiz.state='ask'; renderAdvice(true); const st=F.stats, fire=st.some(r=>r.flame>0), over=F.qxOn&&F.qxOn.some(x=>x);
  quiz.phase= fire? (st.filter(r=>r.flame>0).length>=2||st.reduce((a,r)=>a+r.hrr,0)>20000? 'evac':'fire') : over? 'over' : 'clear';
  const desc={fire:'Smoke alarm, and there are flames at the item.',evac:'The fire is large and spreading.',over:'Smoke alarm, but no flame yet: the item is overheating and smoking.',clear:'Smoke alarm. The flame has already gone out by itself.'}[quiz.phase];
  $('quizBody').innerHTML=`<p><b>${fmtT(F.t)}:</b> ${desc} What do you do first?</p><div class="btns">${QOPTS.map(([k,l])=>`<button type="button" data-q="${k}">${l}</button>`).join('')}</div>`;
  $('quizBody').querySelectorAll('button[data-q]').forEach(b=>b.onclick=()=>quizAnswer(b.dataset.q)); }
function quizGrade(k){ const ph=quiz.phase, orbit=P.g<0.05;
  const T={over:{best:['power'],ok:['fans','mist'],bad:{depress:'Venting is a last resort and nothing is burning yet.',open:'Opening hatches spreads toxic smoke to the crew.',co2:'There is no flame yet; CO₂ makes the air unbreatheable without oxygen masks.'},why:'An overheating item keeps smoking and can ignite until its power is cut. Removing the heat source comes first.'},
    fire:{best:['mist','co2'],ok:['fans','power','evac'],bad:{depress:'Venting is slow, needs the module empty and sealed, and can fan the fire (NTRS 20260003546).',open:'Opening hatches feeds the fire and spreads smoke.'},why:`A small fire is best put out at once with an extinguisher. Water mist keeps the air breathable; CO₂ works too but requires oxygen masks.${orbit?' In orbit, switching the fans off also starves many flames.':''}`},
    evac:{best:['evac'],ok:['fans','mist','co2'],bad:{depress:'Vent only after everyone is out and the hatch is closed.',open:'Opening hatches spreads the fire and smoke.'},why:'A large fire cannot be fought safely. Get the crew out, isolate the module, then decide on further steps.'},
    clear:{best:['fans','power'],ok:['mist','evac'],bad:{depress:'The flame is out; venting would only add risk.',open:'Opening hatches spreads the smoke and CO to clean modules.',co2:'With no flame, CO₂ only adds a toxic gas.'},why:'With the flame out, stop the smoke spreading, remove any heat source, and clean the air with masks on.'}}[quiz.phase];
  return T.best.includes(k)? [2,'Best choice.',T.why] : T.ok.includes(k)? [1,'Acceptable, but not the first priority.',T.why] : [0,'Not recommended. '+(T.bad[k]||''),T.why]; }
function quizAnswer(k){ const [pts,head,why]=quizGrade(k); quizScore[0]+=pts; quizScore[1]+=2; $('quizScore').textContent=`score ${quizScore[0]} / ${quizScore[1]}`;
  const it=G.ITEMS[quiz.item], rid=it.room, mod=MAINM[rid]||rid;
  if(k==='power') respond('power'); else if(k==='fans') act('fans'); else if(k==='mist'||k==='co2') respond(k);
  else if(k==='evac'){ respond('alert'); for(const id of hatchesFor(rid).slice(0,1)) act('close:'+id); }
  else if(k==='depress') respond('depress:'+mod); else if(k==='open'){ G.OPEN.forEach((o,oi)=>{ if(!isOpen(o.id)) toggleOpen(oi); }); }
  if(k==='power') send({cmd:'do',c:{do:'power'}});
  quiz.state='watch'; quiz.answer=k; quiz.tAns=F.t; quiz.out=null;
  $('quizBody').innerHTML=`<p><b>${head}</b> ${why}</p><p class="foot">Your action has been applied. Watching the next 90 s at ×8…</p>`;
  running=true; syncPlay(); send({cmd:'run',running,speed:Math.max(speed,8)}); renderAdvice(true); }
function quizTick(){ if(!quiz||quiz.state!=='watch'||!F||F.replay) return; if(F.t-quiz.tAns<90) return; quiz.state='done';
  const st=F.stats, fire=st.some(r=>r.flame>0), fed=F.crew&&F.crew.length?Math.max(...F.crew.map(c=>c.fed)):0, inc=(F.crew||[]).filter(c=>c.state==='incapacitated').length, co=Math.max(...st.map(r=>r.co));
  $('quizBody').innerHTML+=`<p><b>Outcome after 90 s:</b> ${fire?'the fire is still burning':'no flame'} · highest CO ${Math.round(co)} ppm · worst crew dose ${fed.toFixed(2)}${inc?` · ${inc} crew incapacitated`:''}. Start another round, or keep watching.</p>`; }

// ---------------- whole-model validation plots ----------------
const SAFF=/*__SAFFIRE__*/null;
function renderSaffire(){ if(!SAFF) { $('saffTab').querySelector('tbody').innerHTML='<tr><td colspan="7" class="foot">Validation results not embedded in this build.</td></tr>'; return; }
  const cell=(m,meas,cal,dig)=>{ if(m===null||m===undefined) return '—'; const v=(+m).toFixed(dig??1); if(meas===undefined) return `${v} <span class="foot">(no data)</span>`; const e=(m-meas)/meas*100;
    return `${v} <span class="foot">vs ${meas}${cal?' · calibration':` · ${e>=0?'+':''}${e.toFixed(0)}%`}</span>`; };
  $('saffTab').querySelector('tbody').innerHTML=SAFF.tests.map(T=>{ const m=T.model, M=T.meas, iv=T.id==='Saffire IV-1';
    return `<tr><td>${T.id}<div class="foot">${T.m==='cotton'?'cotton jersey':'SIBAL fabric'} ${Math.round(T.L*100)}×${Math.round(T.W*100)} cm</div></td><td class="foot">${T.X}% O₂ · ${T.Pk} kPa · ${T.vol} m³</td>
      <td class="num">${cell(m.spread,M.spread,T.id==='Saffire-1'||T.id==='Saffire VI-2',2)}</td><td class="num">${cell(m.hrrMean/1000,M.hrr?M.hrr/1000:undefined,false,2)}</td><td class="num">${cell(m.coMean,M.co,iv,0)}</td><td class="num">${cell(m.dp,M.dp,iv,0)}</td><td class="num">${m.alarm===null?'no alarm':cell(m.alarm,M.alarm,iv,0)}</td></tr>`; }).join(''); }
function parityPts(){ const pts=[]; for(const r of G.valid) if(r.mv&&r.mv[1]>0&&r.use==='independent') pts.push([r.mv[0],r.mv[1],'sub',r.name]);
  if(SAFF) for(const T of SAFF.tests){ const m=T.model, M=T.meas, iv=T.id==='Saffire IV-1';
    if(M.spread&&m.spread&&!(T.id==='Saffire-1'||T.id==='Saffire VI-2')) pts.push([M.spread,m.spread,'3d',T.id+' spread']);
    if(M.hrr&&m.hrrMean) pts.push([M.hrr/1000,m.hrrMean/1000,'3d',T.id+' heat']);
    if(M.burn&&m.burn) pts.push([M.burn/100,m.burn/100,'3d',T.id+' burn time']);
    if(!iv&&M.co) pts.push([M.co/100,m.coMean/100,'3d',T.id+' CO']); if(!iv&&M.dp) pts.push([M.dp/10,m.dp/10,'3d',T.id+' pressure']);
    if(!iv&&M.alarm&&m.alarm) pts.push([M.alarm/100,m.alarm/100,'3d',T.id+' alarm']); }
  return pts; }
function drawParity(){ const c=$('parity'); if(!c||!G) return; const ctx=c.getContext('2d'); fit(c,1.25); const W=c.width,H=c.height, dpr=W/(c.clientWidth||W), L=44*dpr,R=10*dpr,T_=10*dpr,B=34*dpr;
  ctx.fillStyle=CSS.panel; ctx.fillRect(0,0,W,H); const lo=-1.3, hi=1.0, X=v=>L+(W-L-R)*(Math.log10(v)-lo)/(hi-lo), Y=v=>H-B-(H-T_-B)*(Math.log10(v)-lo)/(hi-lo);
  ctx.strokeStyle=CSS.line; ctx.lineWidth=1; ctx.strokeRect(L,T_,W-L-R,H-T_-B); ctx.fillStyle=CSS.muted; ctx.font=`${10*dpr}px IBM Plex Mono, monospace`; ctx.textAlign='center';
  for(const v of [0.1,0.3,1,3,10]){ ctx.fillText(v,X(v),H-B+14*dpr); ctx.textAlign='right'; ctx.fillText(v,L-5*dpr,Y(v)+3*dpr); ctx.textAlign='center'; }
  ctx.fillText('measured (scaled units)',L+(W-L-R)/2,H-4*dpr); ctx.save(); ctx.translate(11*dpr,T_+(H-T_-B)/2); ctx.rotate(-Math.PI/2); ctx.fillText('model',0,0); ctx.restore();
  ctx.save(); ctx.beginPath(); ctx.rect(L,T_,W-L-R,H-T_-B); ctx.clip();
  for(const [f,dash] of [[1,[]],[1.3,[4*dpr,3*dpr]],[1/1.3,[4*dpr,3*dpr]],[2,[1.5*dpr,3*dpr]],[0.5,[1.5*dpr,3*dpr]]]){ ctx.setLineDash(dash); ctx.strokeStyle=f===1?CSS.ink:CSS.muted; ctx.beginPath(); ctx.moveTo(X(0.04),Y(0.04*f)); ctx.lineTo(X(12),Y(12*f)); ctx.stroke(); } ctx.setLineDash([]);
  const pts=parityPts(); for(const [m_,v,k] of pts){ ctx.fillStyle= k==='3d'? CSS.crit : CSS.accent; ctx.beginPath(); ctx.arc(X(m_),Y(v),4*dpr,0,7); ctx.fill(); } ctx.restore();
  const n=pts.length, w30=pts.filter(([a,b])=>b/a<=1.3&&b/a>=1/1.3).length, w2=pts.filter(([a,b])=>b/a<=2&&b/a>=0.5).length;
  c.setAttribute('aria-label',`${n} independent checks: ${w30} within 30%, ${w2} within a factor of 2`); c.title=pts.map(p_=>`${p_[3]}: measured ${p_[0]}, model ${(+p_[1]).toFixed(2)}`).join('\n');
  ctx.fillStyle=CSS.ink; ctx.textAlign='left'; ctx.font=`600 ${11*dpr}px IBM Plex Sans, sans-serif`; ctx.fillText(`${w30}/${n} within 30% · ${w2}/${n} within 2×`,L+8*dpr,T_+16*dpr); }
function drawConv(){ const c=$('conv'); if(!c||!SAFF||!SAFF.convergence) { if($('convNote')) $('convNote').textContent= SAFF&&!SAFF.convergence? 'Convergence runs not included in this build.' : ''; return; }
  const ctx=c.getContext('2d'); fit(c,1.25); const W=c.width,H=c.height, dpr=W/(c.clientWidth||W); const runs_=SAFF.convergence.runs.filter(r=>r.spread!==null);
  const fin=runs_[runs_.length-1], keys=[['spread','spread',CSS.crit],['hrrMean','mean heat',CSS.warn],['coMean','cabin CO',CSS.accent],['alarm','alarm time','#7d8f2f']];
  const {X,Y}=axes(ctx,W,H,40*dpr,10*dpr,10*dpr,32*dpr,16,0,2,'cell size, cm','',[0,5,7.5,10,15],[0,0.5,1,1.5,2]);
  for(const [k,_,col] of keys){ ctx.beginPath(); let pen=false; for(const r of runs_){ if(r[k]===null||!fin[k]) continue; const v=r[k]/fin[k]; pen?ctx.lineTo(X(r.h*100),Y(Math.min(2,v))):ctx.moveTo(X(r.h*100),Y(Math.min(2,v))); pen=true; ctx.fillStyle=col; } ctx.strokeStyle=col; ctx.lineWidth=2*dpr; ctx.stroke();
    for(const r of runs_){ if(r[k]===null||!fin[k]) continue; ctx.fillStyle=col; ctx.beginPath(); ctx.arc(X(r.h*100),Y(Math.min(2,r[k]/fin[k])),3.5*dpr,0,7); ctx.fill(); } }
  $('convNote').innerHTML=keys.map(([k,l,col])=>`<span style="color:${col}">■</span> ${l}`).join(' · ')+`. Each value is divided by the ${Math.round(fin.h*1000)/10} cm result. `+
    `Spread ${runs_.map(r=>r.spread.toFixed(2)).join(' → ')} mm/s; mean heat ${runs_.map(r=>(r.hrrMean/1000).toFixed(2)).join(' → ')} kW.`; }

// ---------------- automated self-test (#autotest) ----------------
let auto=null;
function autoTick(){ if(!auto||!auto.check) return; auto.check(); }
if(location.hash.startsWith('#autotest')){ auto={log:[],t0:performance.now(),step:'wait'};
  const out=(o)=>{ let el=$('autotest'); if(!el){ el=document.createElement('pre'); el.id='autotest'; document.body.appendChild(el); } el.textContent=JSON.stringify(o); el.dataset.done='1'; document.title='AUTOTEST '+(o.pass?'PASS':'FAIL'); };
  auto.check=()=>{ if(!G||!F) return;
    if(auto.step==='wait'){ auto.step='ff'; sel=G.ITEMS.findIndex(i=>i.id==='L1'); send({cmd:'do',c:{do:'igniteItem',i:sel,mode:'severe'}}); ffGo('ignition',600); }
    else if(auto.step==='ff2'&&!ffOn){ auto.step='co2'; respond('co2'); ffGo('time',60); }
    else if(auto.step==='done'){ auto.check=null; } };
  auto.onff=d=>{ if(auto.step==='ff'){ const vis=flames.filter(f=>f.visible).length; auto.ign={reason:d.reason,t:+d.t.toFixed(1)};
      setTimeout(()=>{ updateFx(); auto.flameSprites=flames.filter(f=>f.visible).length; auto.adviceDuring=$('advice').className; auto.hud=$('hud').textContent.slice(0,80); auto.step='ff2'; },400); }
    else if(auto.step==='co2'){ const st=F.stats; auto.step='done';
      out({pass: auto.ign.reason==='flame' && auto.flameSprites>0 && /lv-(act|evac)/.test(auto.adviceDuring) && F.sprays.length>0 && F.crew.length===4, ignition:auto.ign, flameSprites:auto.flameSprites, adviceDuring:auto.adviceDuring,
        afterCO2:{t:+F.t.toFixed(1), flames:st.reduce((a,r)=>a+r.flame,0), ext:F.ext, agentMax:Math.max(...st.map(r=>r.agent)).toFixed(1)}, crew:F.crew.map(c=>c.id+':'+c.state), wall_s:+((performance.now()-auto.t0)/1000).toFixed(1)}); } }; }
'''
rep("""// ---------------- controls ----------------""", NEW+"""
// ---------------- controls ----------------""")
# validation renders also the whole-model table and plots
rep("""function renderValidation(){ $('valid').querySelector('tbody').innerHTML=G.valid.map(r=>{""","""function renderValidation(){ renderSaffire(); requestAnimationFrame(()=>{ drawParity(); drawConv(); }); $('valid').querySelector('tbody').innerHTML=G.valid.map(r=>{""")
rep("""  fit($('growth'),4); drawMap(); drawGMap(); if(F) drawGrowth();""","""  fit($('growth'),4); drawMap(); drawGMap(); if(F) drawGrowth(); if(G){ drawParity(); drawConv(); drawCmp(); }""")
# reset clears quiz/replay
rep("""$('reset').onclick=()=>{ log=[]; roomFirst=[]; hist=[]; send({cmd:'reset'});""","""$('reset').onclick=()=>{ log=[]; roomFirst=[]; hist=[]; ffOn=false; $('ffNote').textContent=''; $('rpOn').checked=false; replayMode=false; if(quiz){ quiz=null; $('quizBody').textContent='No round in progress.'; } send({cmd:'reset'});""")
# keyboard/play resumes from replay
rep("""$('play').onclick=()=>{ running=!running; syncPlay(); send({cmd:'run',running,speed}); };""","""$('play').onclick=()=>{ running=!running; if(running&&$('rpOn').checked){ $('rpOn').checked=false; replayMode=false; send({cmd:'replay',on:false}); } syncPlay(); send({cmd:'run',running,speed}); };""")
# sources list additions
rep(""" ['McGrattan et al.: FDS combustion and extinction modelling','https://files.thunderheadeng.com/femtc/2018_d1-01-mcgrattan-paper.pdf'],""",""" ['McGrattan et al.: FDS combustion and extinction modelling','https://files.thunderheadeng.com/femtc/2018_d1-01-mcgrattan-paper.pdf'],
 ['Heat and Smoke Emission from Tests on the Saffire VI Experiment (Table 1: Saffire IV–VI)','https://ntrs.nasa.gov/citations/20260001992'],
 ['Selected Parametric Effects on Materials Flammability Limits (NASA-STD-6001 Test 1 MOCs)','https://ntrs.nasa.gov/citations/20110008636'],
 ['Risks of Depress as a Fire Suppression Technique in Spacecraft','https://ntrs.nasa.gov/citations/20260003546'],
 ['Development of the ISS Fine Water Mist Portable Fire Extinguisher','https://ntrs.nasa.gov/citations/20130011664'],
 ['Developing Standards to Qualify a Fine Water Mist Extinguisher (CO₂ and respirators)','https://ntrs.nasa.gov/citations/20110012896'],
 ['Carbon Dioxide Dispersion in the Combustion Integrated Rack (CO₂ PFE requirement)','https://ntrs.nasa.gov/citations/20050215297'],
 ['ISO 13571 / Purser: fractional effective dose for toxic gases and heat','https://www.iso.org/standard/56172.html'],""")
p.write_text(s,encoding='utf-8'); print('js patched',len(s))
