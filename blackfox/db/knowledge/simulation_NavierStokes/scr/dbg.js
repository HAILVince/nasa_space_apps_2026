const {createSolver}=require('./solver.js');
const S=createSolver({h:0.125,iters:30,g:1,X:21,Pk:101.3,U:10});
const gal=S.ROOMS.findIndex(r=>r.id==='gal'); const pk=S.MKEYS.indexOf('paper');
const cand=S.fuelList.filter(k=>S.room[k]===gal&&S.mat[k]===pk); const k0=cand[Math.floor(cand.length/2)];
console.log('paper cells',cand.length,'k0 faces',S.faces[k0].toString(2));
S.ignite(k0);
for(let s=0;s<1500;s++){ S.step(0.25); if(s%150===0){ let fl=0,ht=0,bu=0,out=0,pmax=0; for(const k of cand){ if(S.fst[k]===2)fl++; if(S.fst[k]===1){ht++; pmax=Math.max(pmax,S.prog[k]);} if(S.fst[k]===4)bu++; if(S.fst[k]===3)out++; }
  const nb=[]; for(const k of cand) if(S.fst[k]===2) nb.push(k);
  console.log('t',S.t.toFixed(0),'flame',fl,'heat',ht,'pmax',pmax.toFixed(2),'burnt',bu,'out',out,'ext',S.extMode,'mA0',S.mA[k0].toExponential(2)); } }
