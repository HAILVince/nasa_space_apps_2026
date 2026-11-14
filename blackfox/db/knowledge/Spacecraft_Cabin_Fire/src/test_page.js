// Runs the embedded solver + worker exactly as the page does, with a fake message channel.
const fs=require('fs');const h=fs.readFileSync('../spacecraft_cabin_fire.html','utf8');
[...h.matchAll(/<script>([\s\S]*?)<\/script>/g)].forEach(m=>{ try{ new Function(m[1]); console.log('main script syntax ok'); }catch(e){ console.log('SYNTAX ERR',e.message);} });
const grab=id=>{ const a=h.indexOf('id="'+id+'">')+('id="'+id+'">').length; return h.slice(a,h.indexOf('</'+'script>',a)); };
const src=grab('solver-src')+'\n'+grab('worker-src'); const msgs=[]; global.postMessage=x=>msgs.push(x);
const api=new Function('postMessage', src.replace(/^onmessage=/m,'globalThis.__on=').replace(/\ntick\(\);\s*$/,'\n')+'\nreturn {tick};')(global.postMessage);
globalThis.__on({data:{cmd:'init',h:0.15,params:{g:0,X:34,Pk:56.5,U:40,vent:true},selMat:'pe'}});
globalThis.__on({data:{cmd:'run',running:true,speed:32}});
globalThis.__on({data:{cmd:'igniteItem',i:0,mode:'severe'}});
const t0=Date.now(); (function spin(){ api.tick(); if(Date.now()-t0<15000) setTimeout(spin,0); else {
 const g=msgs.find(m=>m.type==='geom'), as=msgs.filter(m=>m.type==='assess').pop(), fr=msgs.filter(m=>m.type==='frame').pop();
 console.log('geom rooms', g.ROOMS.map(r=>r.short+'@'+r.c.map(v=>v.toFixed(1)).join(',')).join(' '));
 console.log('assess', as.assess.length, 'matTable', as.matTable.length, 'curves', as.curves.U.length);
 console.log('frame t', fr.t.toFixed(1), 'x', fr.achieved.toFixed(1), 'flame', fr.stats.map(r=>r.flame).join('/'), 'burnt', fr.stats.map(r=>r.burnt).join('/'), 'ext', fr.ext);
 globalThis.__on({data:{cmd:'setItemMat',i:0,m:'ptfe'}}); console.log('setItemMat ->', msgs.filter(m=>m.type==='geom').pop().ITEMS[0].m);
 process.exit(0);} })();
