// Which ignition sites spread between rooms in 2D? Reports rooms reached in 600 s.
const {createSolver}=require('./solver.js');
const pi=+process.argv[2], site=process.argv[3];
const PRE=[['ISS',{g:0,X:21,Pk:101.3,U:20}],['',{}],['LunarSEA',{g:0.165,X:34,Pk:56.5,U:10}],['LunarAir',{g:0.165,X:21,Pk:101.3,U:10}],['MarsSEA',{g:0.378,X:34,Pk:56.5,U:15,lining:'sibal'}],['Earth',{g:1,X:21,Pk:101.3,U:10}]];
const [name,q]=PRE[pi]; const S=createSolver(Object.assign({dim:2,h:0.05,iters:30},q));
const R=n=>S.ROOMS.findIndex(r=>r.id===n);
const pick={pack:()=>S.fuelList.filter(k=>S.room[k]===R('gal')&&S.mat[k]===S.MKEYS.indexOf('paper')),
  bag:()=>S.fuelList.filter(k=>S.room[k]===R('crew')&&S.mat[k]===S.MKEYS.indexOf('nomex')),
  rack:()=>S.fuelList.filter(k=>S.room[k]===R('lab')&&S.mat[k]===S.MKEYS.indexOf('sibal')&&S.faces[k]!==8),
  cargo:()=>S.fuelList.filter(k=>S.room[k]===R('stow')&&S.mat[k]===S.MKEYS.indexOf('sibal')&&S.faces[k]!==8)}[site]();
pick.sort((a,b)=>a-b); S.ignite(pick[0]);
const first={}; let peak=S.ROOMS.map(()=>295), hrr=0;
while(S.t<600){ S.step(0.25); const st=S.stats(); st.forEach((r,i)=>{ if(first[i]===undefined&&r.flame>0) first[i]=S.t; peak[i]=Math.max(peak[i],r.Tmax); }); hrr=Math.max(hrr, st.reduce((a,r)=>a+r.hrr,0)); }
console.log(name.padEnd(9), site.padEnd(6), 'rooms:', S.ROOMS.map((r,i)=>r.id+':'+(first[i]!==undefined?first[i].toFixed(0):'-')).join(' '), ' peakC', peak.map(T=>Math.round(T-273)).join('/'), ' peakHRR kW/m', (hrr/1000/S.info.h).toFixed(0), ' burnt', S.stats().map(r=>r.burnt).join('/'));
