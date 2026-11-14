// Runs solver + worker wrapper exactly as embedded in the page, with a fake message channel.
const fs=require('fs'); const html=fs.readFileSync('../habitat_fire_section_2d.html','utf8');
const grab=id=>{ const a=html.indexOf('id="'+id+'">')+('id="'+id+'">').length; return html.slice(a, html.indexOf('</'+'script>',a)); };
const src=grab('solver-src')+'\n'+grab('worker-src');
const msgs=[]; global.postMessage=(d)=>msgs.push(d);
const api=new Function('postMessage', src.replace(/^onmessage=/m,'globalThis.__onmsg=').replace(/\ntick\(\);\s*$/,'\n')+'\nreturn {tick};')(global.postMessage);
globalThis.__onmsg({data:{cmd:'init',h:0.05,params:{g:0.165,X:34,Pk:56.5,U:10,vent:true,lining:'sibal'}}});
globalThis.__onmsg({data:{cmd:'run',running:true,speed:32}});
const t0=Date.now(); let last=null;
(function spin(){ api.tick(); if(Date.now()-t0<20000) setTimeout(spin,0); else {
  const fr=msgs.filter(m=>m.type==='frame'); last=fr[fr.length-1]; const g=msgs.find(m=>m.type==='geom');
  console.log('geom ok', !!g, 'valid rows', g.valid.length, 'curves', g.curves.U.length, 'gcurve', g.gcurve.G.length);
  console.log('frames', fr.length, 'sim t', last.t.toFixed(1), 'achieved x', last.achieved.toFixed(1), 'flaming', last.stats.map(r=>r.flame).join('/'));
  globalThis.__onmsg({data:{cmd:'toggle',oi:1}}); const f2=msgs[msgs.length-1]; console.log('toggle -> opens', f2.opens);
  globalThis.__onmsg({data:{cmd:'set',params:{lining:'pmma'}}}); console.log('relining geom', msgs.filter(m=>m.type==='geom').length);
  process.exit(0); } })();
