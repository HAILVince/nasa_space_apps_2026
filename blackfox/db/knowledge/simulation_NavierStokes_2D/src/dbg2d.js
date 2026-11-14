const {createSolver}=require('./solver.js');
const S=createSolver({dim:2,h:0.05,iters:30,g:0.165,X:34,Pk:56.5,U:10});
const gal=S.ROOMS.findIndex(r=>r.id==='gal'), pk=S.MKEYS.indexOf('paper'); const c=S.fuelList.filter(k=>S.room[k]===gal&&S.mat[k]===pk);
const k0=c[Math.floor(c.length/2)]; const I=S.info;
const ij=k=>[k%I.nx, Math.floor(k/I.nx)%I.ny];
console.log('paper cells',c.length,'k0',ij(k0),'faces',S.faces[k0].toString(2), 'cells list sample', c.slice(0,6).map(ij).join(' '));
S.ignite(k0);
const nb=[]; for(const k of S.fuelList){ const [a,b]=ij(k),[x,y]=ij(k0); if(Math.abs(a-x)<=1&&Math.abs(b-y)<=1&&k!==k0) nb.push(k); }
for(let s=0;s<30;s++){ S.step(0.25); if(s%3===0){
  const n0=k0+S.info.SY; console.log(JSON.stringify(S.probe(k0)));console.log('t',S.t.toFixed(1),'k0 st',S.fst[k0],'mA',S.mA[k0].toExponential(2),'Xabove',S.Xvol(S.YO[k0+S.info.SY]).toFixed(1),'T above',S.T[k0+S.info.SY].toFixed(0),'nbrs',nb.map(k=>S.fst[k]+':'+S.prog[k].toFixed(2)).join(' '),'ext',S.extMode); } }
