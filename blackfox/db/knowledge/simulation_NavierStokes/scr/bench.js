const {createSolver}=require('./solver.js');
for(const it of (process.argv[2]||"30,20,10").split(",").map(Number)){
 const S=createSolver({h:0.125,iters:it,g:0.165,X:34,Pk:56.5,U:10});
 let t0=process.hrtime.bigint(); for(let i=0;i<40;i++) S.step(0.2); let t1=process.hrtime.bigint();
 console.log('iters',it,'ms/step',(Number(t1-t0)/1e6/40).toFixed(1),'gas cells',S.type.filter(x=>x===0).length);
}
