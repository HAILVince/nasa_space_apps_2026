// Spacecraft solver test: geometry sanity, assessments, and fire behaviour from several origins.
const {createSolver}=require('./solver.js');
const args=process.argv.slice(2); const h=+(args[0]||0.15), secs=+(args[1]||240), item=args[2]||'L1', mode=args[3]||'flame', atm=args[4]||'iss';
const ATM={iss:{g:0,X:21,Pk:101.3,U:40}, explo:{g:0,X:34,Pk:56.5,U:40}, lunar:{g:0.165,X:34,Pk:56.5,U:40}, mars:{g:0,X:26.5,Pk:70.3,U:40}, off:{g:0,X:21,Pk:101.3,U:40,vent:false}};
const t0=Date.now(); const S=createSolver(Object.assign({h,iters:24},ATM[atm])); const tb=Date.now()-t0;
const cnt=a=>{ let c=0; for(const x of a) if(x) c++; return c; };
console.log(`grid ${S.info.nx}x${S.info.ny}x${S.info.nz} N=${S.info.N} gas=${S.type.filter(x=>x===0).length} fuel=${S.fuelList.length} sup=${cnt(S.sup)} ret=${cnt(S.ret)} build ${tb}ms`);
console.log('rooms gas cells:', S.ROOMS.map((r,ri)=>r.short+':'+S.room.reduce((a,x,k)=>a+(x===ri&&S.type[k]===0?1:0),0)).join(' '));
console.log('openings:', S.OPEN.map(o=>o.id+':'+o.cells.length).join(' '), ' items:', S.ITEMS.map(i=>i.id+':'+i.cells.length).join(' '));
const as=S.assess(); console.log('assess:', as.map(a=>`${S.ITEMS[a.i].id}(${S.ITEMS[a.i].m}) U=${a.U} ${a.exists?'BURNS':'no'} lim=${a.lim}`).join(' | '));
const ii=S.ITEMS.findIndex(i=>i.id===item); S.igniteItem(ii,mode);
let steps=0; const t1=Date.now(); const first={}; let peakHRR=0;
while(S.t<secs){ S.step(0.25); steps++; if(steps%8===0){ const st_=S.stats(); peakHRR=Math.max(peakHRR,st_.reduce((a,r)=>a+r.hrr,0)); } if(steps%8===0) S.stats().forEach((r,i)=>{ if(first[i]===undefined&&r.flame>0) first[i]=S.t; if(first['s'+i]===undefined&&r.ext>=0.1) first['s'+i]=S.t; }); }
const ms=Date.now()-t1, st=S.stats();
console.log('  peak HRR kW', (peakHRR/1000).toFixed(1)); console.log(`${atm} ${item} ${mode}: ${(ms/steps).toFixed(1)} ms/step, x${(secs*1000/ms).toFixed(1)} realtime, ext=${S.extMode}`);
console.log('  fire first :', S.ROOMS.map((r,i)=>r.short+':'+(first[i]!==undefined?first[i].toFixed(0):'-')).join(' '));
console.log('  smoke alarm:', S.ROOMS.map((r,i)=>r.short+':'+(first['s'+i]!==undefined?first['s'+i].toFixed(0):'-')).join(' '));
let hp=0; console.log('  now flame/burnt:', st.map(r=>r.flame+'/'+r.burnt).join(' '), ' Tmax C', st.map(r=>Math.round(r.Tmax-273)).join('/'), ' vis', st.map(r=>r.vis.toFixed(1)).join('/'));
