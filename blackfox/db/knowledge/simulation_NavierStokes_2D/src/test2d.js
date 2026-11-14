// 2D solver test: timing and room-to-room spread per preset (one preset per process for honest timing).
const {createSolver}=require('./solver.js');
const h=+(process.argv[2]||0.05), secs=+(process.argv[3]||300), pi=+(process.argv[4]||2);
const PRE=[['ISS-like 0 g',{g:0,X:21,Pk:101.3,U:20}],['0 g fans off',{g:0,X:21,Pk:101.3,U:0,vent:false}],['Lunar SEA',{g:0.165,X:34,Pk:56.5,U:10}],
 ['Lunar air',{g:0.165,X:21,Pk:101.3,U:10}],['Mars SEA Nomex',{g:0.378,X:34,Pk:56.5,U:15,lining:'nomex'}],['Earth',{g:1,X:21,Pk:101.3,U:10}]];
const [name,q]=PRE[pi]; const S=createSolver(Object.assign({dim:2,h,iters:30},q));
const gal=S.ROOMS.findIndex(r=>r.id==='gal'), lm=S.MKEYS.indexOf(S.P.lining); const c=S.fuelList.filter(k=>S.room[k]===gal&&S.mat[k]===lm&&(S.faces[k]&1)).sort((a,b)=>a-b); S.ignite(c[0]); console.log('ignite wall lining cell', c[0]%S.info.nx, Math.floor(c[0]/S.info.nx)%S.info.ny);
const first={}; let steps=0; const t0=Date.now(); let peak=S.ROOMS.map(()=>295);
while(S.t<secs){ S.step(0.25); steps++; if(steps%10===0){ S.stats().forEach((r,i)=>{ if(first[i]===undefined&&r.flame>0) first[i]=S.t; peak[i]=Math.max(peak[i],r.Tmax); }); } }
const ms=Date.now()-t0, st=S.stats();
console.log(`${name.padEnd(16)} grid ${S.info.nx}x${S.info.ny} gas ${S.type.filter(x=>x===0).length} fuel ${S.fuelList.length}  ${(ms/steps).toFixed(1)} ms/step  dt ${(secs/steps).toFixed(3)}  x${(secs*1000/ms).toFixed(1)} realtime`);
console.log('   fire first:', S.ROOMS.map((r,i)=>r.id+':'+(first[i]!==undefined?first[i].toFixed(0):'-')).join(' '), ' ext:', S.extMode);
console.log('   peak °C:', peak.map(T=>Math.round(T-273)).join('/'), ' now flame/burnt:', st.map(r=>r.flame+'/'+r.burnt).join(' '));
