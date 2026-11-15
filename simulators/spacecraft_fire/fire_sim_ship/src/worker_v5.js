let S=null, running=true, speed=8, wallLast=0, simTarget=0, achieved=0, lastPost=0, cfg=null, selMat='pe', ff=null, rec=null, replayOn=false;
function itemsOut(){ return S.ITEMS.map(i=>({id:i.id,name:i.name,where:i.where,room:i.room,m:i.m,opts:i.opts,note:i.note||'',cells:i.cells.slice(),on:i.on})); }
function matInfo(){ return Object.fromEntries(S.MKEYS.map(k=>{const m=S.MAT[k]; return [k,{name:m.name,id:m.id,loi:m.loi??null,test1:m.test1??null,ys:m.ys,ys0:m.ys0,yco:m.yco,yco0:m.yco0,yhcn:m.yhcn,yhf:m.yhf,thick:!!m.thick,src:m.src,m0:m.m0}];})); }
function assessMsg(){ postMessage({type:'assess', assess:S.assess(), matTable:S.matTable(), curves:S.curves(selMat,S.P.Pk), gcurve:S.loiVsG(selMat,S.P.Pk), selMat, P:Object.assign({},S.P)}); }
function geom(){
  postMessage({type:'geom', info:S.info, typeArr:S.type.slice(), room:S.room.slice(), openId:S.openId.slice(), mat:S.mat.slice(), faces:S.faces.slice(),
    sclass:S.sclass.slice(), itemOf:S.itemOf.slice(), sup:S.sup.slice(), ret:S.ret.slice(), fuelList:S.fuelList.slice(),
    ROOMS:S.ROOMS.map(r=>({id:r.id,name:r.name,short:r.short,x0:r.x0,x1:r.x1,ytop:r.ytop,y1:r.y1,c:r.c,vol:r.vol})), OPEN:S.OPEN.map(o=>({id:o.id,name:o.name,open:o.open,cells:o.cells,c:o.c})),
    VALVES:S.VALVES.map(v=>({room:v.room,name:v.name,cells:v.cells})), AGENTS:S.AGENTS,
    ITEMS:itemsOut(), MKEYS:S.MKEYS, MAT:matInfo(), valid:S.validate(), P:Object.assign({},S.P)});
  assessMsg();
}
function snap(){ return {t:S.t, stats:S.stats(), crew:S.crew(), ext:S.extMode, igns:S.igns.slice(), opens:S.OPEN.map(o=>o.open), sprays:S.sprays, valves:S.VALVES.map(v=>v.active), roomPk:S.roomPk(), alarmT:S.alarmT}; }
function frame(extra){
  const f32=a=>Float32Array.from(a), sn=snap();
  const T=f32(S.T), YS=f32(S.YS), YO=f32(S.YO), YC=f32(S.YC), YD=f32(S.YD), YW=f32(S.YW), G=f32(S.G), u=f32(S.u), v=f32(S.v), w=f32(S.w), fst=S.fst.slice(), qxOn=Uint8Array.from(S.qx,x=>x>0?1:0);
  postMessage(Object.assign({type:'frame', dt:S.lastDt, achieved, T,YS,YO,YC,YD,YW,G,u,v,w,fst,qxOn, actions:S.actions.slice(), ff:ff?{until:ff.until,left:Math.max(0,ff.max-S.t)}:null, recLen:rec?rec.series.length:0, recT:rec&&rec.keys.length?rec.keys[rec.keys.length-1].t:0}, sn, extra||{}),
    [T.buffer,YS.buffer,YO.buffer,YC.buffer,YD.buffer,YW.buffer,G.buffer,u.buffer,v.buffer,w.buffer,fst.buffer,qxOn.buffer]);
}
// ---- recording: one row per simulated second, a compressed 3D keyframe every 5 s (for replay)
function recReset(){ const gas=[]; for(let k=0;k<S.info.N;k++) if(S.type[k]===0) gas.push(k); rec={series:[], keys:[], gas:Int32Array.from(gas), lastRow:-1, lastKey:-1}; }
function record(){
  if(!rec) recReset();
  const t=S.t;
  if(t-rec.lastRow>=1||rec.lastRow<0){ rec.lastRow=t; const st=S.stats(), cr=S.crew(), pk=S.roomPk();
    rec.series.push({t:+t.toFixed(1), rooms:st.map((r,i)=>({hrr:+(r.hrr/1000).toFixed(3),T:+(r.Tmax-273.15).toFixed(1),o2:+r.Xmin.toFixed(2),co:+r.co.toFixed(1),hcn:+r.hcn.toFixed(2),hf:+r.hf.toFixed(2),co2:+r.co2.toFixed(3),vis:+r.vis.toFixed(2),pk:+pk[i].toFixed(2),flame:r.flame,dp:+r.pbg.toFixed(1)})), crew:cr.map(c=>({fed:c.fed,state:c.state,room:c.room}))});
    if(rec.series.length>7200) rec.series.shift(); }
  if((t-rec.lastKey>=5||rec.lastKey<0) && rec.keys.length<360){ rec.lastKey=t; const g=rec.gas, n=g.length;
    const qT=new Uint8Array(n), qS=new Uint8Array(n), qO=new Uint8Array(n), qC=new Uint8Array(n);
    for(let q=0;q<n;q++){ const k=g[q]; qT[q]=Math.max(0,Math.min(255,(S.T[k]-290)/1210*255)); qS[q]=Math.min(255,Math.sqrt(Math.max(0,S.YS[k])/2e-3)*255);
      qO[q]=Math.max(0,Math.min(255,S.YO[k]/0.4*255)); qC[q]=Math.min(255,Math.log10(1+S.ppm(S.YC[k],28))/5*255); }
    rec.keys.push({t, qT,qS,qO,qC, fst:S.fst.slice(), snap:snap()}); }
}
function replayFrame(t){
  if(!rec||!rec.keys.length) return; let K=rec.keys[0]; for(const k of rec.keys){ if(k.t<=t+1e-6) K=k; else break; }
  const N=S.info.N, g=rec.gas, T=new Float32Array(N).fill(295), YS=new Float32Array(N), YO=new Float32Array(N), YC=new Float32Array(N);
  for(let q=0;q<g.length;q++){ const k=g[q]; T[k]=290+K.qT[q]/255*1210; const s=K.qS[q]/255; YS[k]=s*s*2e-3; YO[k]=K.qO[q]/255*0.4; YC[k]=(Math.pow(10,K.qC[q]/255*5)-1)/1e6*28/28.8; }
  const Z=()=>new Float32Array(N), fst=K.fst.slice(), qxOn=new Uint8Array(N);
  const G=new Float32Array(N).fill(4*5.67e-8*295**4);
  postMessage(Object.assign({type:'frame', replay:true, dt:0, achieved:0, T,YS,YO,YC,YD:Z(),YW:Z(),G,u:Z(),v:Z(),w:Z(),fst,qxOn, actions:S.actions.slice(), ff:null, recLen:rec.series.length, recT:rec.keys[rec.keys.length-1].t}, K.snap));
}
function ffDone(reason){ const f=ff; ff=null; simTarget=S.t; postMessage({type:'ffdone', reason, until:f.until, t:S.t}); frame(); }
function ffCheck(){ if(!ff) return false;
  if(ff.until==='ignition'){ for(const k of S.fuelList) if(S.fst[k]===2){ ffDone('flame'); return true; } }
  else if(ff.until==='alarm'){ if(S.alarmT>=0){ ffDone('alarm'); return true; } }
  if(S.t>=ff.max){ ffDone(ff.until==='time'?'time':'limit'); return true; } return false; }
function tick(){
  if(!S){ setTimeout(tick,50); return; }
  const now=Date.now(), el=Math.min(0.25,(now-wallLast)/1000); wallLast=now;
  if(ff){ const start=Date.now(), t0=S.t; while(Date.now()-start<160){ S.step(0.25); record(); if(ffCheck()) break; }
    achieved=0.8*achieved+0.2*((S.t-t0)/0.16); }
  else if(running&&!replayOn){ simTarget+=el*speed; const t0=S.t, start=Date.now();
    while(S.t<simTarget && Date.now()-start<45){ S.step(0.25); record(); }
    if(S.t<simTarget-2) simTarget=S.t;
    achieved=0.8*achieved+0.2*((S.t-t0)/Math.max(el,1e-3)); }
  if(!replayOn && now-lastPost>(ff?400:140)){ frame(); lastPost=now; }
  setTimeout(tick, (running||ff)?0:60);
}
function doCmd(c){ const ok=S.command(c); frame(); if(c.do==='opening'||c.do==='depress') geom(); return ok; }
function applyScenario(sc){
  const a=sc.atmosphere||{}; S.setParams({g:a.gravity_g??S.P.g, X:a.o2_pct??S.P.X, Pk:a.pressure_kpa??S.P.Pk, U:a.diffuser_cm_s??S.P.U, vent:a.fans??true});
  for(const it of S.ITEMS){ const m=sc.materials&&sc.materials[it.id]; if(m&&S.MAT[m]) it.m=m; it.on= !(sc.removed||[]).includes(it.id); }
  for(const o of S.OPEN) o.open=true; S.reset();
  for(const id of (sc.closed||[])){ const oi=S.OPEN.findIndex(o=>o.id===id); if(oi>=0) S.toggleOpening(oi); }
  S.setScript((sc.script||[]).map(e=>Object.assign({},e))); recReset(); simTarget=S.t;
}
onmessage=e=>{ const m=e.data;
  if(m.cmd==='init'){ cfg=m; selMat=m.selMat||'pe'; S=createSolver(Object.assign({h:m.h,iters:24},m.params)); if(m.mats) m.mats.forEach((mk,i)=>{ if(mk&&S.ITEMS[i]) S.ITEMS[i].m=mk; }); if(m.off) m.off.forEach((o,i)=>{ if(S.ITEMS[i]) S.ITEMS[i].on=!o; }); if(m.mats||m.off) S.reset(); recReset(); simTarget=S.t; geom(); frame(); wallLast=Date.now(); }
  else if(m.cmd==='run'){ running=m.running; if(m.speed) speed=m.speed; simTarget=S?S.t:0; }
  else if(m.cmd==='set'){ S.setParams(m.params); assessMsg(); }
  else if(m.cmd==='reset'){ for(const o of S.OPEN) o.open=true; S.setScript([]); S.reset(); recReset(); ff=null; simTarget=S.t; geom(); frame(); }
  else if(m.cmd==='do'){ doCmd(m.c); }
  else if(m.cmd==='setItemMat'){ S.setItemMaterial(m.i,m.m); selMat=m.m; recReset(); simTarget=S.t; geom(); frame(); }
  else if(m.cmd==='itemOn'){ S.ITEMS[m.i].on=m.on; S.reset(); recReset(); simTarget=S.t; geom(); frame(); }
  else if(m.cmd==='selMat'){ selMat=m.m; assessMsg(); }
  else if(m.cmd==='ff'){ replayOn=false; ff={until:m.until, max:S.t+(m.secs||900)}; }
  else if(m.cmd==='ffStop'){ if(ff) ffDone('stopped'); }
  else if(m.cmd==='replay'){ replayOn=!!m.on; if(replayOn) replayFrame(m.t); else frame(); }
  else if(m.cmd==='getRec'){ postMessage({type:'rec', series:rec?rec.series:[], tag:m.tag, actions:S.actions.slice(), rooms:S.ROOMS.map(r=>r.id), crew:S.crew().map(c=>c.id)}); }
  else if(m.cmd==='scenario'){ applyScenario(m.sc); geom(); frame(); }
};
tick();
