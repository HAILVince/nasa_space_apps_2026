// Headless test: stability, timing, calibration and room-to-room spread for each preset.
const {createSolver}=require('./solver.js');
const h=+(process.argv[2]||0.125), secs=+(process.argv[3]||300);
const PRE=[
  ['ISS-like 0 g',      {g:0,     X:21, Pk:101.3, U:20}],
  ['0 g fans off',      {g:0,     X:21, Pk:101.3, U:0, vent:false}],
  ['Lunar SEA',         {g:0.165, X:34, Pk:56.5,  U:10}],
  ['Lunar air',         {g:0.165, X:21, Pk:101.3, U:10}],
  ['Mars SEA (Nomex)',  {g:0.378, X:34, Pk:56.5,  U:15, lining:'nomex'}],
  ['Earth',             {g:1,     X:21, Pk:101.3, U:10}],
];
let S0=null;


const which=process.argv[4]? [PRE[+process.argv[4]]] : PRE;
for(const [name,q] of which){
  const S=createSolver(Object.assign({h,iters:30},q,{vent:q.vent??true}));
  // ignite the food packaging in the Galley
  const gal=S.ROOMS.findIndex(r=>r.id==='gal'); const pk=S.MKEYS.indexOf('paper');
  const cand=S.fuelList.filter(k=>S.room[k]===gal&&S.mat[k]===pk); const k0=cand[Math.floor(cand.length/2)];
  S.ignite(k0);
  if(!S0){S0=S; console.log('grid',S.info.nx,S.info.ny,S.info.nz,'fuel',S.fuelList.length); for(const k of S.MKEYS){ const m=S.MAT[k]; console.log(k.padEnd(6),'R',m.R.toFixed(3),'Tc',m.Tc.toFixed(0),'UboO',m.UboO.toFixed(1),'UboC',m.UboC.toFixed(1),'kc',m.kc.toFixed(4)); } }
  const t0=Date.now(); const first={}; let steps=0, nanf=false;
  while(S.t<secs){ S.step(0.25); steps++;
    if(steps%20===0){ const st=S.stats(); st.forEach((r,i)=>{ if(first[i]===undefined && (r.flame>0)) first[i]=S.t; });
      if(!Number.isFinite(S.T[k0+1])) { nanf=true; break; } } }
  const ms=Date.now()-t0; const st=S.stats();
  let Tmax=0; for(let k=0;k<S.info.N;k++) if(S.type[k]===0&&S.T[k]>Tmax) Tmax=S.T[k];
  console.log(`${name.padEnd(18)} ${(ms/steps).toFixed(1)}ms/step dt~${(secs/steps).toFixed(2)} ${nanf?'NaN!':''}`);
  console.log('   fire first in:', S.ROOMS.map((r,i)=>r.id+':'+(first[i]!==undefined?first[i].toFixed(0):'-')).join(' '), ' ext:',S.extMode);
  console.log('   now flame/burnt:', st.map((r,i)=>S.ROOMS[i].id+':'+r.flame+'/'+r.burnt).join(' '));
  console.log('   Tmax °C:', st.map(r=>Math.round(r.Tmax-273)).join('/'), ' Xmin:', st.map(r=>r.Xmin.toFixed(1)).join('/'), ' vis m:', st.map(r=>r.vis.toFixed(1)).join('/'), ' HRR kW:', st.map(r=>(r.hrr/1000).toFixed(1)).join('/'), ' dP Pa:', st.map(r=>r.pbg.toFixed(0)).join('/'));
}
