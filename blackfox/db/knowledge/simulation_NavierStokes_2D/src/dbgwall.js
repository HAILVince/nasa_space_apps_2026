const {createSolver}=require('./solver.js');
const S=createSolver({dim:2,h:0.05,iters:30,g:1,X:21,Pk:101.3,U:10});
const I=S.info, gal=S.ROOMS.findIndex(r=>r.id==='gal'), lm=S.MKEYS.indexOf('sibal');
const col=S.fuelList.filter(k=>S.room[k]===gal&&S.mat[k]===lm&&(S.faces[k]&1)).sort((a,b)=>a-b);
console.log('wall column cells', col.length, col.slice(0,4).map(k=>[k%I.nx,Math.floor(k/I.nx)%I.ny]));
S.ignite(col[0]);
for(let s=0;s<400;s++){ S.step(0.25); if(s%40===0){ console.log('t',S.t.toFixed(0), col.slice(0,8).map(k=>S.fst[k]+':'+S.prog[k].toFixed(2)).join(' '), JSON.stringify(S.probe(col[0]))); } }
