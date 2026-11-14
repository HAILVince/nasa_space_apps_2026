// Habitat fire solver v4 — 3D variable-density LES-style fire model for a two-deck habitat.
// Pure JS, no DOM: runs in a Web Worker in the page and in Node for tests.
// Gas phase: incompressible momentum with full density-ratio buoyancy, Smagorinsky SGS viscosity,
//   approximate projection with thermal-expansion divergence (low-Mach style), semi-Lagrangian advection.
// Combustion: mixing-controlled (eddy-dissipation style) with FDS-style critical flame temperature check.
// Solids: thermally thin surfaces; subgrid flame existence from a flame-temperature model
//   (radiative quench / kinetic blowoff), opposed spread from de Ris with the exact thin-fuel π/4 factor,
//   concurrent spread calibrated to Saffire-1, ignition by gas heating from a surface energy balance.
function createSolver(cfg){
'use strict';
// ---------------- constants ----------------
const SIGMA=5.670e-8, CP=1100, DH_O2=13.1e6, T_AMB=295, CHI_R=0.30, T_CFT=1600, T_AIT=700,
      LAMBDA_G=0.06, H_CONV=10, KAPPA=95, UD=0.5, TA=15000, LB=0.012, GAMMA=1.4, M_AIR=0.0288, RU=8.314,
      SOOT_EXT=8700, Y_SOOT_RXN=0.012, CP_MIX=1300, T_CELL_MAX=1500, U_CAP=2.5;
const TF_REF=T_AMB+KAPPA*21;               // adiabatic reference flame temperature in air, K

// ---------------- materials ----------------
// m0: areal mass kg/m², inert: non-combustible fraction (fiberglass / char), cs: J/kg/K, Tv: pyrolysis K,
// s: kg O2 per kg fuel (ΔHc/13.1 MJ), Lg: heat of gasification J/kg, qfl: flame heat flux to own surface W/m².
const MAT={
  sibal:{name:'SIBAL cotton-fiberglass fabric', id:'sibal', m0:0.18, inert:0.25, cs:1300, Tv:620, s:1.23, Lg:2.0e6, qfl:15e3, ys:0.010,
    quench:[[1,21],[5,16]], boOpp:[28,21], boCon:[80,21],
    src:{quench:'BASS-II quench speeds 1–5 cm/s at 21–16% O₂ (ntrs-20150008962)', boOpp:'1 g downward self-extinguishes in air, Lunar g burns (LUCI / FM2)', boCon:'BASS burned at 40 cm/s in air; assumed 80 cm/s'}},
  pmma:{name:'PMMA (acrylic) panel, 3 mm', id:'pmma', m0:3.57, inert:0, cs:1500, Tv:630, s:1.92, Lg:1.6e6, qfl:18e3, ys:0.022,
    Rset:0.35, xmin:16.6, boOpp:[30,18], boCon:[60,18],
    src:{quench:'R assumed; X_min set so the 0 g opposed limit is ~17% (pmc-5760683)', boOpp:'1 g downward limit ~18% (pmc-5760683)', boCon:'Marcum 2016 linear O₂–flow boundary, assumed point'}},
  paper:{name:'Thin cellulose (paper, packaging)', id:'cellulose', m0:0.08, inert:0.05, cs:1300, Tv:600, s:1.23, Lg:2.0e6, qfl:15e3, ys:0.010,
    Rset:0.5, xmin:14.5, boOpp:[34,19], boCon:[90,21],
    src:{quench:'R assumed', boOpp:'paper burns downward in 1 g air; partial g easier (ntrs-19930040901)', boCon:'assumed'}},
  nomex:{name:'Nomex fabric', id:'nomex_iii', m0:0.22, inert:0.40, cs:1200, Tv:800, s:2.1, Lg:3.0e6, qfl:15e3, ys:0.030,
    Rset:0.45, xmin:24.0, boOpp:[30,28.5], boCon:[60,28],
    src:{quench:'ASSUMED: 0 g limits up to 4% O₂ below 1 g (ntrs-20080034883)', boOpp:'ASSUMED: 1 g LOI ~28–29%', boCon:'assumed'}},
};
const MKEYS=Object.keys(MAT);

// ---------------- flame model (also exported for maps and validation) ----------------
function Tflame(m,X,U,P,Tg){ return Tg + KAPPA*X*(1 - m.R*(101.3/P)/(U+UD)); }
function Ubo(ref,X,P,Tf){ return ref*Math.sqrt(Math.max(0,(P/101.3)*(X/21)))*Math.exp(-(TA/2)*(1/Math.max(Tf,300)-1/TF_REF)); }
function Ubuoy(g,L,Tf,Tg){ return 100*Math.sqrt(Math.max(0,g*(LB+L)*(1-Tg/Math.max(Tf,Tg+1)))); }  // cm/s, Froude scaling
function flameState(m,X,Ures,P,Tg,g,Lup){
  // iterate: Tf depends on U through radiative loss, U depends on Tf through buoyancy
  // leading-edge buoyant flow uses the fixed scale LB (buoyant stretch); the flow that drives concurrent
  // spread grows with the burning length above it (Froude scaling, accelerating upward fires in gravity)
  let Tf=Tg+KAPPA*X, U=Ures, Ub=0;
  for(let it=0;it<3;it++){ Ub=Ubuoy(g,0,Tf,Tg); U=Math.hypot(Ures,Ub); Tf=Tflame(m,X,U,P,Tg); }
  const UbL=Ubuoy(g,Lup||0,Tf,Tg), Us=Math.hypot(Ures,UbL);
  const bc=Ubo(m.UboC,X,P,Tf), bo=Ubo(m.UboO,X,P,Tf);
  const rad= Tf>=m.Tc;
  return {Tf,U,Ub,UbL,Us,exists: rad && U<=bc, oppOK: rad && U<=bo, bc, bo, mode: (rad && U<=bc)? 'ok' : U<(m.Uopt||8)? 'quench':'blowoff'};
}
function Vopp(m,fs,Tg,mArea){ // mm/s, de Ris thin-fuel with exact π/4 factor (Delichatsios) and Damköhler factor
  if(!fs.oppOK) return 0;
  const V=(Math.PI/4)*LAMBDA_G*(fs.Tf-m.Tv)/((mArea||m.m0)*m.cs*Math.max(20,m.Tv-Tg));
  return 1000*V*Math.sqrt(Math.max(0,1-fs.U/fs.bo));
}
function Vcon(m,fs){ // mm/s, linear in flow (BASS), calibrated to Saffire-1
  if(!fs.exists) return 0;
  const phi=Math.min(1,Math.max(0,(fs.Tf-m.Tc)/(TF_REF-m.Tc)));
  return m.kc*(fs.Us||fs.U)*phi*Math.sqrt(Math.max(0,1-fs.U/fs.bc));
}
// ---- calibration from knowledge-base targets ----
function calibrate(){
  for(const k of MKEYS){ const m=MAT[k];
    if(m.quench){ const [[U1,X1],[U2,X2]]=m.quench; m.R=(X1-X2)/(X1/(U1+UD)-X2/(U2+UD)); m.Tc=T_AMB+KAPPA*X1*(1-m.R/(U1+UD)); }
    else { m.R=m.Rset; m.Tc=T_AMB+KAPPA*m.xmin; }
    const solveRef=([Ut,Xt])=>{ const Tf=Tflame(m,Xt,Ut,101.3,T_AMB); return Ut/Ubo(1,Xt,101.3,Tf); };
    m.UboO=solveRef(m.boOpp); m.UboC=solveRef(m.boCon);
  }
  // concurrent coefficient: Saffire-1, SIBAL, 0 g, 21.7% O2, 20 cm/s → 1.8 mm/s
  const s=MAT.sibal; s.kc=1; const fs=flameState(s,21.7,20,101.3,T_AMB,0,0); s.kc=1.8/Vcon(s,fs);
  for(const k of MKEYS){ if(k==='sibal') continue; const m=MAT[k];
    // thin concurrent spread scales as q_fl / (m'' c_s (Tv - T∞))
    m.kc=s.kc*(m.qfl/s.qfl)*(s.m0*s.cs*(s.Tv-T_AMB))/(m.m0*m.cs*(m.Tv-T_AMB)); }
}
calibrate();
// ---- limits, curves and validation (used by the page's maps and tables) ----
function limitX(m,U,P,mode,g){ const ok=X=>{ const fs=flameState(m,X,U,P,T_AMB,g||0,0); return mode==='opp'? fs.oppOK : fs.exists; };
  let lo=5, hi=80; if(!ok(hi)) return null; if(ok(lo)) return lo;
  for(let i=0;i<40;i++){ const mid=(lo+hi)/2; if(ok(mid)) hi=mid; else lo=mid; } return hi; }
function quenchU(m,X,P){ const ok=U=>flameState(m,X,U,P,T_AMB,0,0).exists; let lo=0.01, hi=-1;
  for(let U=0.05;U<=60;U*=1.15){ if(ok(U)){ hi=U; break; } lo=U; } if(hi<0) return null; if(ok(0.01)) return 0;
  for(let i=0;i<40;i++){ const mid=(lo+hi)/2; if(ok(mid)) hi=mid; else lo=mid; } return hi; }
for(const k of MKEYS){ const m=MAT[k]; let best=1e9, ub=8; for(let U=0.5;U<=80;U+=0.5){ const x=limitX(m,U,101.3,'con',0); if(x!==null&&x<best){best=x;ub=U;} } m.Uopt=ub; }
function curves(mk,P){ const m=MAT[mk], U=[], con=[], opp=[]; for(let u=0.25;u<=60;u+=0.25){ U.push(u); con.push(limitX(m,u,P,'con',0)); opp.push(limitX(m,u,P,'opp',0)); } return {U,con,opp}; }
function loiVsG(mk,P){ const m=MAT[mk], G=[], down=[], up=[]; for(let g=0;g<=1.0001;g+=0.01){ G.push(+g.toFixed(2)); down.push(limitX(m,0,P,'opp',g*9.81)); up.push(limitX(m,0,P,'con',g*9.81)); } return {G,down,up}; }
function validate(){
  const S_=MAT.sibal, PM=MAT.pmma, rows=[];
  const fsA=(m,X,U,P,g)=>flameState(m,X,U,P,T_AMB,(g||0)*9.81,0);
  const row=(name,cond,meas,model,unit,use,src,note)=>rows.push({name,cond,meas,model,unit,use,src,note});
  row('Concurrent spread, SIBAL','0 g · 21.7% · 101 kPa · 20 cm/s','1.8',Vcon(S_,fsA(S_,21.7,20,101.3)).toFixed(2),'mm/s','calibration','Saffire-1 (NTRS 20170008805)','sets the concurrent coefficient');
  row('Concurrent spread, SIBAL 5 cm strip','0 g · 22.1% · 101 kPa · 20 cm/s','2.1',Vcon(S_,fsA(S_,22.1,20,101.3)).toFixed(2),'mm/s','independent','Saffire-1 narrow sample','narrow strip, not used in fitting');
  const q21=quenchU(S_,21,101.3), q16=quenchU(S_,16,101.3);
  row('Quench flow speed, SIBAL','0 g · 21% · 101 kPa','≈1',q21===null?'none':q21.toFixed(2),'cm/s','calibration','BASS-II (ntrs-20150008962)','');
  row('Quench flow speed, SIBAL','0 g · 16% · 101 kPa','≈5',q16===null?'none':q16.toFixed(2),'cm/s','calibration','BASS-II (ntrs-20150008962)','');
  const lu=fsA(S_,21,0,101.3,0.165);
  row('Downward spread, SIBAL','Lunar g · air · quiescent','0.92–1.1',Vopp(S_,lu,T_AMB,S_.m0).toFixed(2),'mm/s','independent','LUCI, preliminary (ntrs-20250010653)','flame base 0.92, tip 1.1 mm/s');
  const e1=fsA(S_,21,0,101.3,1);
  row('Downward burning, SIBAL','1 g · air · quiescent','self-extinguishes',e1.oppOK?'burns ('+Vopp(S_,e1,T_AMB,S_.m0).toFixed(2)+' mm/s)':'extinguishes','','calibration','LUCI / FM2 (ntrs-20240015307)','sets the opposed blowoff constant');
  const p0=limitX(PM,5,101.3,'opp',0), p1=limitX(PM,0,101.3,'opp',9.81);
  row('Opposed-flow limit, PMMA','0 g · 101 kPa · ~5 cm/s','≈17',p0===null?'none':p0.toFixed(1),'% O₂','calibration','ISS PMMA cylinders (pmc-5760683)','');
  row('Downward limit, PMMA','1 g · 101 kPa · quiescent','≈18',p1===null?'none':p1.toFixed(1),'% O₂','calibration','ISS vs 1 g PMMA (pmc-5760683)','');
  const rib=Object.assign({},PM,{m0:1.19});
  row('Opposed edge spread, PMMA rib','0 g · 26.9% · 76 kPa · 20 cm/s','0.88',Vopp(rib,flameState(rib,26.9,20,76,T_AMB,0,0),T_AMB,1.19).toFixed(2),'mm/s','independent','Saffire V (ntrs-20210017838)','1 mm rib edge; flat-sheet theory misses edge heating');
  const lg=loiVsG('sibal',101.3); let gmin=0,xmin=1e9; lg.G.forEach((g,i)=>{ const x=lg.down[i]; if(x!==null&&x<xmin){xmin=x;gmin=g;} });
  row('Gravity of easiest burning, SIBAL downward','air pressure, quiescent','near Lunar g (~0.16 g)',gmin.toFixed(2)+' g','','qualitative','LPSC 2026 Ferkul et al. (ntrs-20260000646)','');
  const l1=limitX(S_,0,101.3,'con',9.81), l0=Math.min(...curves('sibal',101.3).con.filter(x=>x!==null));
  row('1 g minus best 0 g limit, SIBAL','101 kPa','up to 4',(l1-l0).toFixed(1),'% O₂ pts','qualitative','Exploration atmospheres (ntrs-20080034883)','');
  return rows;
}

// ---------------- grid ----------------
const h=cfg.h||0.125, LX=6, LY=3, LZ=2;
const NXi=Math.round(LX/h), NYi=Math.round(LY/h), NZi=Math.round(LZ/h);
const nx=NXi+2, ny=NYi+2, nz=NZi+2, N=nx*ny*nz, SY=nx, SZ=nx*ny, V=h*h*h, A=h*h;
const id=(i,j,l)=>i+nx*(j+ny*l);
const ci=x=>Math.min(NXi,Math.max(1,Math.floor(x/h+1e-9)+1));
const cj=y=>Math.min(NYi,Math.max(1,Math.floor(y/h+1e-9)+1));
const ck=z=>Math.min(NZi,Math.max(1,Math.floor(z/h+1e-9)+1));
const cx=i=>(i-0.5)*h, cy=j=>(j-0.5)*h, cz=l=>(l-0.5)*h;
const GAS=0, WALL=1, FUEL=2;
const type=new Uint8Array(N), room=new Int8Array(N), openId=new Int8Array(N), sup=new Uint8Array(N), ret=new Uint8Array(N);

const ROOMS=[
  {id:'crew', name:'Crew quarters', deck:'upper', x0:0,  x1:2.5, y0:1.5, y1:3},
  {id:'hyg',  name:'Hygiene',       deck:'upper', x0:2.5,x1:3.5, y0:1.5, y1:3},
  {id:'stow', name:'Stowage',       deck:'upper', x0:3.5,x1:6,   y0:1.5, y1:3},
  {id:'air',  name:'Airlock',       deck:'lower', x0:0,  x1:1.5, y0:0,   y1:1.5},
  {id:'gal',  name:'Galley',        deck:'lower', x0:1.5,x1:3.5, y0:0,   y1:1.5},
  {id:'lab',  name:'Lab',           deck:'lower', x0:3.5,x1:6,   y0:0,   y1:1.5},
];
const OPEN=[
  {id:'D1', name:'Airlock hatch',          plane:'x', pos:1.5, a:[0,1.0],   b:[0.6,1.4], open:true},
  {id:'D2', name:'Galley–Lab door',        plane:'x', pos:3.5, a:[0,1.0],   b:[0.6,1.4], open:true},
  {id:'D3', name:'Crew–Hygiene door',      plane:'x', pos:2.5, a:[1.5,2.5], b:[0.6,1.4], open:true},
  {id:'D4', name:'Hygiene–Stowage door',   plane:'x', pos:3.5, a:[1.5,2.5], b:[0.6,1.4], open:true},
  {id:'H1', name:'Deck hatch Galley–Crew', plane:'y', pos:1.5, a:[2.0,2.7], b:[0.65,1.35], open:true},
  {id:'H2', name:'Deck hatch Lab–Stowage', plane:'y', pos:1.5, a:[4.8,5.5], b:[0.65,1.35], open:true},
];
const ITEMS=[
  {name:'sleeping bag',  room:'crew', m:'nomex', x:[0.30,0.45], y:[1.75,2.8], z:[1.55,1.9]},
  {name:'sleeping bag',  room:'crew', m:'nomex', x:[1.00,1.15], y:[1.75,2.8], z:[1.55,1.9]},
  {name:'sleeping bag',  room:'crew', m:'nomex', x:[1.70,1.85], y:[1.75,2.8], z:[1.55,1.9]},
  {name:'towels',        room:'hyg',  m:'sibal', x:[2.75,3.25], y:[2.1,2.5],  z:[1.55,1.9]},
  {name:'cargo bags',    room:'stow', m:'nomex', x:[3.8,4.6],   y:[1.5,2.1],  z:[0.2,1.8]},
  {name:'cargo bags',    room:'stow', m:'sibal', x:[5.0,5.7],   y:[1.5,2.0],  z:[0.3,1.0]},
  {name:'EVA suit bag',  room:'air',  m:'sibal', x:[0.4,0.8],   y:[0.1,1.2],  z:[1.2,1.8]},
  {name:'food packaging',room:'gal',  m:'paper', x:[2.0,2.8],   y:[0.0,0.4],  z:[1.2,1.85]},
  {name:'galley table',  room:'gal',  m:'pmma',  x:[2.9,3.3],   y:[0.7,0.82], z:[0.5,1.5]},
  {name:'acrylic panels',room:'lab',  m:'pmma',  x:[3.7,3.82],  y:[0.3,1.2],  z:[0.3,1.7]},
  {name:'paperwork',     room:'lab',  m:'paper', x:[4.2,4.8],   y:[0.0,0.2],  z:[1.4,1.85]},
  {name:'rack fabric',   room:'lab',  m:'sibal', x:[5.3,5.8],   y:[0.2,1.2],  z:[1.75,1.9]},
];

// ---------------- state ----------------
const P={g:cfg.g??0.165, X:cfg.X??34, Pk:cfg.Pk??56.5, U:cfg.U??10, vent:cfg.vent??true, lining:cfg.lining||'sibal'};
const u=new Float64Array(N), v=new Float64Array(N), w=new Float64Array(N);
const u2=new Float64Array(N), v2=new Float64Array(N), w2=new Float64Array(N);
// last velocity seen while a cell was cold: the ambient/ventilation flow a surface flame sees (its own induced flow is subgrid, via U_b)
const ucx=new Float64Array(N), ucy=new Float64Array(N), ucz=new Float64Array(N);
const T=new Float64Array(N), YO=new Float64Array(N), YF=new Float64Array(N), YS=new Float64Array(N);
const tmp=new Float64Array(N), p=new Float64Array(N), rhs=new Float64Array(N), D=new Float64Array(N), nut=new Float64Array(N), rho=new Float64Array(N), hrr=new Float64Array(N);
const comp=new Int32Array(N); let comps=[];
// fuel
const mat=new Int8Array(N).fill(-1), faces=new Uint8Array(N), mA=new Float64Array(N), Ts=new Float64Array(N), fst=new Uint8Array(N),
      prog=new Float64Array(N), igT=new Float64Array(N), Lup=new Float64Array(N), flameAdj=new Uint8Array(N), inc=new Float64Array(N);
let fuelList=[], t=0, firstIgn=-1, igns=[], extMode=null, events=[];
const FL={NONE:0, HEAT:1, FLAME:2, OUT:3, BURNT:4};
const NB6=[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]];
const OFF6=NB6.map(([a,b,c])=>a+b*SY+c*SZ);
const NB26=[]; for(let c=-1;c<=1;c++)for(let b=-1;b<=1;b++)for(let a=-1;a<=1;a++){ if(a||b||c) NB26.push([a,b,c,a+b*SY+c*SZ,Math.hypot(a,b,c)]); }
const Y0=()=>{ const X=P.X/100; return X*32/(X*32+(1-X)*28); };
const Xvol=y=>{ const n=y/32, r=(1-y)/28; return 100*n/(n+r); };
const pAmb=()=>P.Pk*1000;

function inside(b,i,j,l){ const x=cx(i),y=cy(j),z=cz(l); return x>=b.x0&&x<b.x1&&y>=b.y0&&y<b.y1&&(b.z0===undefined||(z>=b.z0&&z<b.z1)); }
function build(){
  type.fill(GAS); room.fill(-1); openId.fill(-1); sup.fill(0); ret.fill(0); mat.fill(-1); faces.fill(0);
  for(let l=0;l<nz;l++)for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){ const k=id(i,j,l); if(i===0||j===0||l===0||i===nx-1||j===ny-1||l===nz-1) type[k]=WALL; }
  const jd=cj(1.5);
  for(let l=1;l<=NZi;l++)for(let i=1;i<=NXi;i++) type[id(i,jd,l)]=WALL;
  const partX=(x,y0,y1)=>{ const i=ci(x); for(let l=1;l<=NZi;l++)for(let j=1;j<=NYi;j++){ const y=cy(j); if(y>=y0&&y<y1) type[id(i,j,l)]=WALL; } };
  partX(1.5,0,1.5); partX(3.5,0,1.5); partX(2.5,1.5,3); partX(3.5,1.5,3);
  for(let l=1;l<=NZi;l++)for(let j=1;j<=NYi;j++)for(let i=1;i<=NXi;i++){ const k=id(i,j,l); if(type[k]!==GAS) continue; ROOMS.forEach((r,ri)=>{ if(inside(r,i,j,l)) room[k]=ri; }); }
  OPEN.forEach((o,oi)=>{ const cells=[];
    for(let l=1;l<=NZi;l++){ const z=cz(l); if(z<o.b[0]||z>=o.b[1]) continue;
      if(o.plane==='x'){ const i=ci(o.pos); for(let j=1;j<=NYi;j++){ const y=cy(j); if(y>=o.a[0]&&y<o.a[1]) cells.push(id(i,j,l)); } }
      else { const j=cj(o.pos); for(let i=1;i<=NXi;i++){ const x=cx(i); if(x>=o.a[0]&&x<o.a[1]) cells.push(id(i,j,l)); } } }
    o.cells=cells; for(const k of cells){ openId[k]=oi; type[k]= o.open? GAS : WALL; } });
  for(let l=1;l<=NZi;l++)for(let j=1;j<=NYi;j++){ const y=cy(j), z=cz(l);
    if(y>=2.55&&y<2.95&&z>=0.7&&z<1.3) sup[id(1,j,l)]=1;
    if(y>=0.1&&y<0.5&&z>=0.7&&z<1.3) ret[id(NXi,j,l)]=1; }
  // wall linings: ceilings (face -y) and back walls (face -z) of every room except the airlock
  const lm=MKEYS.indexOf(P.lining);
  for(let l=1;l<=NZi;l++)for(let j=1;j<=NYi;j++)for(let i=1;i<=NXi;i++){ const k=id(i,j,l); const r=room[k]; if(type[k]!==GAS||r<0||ROOMS[r].id==='air'||openId[k]>=0) continue;
    const up=k+SY, back=k+SZ;
    if(type[up]===WALL && openId[up]<0){ type[up]=FUEL; mat[up]=lm; faces[up]|=8; }
    else if(type[up]===FUEL && mat[up]===lm) faces[up]|=8;
    if(type[back]===WALL && openId[back]<0){ type[back]=FUEL; mat[back]=lm; faces[back]|=32; }
    else if(type[back]===FUEL && mat[back]===lm) faces[back]|=32; }
  for(const it of ITEMS){ const mi=MKEYS.indexOf(it.m);
    for(let l=ck(it.z[0]);l<=ck(it.z[1]-1e-6);l++)for(let j=cj(it.y[0]);j<=cj(it.y[1]-1e-6);j++)for(let i=ci(it.x[0]);i<=ci(it.x[1]-1e-6);i++){
      const k=id(i,j,l); if(type[k]!==GAS||openId[k]>=0||sup[k]||ret[k]) continue; type[k]=FUEL; mat[k]=mi; faces[k]=63; it.cells=(it.cells||0)+1; } }
  fuelList=[]; for(let k=0;k<N;k++) if(type[k]===FUEL){
    // keep only faces that touch gas
    let f=0; for(let d=0;d<6;d++) if((faces[k]>>d)&1 && type[k+OFF6[d]]===GAS) f|=1<<d; faces[k]=f;
    if(f) fuelList.push(k); else { type[k]=WALL; mat[k]=-1; } }
  // fuel cells that sit in a room belong to it (for stats); lining cells take the room of their exposed gas
  for(const k of fuelList){ if(room[k]<0){ for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const g=k+OFF6[d]; if(room[g]>=0){ room[k]=room[g]; break; } } } }
  buildComps();
}
function buildComps(){
  comp.fill(-1); comps=[];
  for(let k=0;k<N;k++){ if(type[k]!==GAS||comp[k]>=0) continue;
    const c={vol:0, outlet:false, pbg:0, cells:0}; const ci_=comps.length; comps.push(c);
    const st=[k]; comp[k]=ci_;
    while(st.length){ const q=st.pop(); c.cells++; if(ret[q]) c.outlet=true;
      for(let d=0;d<6;d++){ const n=q+OFF6[d]; if(type[n]===GAS&&comp[n]<0){ comp[n]=ci_; st.push(n); } } }
    c.vol=c.cells*V; }
  buildLists();
}
// Precomputed cell lists and neighbour masks (bits: +x,-x,+y,-y,+z,-z) make the inner loops branch-light.
let gasList=new Int32Array(0), red=new Int32Array(0), black=new Int32Array(0), border=new Int32Array(0), solidList=new Int32Array(0);
const nbMask=new Uint8Array(N), invC=new Float64Array(N), gi=new Uint16Array(N), gj=new Uint16Array(N), gl=new Uint16Array(N);
for(let l=0;l<nz;l++)for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){ const k=id(i,j,l); gi[k]=i; gj[k]=j; gl[k]=l; }
function buildLists(){
  const g=[],r=[],b=[],bd=[],so=[];
  for(let k=0;k<N;k++){
    if(type[k]===GAS){ let m=0,c=0; for(let d=0;d<6;d++) if(type[k+OFF6[d]]===GAS){ m|=1<<d; c++; }
      nbMask[k]=m; invC[k]=c?1/c:0; g.push(k); (((gi[k]+gj[k]+gl[k])&1)?r:b).push(k); }
    else { nbMask[k]=0; so.push(k); let near=false;
      for(let d=0;d<6;d++){ const n=k+OFF6[d]; if(n>=0&&n<N&&type[n]===GAS){ near=true; break; } }
      if(near) bd.push(k); } }
  gasList=Int32Array.from(g); red=Int32Array.from(r); black=Int32Array.from(b); border=Int32Array.from(bd); solidList=Int32Array.from(so);
}
function initFields(){
  const y0=Y0();
  u.fill(0);v.fill(0);w.fill(0);p.fill(0);T.fill(T_AMB);YO.fill(y0);YF.fill(0);YS.fill(0);hrr.fill(0);
  for(const k of fuelList){ const m=MAT[MKEYS[mat[k]]]; mA[k]=m.m0*(1-m.inert); Ts[k]=T_AMB; fst[k]=FL.NONE; prog[k]=0; igT[k]=-1; }
  t=0; firstIgn=-1; igns=[]; extMode=null; events=[];
}
function reset(){ build(); initFields(); warmup(); }

// ---------------- helpers ----------------
function ghost(f,def){ // solid cells that touch gas take the mean of their gas neighbours (zero-gradient walls)
  for(let q=0;q<border.length;q++){ const k=border[q]; let s=0,c=0;
    for(let d=0;d<6;d++){ const n=k+OFF6[d]; if(n>=0&&n<N&&type[n]===GAS){ s+=f[n]; c++; } }
    f[k]= c? s/c : def; }
}
function sample(f,x,y,z){ // x,y,z in cell-index space
  x=x<0?0:x>nx-1.001?nx-1.001:x; y=y<0?0:y>ny-1.001?ny-1.001:y; z=z<0?0:z>nz-1.001?nz-1.001:z;
  const i=x|0,j=y|0,l=z|0, fx=x-i, fy=y-j, fz=z-l, k=i+nx*(j+ny*l);
  const a=f[k]+(f[k+1]-f[k])*fx, b=f[k+SY]+(f[k+SY+1]-f[k+SY])*fx, c=f[k+SZ]+(f[k+SZ+1]-f[k+SZ])*fx, d=f[k+SZ+SY]+(f[k+SZ+SY+1]-f[k+SZ+SY])*fx;
  const e=a+(b-a)*fy, ff=c+(d-c)*fy; return e+(ff-e)*fz;
}
function advect(src,dst,dt){
  const s=dt/h; dst.set(src);
  for(let q=0;q<gasList.length;q++){ const k=gasList[q];
    dst[k]=sample(src, gi[k]-u[k]*s, gj[k]-v[k]*s, gl[k]-w[k]*s); }
}
function diffuse(f,dt,coef,molec){
  tmp.set(f); const c0=dt/(h*h), cap=0.15;
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; let a=(molec+coef*nut[k])*c0; if(a>cap) a=cap;
    const m=nbMask[k], fk=f[k];
    const lap=((m&1)?f[k+1]-fk:0)+((m&2)?f[k-1]-fk:0)+((m&4)?f[k+SY]-fk:0)+((m&8)?f[k-SY]-fk:0)+((m&16)?f[k+SZ]-fk:0)+((m&32)?f[k-SZ]-fk:0);
    tmp[k]=fk+a*lap; }
  f.set(tmp);
}
function velBC(){
  const uin=P.vent?P.U/100:0;
  for(let q=0;q<solidList.length;q++){ const k=solidList[q]; u[k]=0;v[k]=0;w[k]=0; }
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; if(sup[k]){ u[k]=uin; v[k]=0; w[k]=0; } }
}
const sumC=[], cntC=[];
function project(dt){
  const ventOn=P.vent&&P.U>0, ih=1/h, idt=1/dt;
  rhs.fill(0);
  for(let q=0;q<gasList.length;q++){ const k=gasList[q], m=nbMask[k];
    const fe=(m&1)?0.5*(u[k]+u[k+1]):0, fw=(m&2)?0.5*(u[k]+u[k-1]):0;
    const fn=(m&4)?0.5*(v[k]+v[k+SY]):0, fs=(m&8)?0.5*(v[k]+v[k-SY]):0;
    const ft=(m&16)?0.5*(w[k]+w[k+SZ]):0, fb=(m&32)?0.5*(w[k]+w[k-SZ]):0;
    let div=(fe-fw+fn-fs+ft-fb)*ih;
    if(sup[k]&&ventOn) div-=P.U/100*ih;          // inflow through the supply face
    rhs[k]=(div-D[k])*idt; }
  // closed regions (no active outlet): remove the mean so the Neumann problem is solvable
  const nc=comps.length; for(let c=0;c<nc;c++){ sumC[c]=0; cntC[c]=0; }
  for(let q=0;q<gasList.length;q++){ const k=gasList[q], c=comp[k]; sumC[c]+=rhs[k]; cntC[c]++; }
  for(let q=0;q<gasList.length;q++){ const k=gasList[q], c=comp[k]; if(!(comps[c].outlet&&ventOn)) rhs[k]-=sumC[c]/cntC[c]; }
  const h2=h*h, om=1.8;
  for(let it=0;it<cfg.iters;it++){
    for(let pass=0;pass<2;pass++){ const L=pass?black:red;
      for(let q=0;q<L.length;q++){ const k=L[q];
        if(ventOn&&ret[k]){ p[k]=0; continue; }
        const m=nbMask[k]; if(!m) continue;
        const s=((m&1)?p[k+1]:0)+((m&2)?p[k-1]:0)+((m&4)?p[k+SY]:0)+((m&8)?p[k-SY]:0)+((m&16)?p[k+SZ]:0)+((m&32)?p[k-SZ]:0);
        p[k]+=om*((s-h2*rhs[k])*invC[k]-p[k]); } } }
  const f=dt/(2*h);
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; if(sup[k]) continue; const m=nbMask[k], pk=p[k];
    u[k]-=f*(((m&1)?p[k+1]:pk)-((m&2)?p[k-1]:pk));
    v[k]-=f*(((m&4)?p[k+SY]:pk)-((m&8)?p[k-SY]:pk));
    w[k]-=f*(((m&16)?p[k+SZ]:pk)-((m&32)?p[k-SZ]:pk)); }
}
function smagorinsky(dt){
  const cs2=(0.18*h)**2, cap=h*h/(8*dt);
  for(let l=1;l<nz-1;l++)for(let j=1;j<ny-1;j++){ let k=1+nx*(j+ny*l); for(let i=1;i<nx-1;i++,k++){
    if(type[k]!==GAS){ nut[k]=0; continue; }
    const dux=(u[k+1]-u[k-1]), duy=(u[k+SY]-u[k-SY]), duz=(u[k+SZ]-u[k-SZ]);
    const dvx=(v[k+1]-v[k-1]), dvy=(v[k+SY]-v[k-SY]), dvz=(v[k+SZ]-v[k-SZ]);
    const dwx=(w[k+1]-w[k-1]), dwy=(w[k+SY]-w[k-SY]), dwz=(w[k+SZ]-w[k-SZ]);
    const f=1/(2*h);
    const S2=2*((dux*f)**2+(dvy*f)**2+(dwz*f)**2)+((duy+dvx)*f)**2+((duz+dwx)*f)**2+((dvz+dwy)*f)**2;
    nut[k]=Math.min(cap,cs2*Math.sqrt(S2)); } }
}

// ---------------- one time step ----------------
let lastDt=0.1;
function step(dtMax){
  const g=P.g*9.81, y0=Y0(), Pa=pAmb(), ventOn=P.vent&&P.U>0;
  let umax=0.05; for(let q=0;q<gasList.length;q++){ const k=gasList[q]; const a=Math.abs(u[k])+Math.abs(v[k])+Math.abs(w[k]); if(a>umax) umax=a; }
  const dt=Math.max(0.03,Math.min(dtMax, 2.0*h/umax)); lastDt=dt;   // semi-Lagrangian: stable beyond CFL 1
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; const c=comp[k]; rho[k]=(Pa+(comps[c]?comps[c].pbg:0))*M_AIR/(RU*T[k]); }
  // ---- momentum
  smagorinsky(dt);
  advect(u,u2,dt); advect(v,v2,dt); advect(w,w2,dt); u.set(u2); v.set(v2); w.set(w2);
  if(g>0) for(let k=0;k<N;k++) if(type[k]===GAS) v[k]+=dt*g*(T[k]/T_AMB-1);
  diffuse(u,dt,1,1.6e-5); diffuse(v,dt,1,1.6e-5); diffuse(w,dt,1,1.6e-5);
  for(let k=0;k<N;k++){ const s=Math.abs(u[k])+Math.abs(v[k])+Math.abs(w[k]); if(s>U_CAP){ const f=U_CAP/s; u[k]*=f; v[k]*=f; w[k]*=f; } }
  velBC(); project(dt); velBC();
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; if(T[k]<360){ ucx[k]=u[k]; ucy[k]=v[k]; ucz[k]=w[k]; } }
  // ---- scalars
  ghost(T,T_AMB); ghost(YO,y0); ghost(YF,0); ghost(YS,0);
  advect(T,tmp,dt); T.set(tmp); advect(YO,tmp,dt); YO.set(tmp); advect(YF,tmp,dt); YF.set(tmp); advect(YS,tmp,dt); YS.set(tmp);
  diffuse(T,dt,2,2.2e-5); diffuse(YO,dt,2,2.0e-5); diffuse(YF,dt,2,2.0e-5); diffuse(YS,dt,2,1e-5);
  if(ventOn) for(let k=0;k<N;k++) if(sup[k]){ T[k]=T_AMB; YO[k]=y0; YF[k]=0; YS[k]=0; }
  // ---- solids: surface heating, flame existence, burning, spread
  solids(dt,g);
  // ---- gas combustion, radiation and wall losses → temperature and expansion source
  D.fill(0); hrr.fill(0);
  const qComp=new Float64Array(comps.length);
  for(let l=1;l<nz-1;l++)for(let j=1;j<ny-1;j++){ let k=1+nx*(j+ny*l); for(let i=1;i<nx-1;i++,k++){
    if(type[k]!==GAS) continue;
    const r=rho[k]; let q=0;
    const yf=YF[k], yo=YO[k];
    if(yf>1e-7 && yo>1e-5){
      // FDS-style extinction: a stoichiometric mixture of the local gas must be able to reach the critical flame temperature.
      // Surface-anchored (subgrid) flames are already screened by the flame-temperature model of the solid.
      const Tpot=T[k]+yo*DH_O2/CP_MIX;
      if(flameAdj[k] || (T[k]>T_AIT && Tpot>=T_CFT)){
        const sp=Math.hypot(u[k],v[k],w[k]);
        const tau= flameAdj[k]? 0.05 : Math.min(2,Math.max(0.1,h/(sp+Math.sqrt(Math.max(g,0.05)*h))));
        const dd=Math.min(yf,yo)*(1-Math.exp(-dt/tau));
        YF[k]-=dd; YO[k]-=dd; YS[k]+=Y_SOOT_RXN*dd;
        q=r*dd*DH_O2/dt;   // W/m³
      }
    }
    const kap=0.1+Math.min(5,SOOT_EXT*r*YS[k]*0.15);
    const Tk=T[k]; let qrad=4*kap*SIGMA*(Tk**4-T_AMB**4);
    let nw=0; for(let d=0;d<6;d++) if(type[k+OFF6[d]]!==GAS) nw++;
    const qwall=nw*H_CONV*A*(Tk-T_AMB)/V;
    const qnet=(1-CHI_R)*q - qrad - qwall;
    T[k]=Math.max(T_AMB-5,Math.min(T_CELL_MAX,Tk+qnet*dt/(r*CP)));
    D[k]=qnet/(r*CP*T[k]);
    hrr[k]=q*V;
    qComp[comp[k]]+=qnet*V;
    if(YO[k]<0) YO[k]=0; if(YF[k]<0) YF[k]=0;
  } }
  for(let c=0;c<comps.length;c++){ const C=comps[c]; if(C.outlet&&ventOn) C.pbg=0; else C.pbg+= (GAMMA-1)*qComp[c]/C.vol*dt; }
  t+=dt;
  return dt;
}

function solids(dt,g){
  flameAdj.fill(0); inc.fill(0);
  // vertical run length of flaming surface below each fuel cell (flame length for buoyant acceleration)
  for(const k of fuelList){ const b=k-SY; Lup[k]= (fst[b]===FL.FLAME && type[b]===FUEL)? Math.min(1, (Lup[b]||0)+h) : 0; }
  for(const k of fuelList){
    const m=MAT[MKEYS[mat[k]]]; const st=fst[k];
    if(st===FL.NONE && prog[k]===0){ // cheap skip for cold, unexposed fuel
      let hot=false; for(let d=0;d<6;d++) if((faces[k]>>d)&1 && T[k+OFF6[d]]>T_AMB+15){ hot=true; break; }
      if(!hot && !nearFlame(k)) continue; }
    if(st===FL.BURNT) continue;
    // local gas state over exposed faces
    let Tg=0,yo=0,uu=0,vv=0,ww=0,c=0,ksoot=0, nrm=[0,0,0];
    for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; Tg+=T[n]; yo=Math.max(yo,YO[n]); uu+=ucx[n]; vv+=ucy[n]; ww+=ucz[n]; c++; ksoot=Math.max(ksoot,SOOT_EXT*(rho[n]||1)*YS[n]); nrm[0]+=NB6[d][0]; nrm[1]+=NB6[d][1]; nrm[2]+=NB6[d][2]; }
    if(!c) continue;
    Tg/=c; uu/=c; vv/=c; ww/=c;
    const X=Xvol(yo), Pk=P.Pk, isItem=faces[k]===63||c>2;
    // remove the flow component normal to a single exposed face (flow along the surface)
    if(!isItem){ const nn=Math.hypot(...nrm)||1, nx_=nrm[0]/nn, ny_=nrm[1]/nn, nz_=nrm[2]/nn, dot=uu*nx_+vv*ny_+ww*nz_; uu-=dot*nx_; vv-=dot*ny_; ww-=dot*nz_; }
    const Ures=100*Math.hypot(uu,vv,ww);
    const gEff= (!isItem && nrm[1]!==0)? 0 : P.g;      // buoyant flow is along a wall, not along a ceiling
    const fs=flameState(m,X,Ures,Pk,Tg,gEff*9.81,Lup[k]);
    const total=mA[k]+m.m0*m.inert;
    if(st===FL.FLAME){
      if(!fs.exists && !(igT[k]>=0 && t-igT[k]<4 && igns.includes(k))){ fst[k]=FL.OUT; extMode= X<P.X-3? 'oxygen' : fs.mode==='quench'?'quenching':'blowoff'; continue; }
      // burning: mass loss from flame heat flux + external flux
      const qf=m.qfl*Math.max(0.2,(fs.Tf-m.Tv)/(TF_REF-m.Tv));
      // extra heat from a smoky hot layer only (the cell's own flame is already in qf)
      const Tl=Math.min(Tg,1100), qext=Math.max(0,epsLayer(ksoot)*SIGMA*(Tl**4-m.Tv**4));
      // subgrid surface spread to neighbouring fuel (same room only: rooms connect through the gas)
      const vo=Vopp(m,fs,Tg,m.m0), vc=Vcon(m,fs);
      const W=[uu*100,(vv*100+fs.UbL*(gEff>0?1:0)),ww*100], Wn=Math.hypot(W[0],W[1],W[2])||1;
      let tLeft=0;   // time the slowest active front still needs to leave this cell
      for(let q=0;q<26;q++){ const nb=NB26[q], n=k+nb[3]; if(type[n]!==FUEL||fst[n]===FL.FLAME||fst[n]===FL.BURNT) continue;
        if(room[n]!==room[k]) continue;
        const len=nb[4], cos=(nb[0]*W[0]+nb[1]*W[1]+nb[2]*W[2])/(len*Wn);
        const mn=MAT[MKEYS[mat[n]]]; const scale=Math.min(4,(m.m0*m.cs)/(mn.m0*mn.cs));   // thermal-mass ratio for mixed materials
        const vel=(cos>=0? vo+(vc-vo)*cos*cos*cos*cos : vo)*scale;
        if(vel<=0.02) continue; const di=dt*vel/(1000*h*len); if(di>inc[n]) inc[n]=di;
        const tl=(1-prog[n])*1000*h*len/vel; if(tl>tLeft) tLeft=tl; }
      // a 1-cell surface burns as a strip behind the front: it lasts t_b + (time for its slowest front to leave)
      const m0c=m.m0*(1-m.inert), qtot=qf+qext, tb=m0c*m.Lg/qtot;
      const mdot=Math.min(qtot/m.Lg, mA[k]/(Math.min(tb,mA[k]*m.Lg/qtot)+Math.min(tLeft,900)));  // kg/m²/s
      const dm=Math.min(mA[k],mdot*dt); mA[k]-=dm;
      for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; const r=rho[n]||1;
        YF[n]+=dm*A*m.s/(r*V); YS[n]+=dm*A*m.ys/(r*V); flameAdj[n]=1; }
      Ts[k]=m.Tv;
      if(mA[k]<=1e-3*m.m0){ fst[k]=FL.BURNT; continue; }
    } else {
      // surface energy balance (thermally thin): convection + gas radiation + radiation from neighbouring flames − re-radiation
      let qn=0; for(const [,,,off] of NB26){ const n=k+off; if(n>=0&&n<N&&type[n]===FUEL&&fst[n]===FL.FLAME) qn+=1500; }
      // hot-layer emissivity from soot over a 0.5 m path (absorption ≈ 0.1 × extinction for soot-laden smoke)
      const epsg=epsLayer(ksoot);
      const qin=H_CONV*(Tg-Ts[k])+ epsg*SIGMA*(Tg**4-Ts[k]**4) + qn - 0.9*SIGMA*(Ts[k]**4-T_AMB**4);
      Ts[k]+=qin*dt/(total*m.cs);
      if(Ts[k]>=m.Tv){
        // pyrolysis without a pilot releases unburnt fuel vapour
        const mdot=Math.max(0,qin)/m.Lg, dm=Math.min(mA[k],mdot*dt); mA[k]-=dm; Ts[k]=m.Tv;
        for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; YF[n]+=dm*A*m.s/((rho[n]||1)*V); }
        if(fs.exists && (Tg>T_AIT-150 || prog[k]>0.3)){ fst[k]=FL.FLAME; igT[k]=t; noteIgn(k,'hot gas'); }
        if(mA[k]<=1e-4*m.m0) fst[k]=FL.BURNT;
      } else if(st===FL.NONE && Ts[k]>T_AMB+30) fst[k]=FL.HEAT;
    }
  }
  for(const k of fuelList){ if(inc[k]<=0||fst[k]===FL.FLAME||fst[k]===FL.BURNT) continue;
    prog[k]+=inc[k]; if(fst[k]===FL.NONE) fst[k]=FL.HEAT;
    if(prog[k]>=1){ const m=MAT[MKEYS[mat[k]]];
      let Tg=0,yo=0,c=0; for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; Tg+=T[n]; yo=Math.max(yo,YO[n]); c++; } Tg/=c||1;
      const fs=flameState(m,Xvol(yo),0,P.Pk,Tg,P.g*9.81,0);
      if(fs.Tf>=m.Tc){ fst[k]=FL.FLAME; igT[k]=t; Ts[k]=m.Tv; noteIgn(k,'spread'); } else prog[k]=0.95; } }
}
function nearFlame(k){ for(let q=0;q<26;q++){ const n=k+NB26[q][3]; if(fst[n]===FL.FLAME&&type[n]===FUEL) return true; } return false; }
function epsLayer(K){ return Math.min(0.95,0.05+1-Math.exp(-0.1*K*0.5)); }
function noteIgn(k,how){ if(firstIgn<0) firstIgn=k; }

function warmup(){ const ig=igns; igns=[]; for(let i=0;i<60;i++) step(0.25); t=0; igns=ig; }

// ---------------- API ----------------
function ignite(k){ if(type[k]!==FUEL||fst[k]===FL.FLAME||fst[k]===FL.BURNT) return false;
  fst[k]=FL.FLAME; igT[k]=t; Ts[k]=MAT[MKEYS[mat[k]]].Tv; igns.push(k); if(firstIgn<0) firstIgn=k; return true; }
function toggleOpening(oi){ const o=OPEN[oi]; o.open=!o.open; for(const k of o.cells){ type[k]=o.open?GAS:WALL; if(!o.open){u[k]=v[k]=w[k]=0;} else { T[k]=T_AMB; YO[k]=Y0(); YF[k]=0; YS[k]=0; } } buildComps(); return o.open; }
function setParams(q){ const relining= q.lining && q.lining!==P.lining; Object.assign(P,q); if(relining){ reset(); } }
function stats(){
  const r=ROOMS.map(()=>({flame:0,burnt:0,heat:0,Tmax:T_AMB,Xmin:100,soot:0,sootN:0,hrr:0,pbg:0,vis:99}));
  for(let k=0;k<N;k++){ const ri=room[k]; if(ri<0) continue; const R_=r[ri];
    if(type[k]===GAS){ if(T[k]>R_.Tmax)R_.Tmax=T[k]; const x=Xvol(YO[k]); if(x<R_.Xmin)R_.Xmin=x; R_.hrr+=hrr[k];
      const c=comp[k]; if(comps[c]) R_.pbg=Math.max(R_.pbg,comps[c].pbg);
      // detector band: top 25 cm of the room
      const j=Math.floor(k/nx)%ny; if(cy(j)>=ROOMS[ri].y1-0.25){ R_.soot+=SOOT_EXT*rho[k]*YS[k]; R_.sootN++; } }
    else if(type[k]===FUEL){ const s=fst[k]; if(s===FL.FLAME) R_.flame++; else if(s===FL.BURNT||s===FL.OUT) R_.burnt++; else if(s===FL.HEAT) R_.heat++; } }
  for(const R_ of r){ const K=R_.sootN? R_.soot/R_.sootN : 0; R_.ext=K; R_.vis= K>1e-4? Math.min(99,3/K) : 99; R_.Xmin=Math.min(R_.Xmin,P.X); }
  return r;
}
reset();
return {
  info:{nx,ny,nz,N,h,NXi,NYi,NZi,LX,LY,LZ,SY,SZ}, MAT, MKEYS, ROOMS, OPEN, ITEMS, P, FL,
  type, room, openId, sup, ret, mat, faces, fst, prog, igT, Ts, mA, T, YO, YF, YS, u, v, w, hrr,
  get t(){return t;}, get lastDt(){return lastDt;}, get fuelList(){return fuelList;}, get firstIgn(){return firstIgn;}, get extMode(){return extMode;}, get igns(){return igns;},
  step, reset, ignite, toggleOpening, setParams, stats, id, Xvol,
  model:{flameState, Vopp, Vcon, Tflame, Ubo, Ubuoy, KAPPA, T_AMB, TF_REF, LB}, curves, loiVsG, validate, limitX,
};
}
if(typeof module!=='undefined') module.exports={createSolver};
