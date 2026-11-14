const {createSolver}=require('./solver.js');
const S=createSolver({dim:2,h:0.05,iters:30,g:1,X:21,Pk:101.3,U:10});
const I=S.info, idx=(i,j)=>i+I.nx*(j+I.ny*1);
const gal=S.ROOMS.findIndex(r=>r.id==='gal'), lm=S.MKEYS.indexOf('sibal');
const col=S.fuelList.filter(k=>S.room[k]===gal&&S.mat[k]===lm&&(S.faces[k]&1)).sort((a,b)=>a-b);
S.ignite(col[0]);
const watch=[idx(31,30),idx(32,31),idx(33,31),idx(34,31),idx(36,31),idx(40,31),idx(46,31)];
console.log('types', watch.map(k=>S.type[k]+'/f'+S.faces[k]+'/r'+S.room[k]).join(' '));
let nxt=0; while(S.t<300){ S.step(0.25); if(S.t>=nxt){ nxt+=25;{ console.log('t',S.t.toFixed(0), watch.map(k=>S.fst[k]+':'+S.prog[k].toFixed(2)+':'+S.mA[k].toFixed(3)).join('  '), 'probe ceil', JSON.stringify(S.probe(idx(33,31)))); } }
}
