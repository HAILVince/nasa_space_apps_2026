// Spacecraft scenario test for the shared engine: node test_ship.js [h] [secs] [item] [mode] [atm] [script-json]
const {createSolver}=require('./engine.js');
const a=process.argv.slice(2); const h=+(a[0]||0.15), secs=+(a[1]||240), item=a[2]||'L1', mode=a[3]||'flame', atm=a[4]||'iss', scr=a[5]?JSON.parse(a[5]):[];
const ATM={iss:{g:0,X:21,Pk:101.3,U:40}, explo:{g:0,X:34,Pk:56.5,U:40}, lunar:{g:0.165,X:34,Pk:56.5,U:40}, mars:{g:0,X:26.5,Pk:70.3,U:40}, off:{g:0,X:21,Pk:101.3,U:40,vent:false}, earth:{g:1,X:21,Pk:101.3,U:40}};
const t0=Date.now(); const S=createSolver(Object.assign({h,iters:24,layout:process.env.LAYOUT||'ship'},ATM[atm])); const tb=Date.now()-t0;
console.log(`grid ${S.info.nx}x${S.info.ny}x${S.info.nz} N=${S.info.N} fuel=${S.fuelList.length} build ${tb}ms`);
const ii=S.ITEMS.findIndex(i=>i.id===item); S.command({do:'igniteItem',i:ii,mode}); S.setScript(scr.map(e=>Object.assign({},e,{i:e.i===undefined?ii:e.i})));
let steps=0, peak=0; const t1=Date.now(); const first={};
while(S.t<secs){ S.step(0.25); steps++; if(steps%8===0){ const st=S.stats(); peak=Math.max(peak,st.reduce((s,r)=>s+r.hrr,0));
  st.forEach((r,i)=>{ if(first[i]===undefined&&r.flame>0) first[i]=S.t; if(first['s'+i]===undefined&&r.ext>=0.1) first['s'+i]=S.t; }); }
  if(steps%120===0){ const st=S.stats(); console.log(`  t=${S.t.toFixed(0)} hrr=${(st.reduce((s,r)=>s+r.hrr,0)/1000).toFixed(2)}kW flame=${st.map(r=>r.flame).join('/')} COmax=${st.map(r=>r.co.toFixed(0)).join('/')} vis=${st.map(r=>r.vis.toFixed(1)).join('/')} Pk=${st.map(r=>r.Pk.toFixed(1)).join('/')} agent=${st.map(r=>r.agent.toFixed(1)).join('/')}`); } }
const ms=Date.now()-t1, st=S.stats();
console.log(`${atm} ${item} ${mode}: ${(ms/steps).toFixed(1)} ms/step, x${(secs*1000/ms).toFixed(1)} realtime, ext=${S.extMode}, peak ${(peak/1000).toFixed(2)} kW`);
console.log('  fire first :', S.ROOMS.map((r,i)=>r.short+':'+(first[i]!==undefined?first[i].toFixed(0):'-')).join(' '));
console.log('  smoke alarm:', S.ROOMS.map((r,i)=>r.short+':'+(first['s'+i]!==undefined?first['s'+i].toFixed(0):'-')).join(' '));
console.log('  now flame/burnt:', st.map(r=>r.flame+'/'+r.burnt).join(' '), ' Tmax C', st.map(r=>Math.round(r.Tmax-273)).join('/'), ' CO ppm', st.map(r=>r.co.toFixed(0)).join('/'), ' HCN', st.map(r=>r.hcn.toFixed(1)).join('/'), ' HF', st.map(r=>r.hf.toFixed(0)).join('/'));
console.log('  crew:', S.crew().map(c=>`${c.id}:${c.state}@${c.room} FED=${c.fed} ${c.why}`).join(' | '));
console.log('  actions:', JSON.stringify(S.actions));
