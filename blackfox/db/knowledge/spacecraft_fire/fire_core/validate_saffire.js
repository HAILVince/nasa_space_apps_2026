// Whole-model validation: the full 3D engine (gas flow, combustion, radiation, solids, species) reproduces the Saffire
// large-scale fire tests flown in Cygnus. A sample sits in a 20 cm/s flow duct inside a sealed cabin of the measured free
// volume. Measured values: NTRS 20170008805 (Saffire-1) and NTRS 20260001992 Table 1 (Saffire IV–VI).
// Usage: node validate_saffire.js [h=0.1] [convergence: 0|1]  → writes validation_results.json
const {createSolver}=require('./engine.js');
const fs=require('fs');
const H=+(process.argv[2]||0.1), CONV=process.argv[3]==='1', HVa=process.argv[4]!==undefined?+process.argv[4]:undefined, ONLY=process.argv[5]||'';
const TESTS=[
  {id:'Saffire-1', m:'sibal', L:0.94, W:0.406, X:21.7, Pk:101.3, vol:17.9, meas:{spread:1.8, hrr:1200, burn:420}, note:'94 × 40.6 cm SIBAL, concurrent flow'},
  {id:'Saffire IV-1', m:'sibal', L:0.5, W:0.4, X:23, Pk:98.0, vol:17.9, meas:{spread:3.6, co:77.4, dp:33, alarm:92}, note:'CO yield calibrated here'},
  {id:'Saffire V-2', m:'cotton', L:0.5, W:0.4, X:28, Pk:74.1, vol:19, meas:{spread:3.4, co:74.3, dp:30, alarm:146}, note:'cotton jersey'},
  {id:'Saffire VI-2', m:'sibal', L:0.5, W:0.4, X:31, Pk:54.1, vol:16.7, meas:{spread:4.05, hrr:3376, co:122, dp:31, alarm:201}, note:'O₂ exponent of the spread model calibrated on this spread rate'},
];
function run(T,h){
  const S=createSolver({layout:'saffire', h, iters:24, hv:HVa, g:0, X:T.X, Pk:T.Pk, U:20, vent:true, saffire:{L:T.L,W:T.W,m:T.m,vol:T.vol,sides:2}});
  const it=S.ITEMS[0], x0=S.LYT.sample.x0, I=S.info, colOf=k=>k%I.nx;
  const cols=[...new Set(it.cells.map(colOf))].sort((a,b)=>a-b), first=cols[0];
  for(const k of it.cells) if(colOf(k)===first) S.ignite(k);
  const pr=S.LYT.probe, track=[], win=[]; let peak=0, hsum=0, hn=0, coMax=0, coMean=0, dp=0, alarm=null, tOut=null, wall=Date.now();
  const tEnd= T.meas.burn? 700 : 420;
  while(S.t<tEnd){ S.step(0.25);
    let fl=0; for(const k of it.cells) if(S.fst[k]===2) fl++;
    let F=0; for(const c of cols){ let st=0; for(const k of it.cells) if(colOf(k)===c){ const f=S.fst[k]; st=Math.max(st, f>=2? 1 : Math.min(0.999,S.prog[k])); } F+=st; }
    let hrr=0; for(let k=0;k<I.N;k++) hrr+=S.hrr[k];
    track.push([S.t,F*h,hrr,fl]); win.push([S.t,hrr]); while(win.length&&win[0][0]<S.t-10) win.shift(); if(fl>0){ const av=win.reduce((a,r)=>a+r[1],0)/win.length; peak=Math.max(peak,av); hsum+=hrr*S.lastDt; hn+=S.lastDt; }
    const p=S.probeAt(...pr); if(p){ coMax=Math.max(coMax,p.co); if(alarm===null&&p.aerosol>=2) alarm=S.t; }
    const st=S.stats()[0]; dp=Math.max(dp,st.pbg); coMean=st.coMean;
    if(fl===0&&S.t>5&&tOut===null) tOut=S.t; if(fl>0) tOut=null;
    if(tOut!==null&&S.t>tOut+90&&S.t>200) break; }
  // spread rate: slope of the front position between 20% and 80% of the sample length
  const L=cols.length*h, sel=track.filter(r=>r[1]>=0.2*L&&r[1]<=0.8*L); let spread=null;
  if(sel.length>3){ const n=sel.length, mx=sel.reduce((a,r)=>a+r[0],0)/n, my=sel.reduce((a,r)=>a+r[1],0)/n; let sxy=0,sxx=0; for(const r of sel){ sxy+=(r[0]-mx)*(r[1]-my); sxx+=(r[0]-mx)**2; } spread=1000*sxy/sxx; }
  const burn=(()=>{ const on=track.filter(r=>r[3]>0); return on.length? on[on.length-1][0]-on[0][0] : 0; })();
  return {h, spread, hrrPeak:peak, hrrMean: hn? hsum/hn : 0, burn, co:coMax, coMean, dp, alarm, cells:it.cells.length, wall_s:(Date.now()-wall)/1000,
    series:track.filter((r,i)=>i%4===0).map(r=>[+r[0].toFixed(1),+r[1].toFixed(3),+(r[2]/1000).toFixed(3)])};
}
const out={engine:'fire_core/engine.js v5', when:new Date().toISOString(), h:H, tests:[], convergence:null};
for(const T of TESTS){ if(ONLY&&!T.id.includes(ONLY)) continue; const r=run(T,H); out.tests.push({...T, model:r});
  console.log(`${T.id}: spread ${r.spread?.toFixed(2)} mm/s (meas ${T.meas.spread}) · HRR mean ${(r.hrrMean/1000).toFixed(2)} kW peak ${(r.hrrPeak/1000).toFixed(2)} kW${T.meas.hrr?` (meas ${T.meas.hrr/1000})`:''} · burn ${r.burn.toFixed(0)} s${T.meas.burn?` (meas ${T.meas.burn})`:''} · CO ${r.coMean.toFixed(0)} ppm (probe max ${r.co.toFixed(0)})${T.meas.co?` (meas ${T.meas.co})`:''} · dp ${r.dp.toFixed(1)} Pa${T.meas.dp?` (meas ${T.meas.dp})`:''} · alarm ${r.alarm===null?'none':r.alarm.toFixed(0)+' s'}${T.meas.alarm?` (meas ${T.meas.alarm})`:''} · ${r.wall_s.toFixed(0)} s wall`); }
if(CONV){ const T=TESTS[1]; out.convergence={test:T.id, runs:[]};
  for(const h of [0.15,0.1,0.075,0.05]){ const r=run(T,h); delete r.series; out.convergence.runs.push(r); console.log(`  conv h=${h}: spread ${r.spread?.toFixed(2)} HRR ${(r.hrrMean/1000).toFixed(2)} kW CO ${r.co.toFixed(0)} dp ${r.dp.toFixed(1)} alarm ${r.alarm} (${r.wall_s.toFixed(0)} s)`); } }
fs.writeFileSync(__dirname+'/validation_results.json', JSON.stringify(out));
console.log('wrote validation_results.json');
