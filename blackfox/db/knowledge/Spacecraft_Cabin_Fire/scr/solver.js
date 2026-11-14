// Spacecraft cabin fire solver (v4 physics) — 3D variable-density LES-style fire model of a crewed spacecraft:
// US-Lab-style module with rack ring and central aisle, a node with crew quarters and galley, and an airlock.
// cfg.dim = 2 solves a vertical (x–y) section one cell deep with zero-flux front/back faces; cfg.dim = 3 is the full 3D model.
// Quantities per cell are for a slab of depth h; heat release is reported per metre of depth by the page.
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
  // Spacecraft materials below are set from typical 1 g limiting oxygen indices (ASTM D2863 handbook values, not in the
  // knowledge base); the 0 g best-case limit is taken 1.5–3 points lower, following ntrs-20080034883.
  pe:{name:'Polyethylene wire insulation', id:'pe', m0:0.30, inert:0, cs:2300, Tv:650, s:3.3, Lg:2.2e6, qfl:20e3, ys:0.06,
    Rset:0.45, xmin:16.0, boOpp:[30,17.6], boCon:[70,17.4], loi:17.4,
    src:{quench:'ASSUMED from handbook LOI 17.4%', boOpp:'1 g LOI', boCon:'assumed'}},
  ptfe:{name:'PTFE (Teflon) wire insulation', id:'ptfe', m0:0.60, inert:0, cs:1000, Tv:800, s:0.38, Lg:1.8e6, qfl:10e3, ys:0.002,
    Rset:0.45, xmin:92, boOpp:[30,95], boCon:[70,95], loi:95,
    src:{quench:'handbook LOI ~95%: does not burn in any cabin atmosphere', boOpp:'1 g LOI', boCon:'assumed'}},
  kapton:{name:'Kapton (polyimide) film / wire wrap', id:'kapton', m0:0.07, inert:0.5, cs:1100, Tv:850, s:1.9, Lg:2.5e6, qfl:15e3, ys:0.01,
    Rset:0.45, xmin:34, boOpp:[30,37], boCon:[70,37], loi:37,
    src:{quench:'ASSUMED from handbook LOI ~37%', boOpp:'1 g LOI', boCon:'assumed'}},
  silicone:{name:'Silicone rubber (seals, cable jacket)', id:'silicone', m0:1.4, inert:0.6, cs:1300, Tv:700, s:1.15, Lg:2.5e6, qfl:15e3, ys:0.03,
    Rset:0.45, xmin:26.5, boOpp:[30,29], boCon:[70,29], loi:29,
    src:{quench:'ASSUMED from handbook LOI 26–30%', boOpp:'1 g LOI', boCon:'assumed'}},
  pc:{name:'Polycarbonate panel, 3 mm', id:'pc', m0:3.6, inert:0.2, cs:1300, Tv:700, s:2.35, Lg:2.1e6, qfl:18e3, ys:0.10,
    Rset:0.40, xmin:24.0, boOpp:[30,26.5], boCon:[70,26.5], loi:26.5,
    src:{quench:'ASSUMED from handbook LOI 25–28%', boOpp:'1 g LOI', boCon:'assumed'}},
  pu:{name:'Pyrell polyurethane foam (packing)', id:'pyrell', m0:0.30, inert:0.05, cs:1400, Tv:560, s:2.0, Lg:1.4e6, qfl:20e3, ys:0.10,
    Rset:0.50, xmin:20.0, boOpp:[30,22.5], boCon:[70,22], loi:22,
    src:{quench:'ASSUMED: flame-retarded PU, LOI ~22%', boOpp:'1 g LOI', boCon:'assumed'}},
  nylon:{name:'Nylon Velcro / webbing', id:'nylon', m0:0.30, inert:0, cs:1700, Tv:700, s:2.3, Lg:2.4e6, qfl:18e3, ys:0.03,
    Rset:0.45, xmin:22.0, boOpp:[30,24.5], boCon:[70,24], loi:24,
    src:{quench:'ASSUMED from handbook LOI 24%; nylon Velcro burned at 30% O₂, 70 kPa in drop tests (ntrs-19870010085)', boOpp:'1 g LOI', boCon:'assumed'}},
  cotton:{name:'Cotton clothing / towels', id:'cotton', m0:0.15, inert:0.03, cs:1300, Tv:600, s:1.23, Lg:2.0e6, qfl:15e3, ys:0.012,
    Rset:0.50, xmin:16.5, boOpp:[30,18.5], boCon:[70,18.5], loi:18.5,
    src:{quench:'ASSUMED from handbook LOI ~18.5%', boOpp:'1 g LOI', boCon:'assumed'}},
};
MAT.sibal.loi=19; MAT.pmma.loi=17.3; MAT.paper.loi=18.5; MAT.nomex.loi=28.5;
const REFS={sibal:['ntrs-20150008962','ntrs-20170008805'], pmma:['pmc-5760683','ntrs-20210017838'], paper:['ntrs-19930040901'], nomex:['ntrs-20240002981','ntrs-20080034883'],
  pe:['epmc-ppr-ppr477634','ntrs-20140000850'], ptfe:['epmc-med-27501881','ntrs-20140006585'], kapton:['ntrs-20140006585','ntrs-20040053602'], silicone:['ntrs-20140006585','ntrs-20040053602'],
  pc:['ntrs-20205004657'], pu:['ntrs-20140006585','ntrs-20040084186'], nylon:['ntrs-19870010085','ntrs-20230004106'], cotton:['ntrs-20140006585','ntrs-20260001992']};
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

// ---------------- grid: spacecraft (Lab module – Node with crew quarters – Airlock) ----------------
// x runs aft→forward along the vehicle axis, y is "overhead" (up when there is gravity), z runs port→starboard.
const DIM=3; const h=cfg.h||0.15, LX=11.5, LY=4.2, LZ=4.2;
const NXi=Math.round(LX/h), NYi=Math.round(LY/h), NZi=Math.round(LZ/h);
const nx=NXi+2, ny=NYi+2, nz=NZi+2, N=nx*ny*nz, SY=nx, SZ=nx*ny, V=h*h*h, A=h*h;
const id=(i,j,l)=>i+nx*(j+ny*l);
const ci=x=>Math.min(NXi,Math.max(1,Math.floor(x/h+1e-9)+1));
const cj=y=>Math.min(NYi,Math.max(1,Math.floor(y/h+1e-9)+1));
const ck=z=>Math.min(NZi,Math.max(1,Math.floor(z/h+1e-9)+1));
const cx=i=>(i-0.5)*h, cy=j=>(j-0.5)*h, cz=l=>(l-0.5)*h;
const GAS=0, WALL=1, FUEL=2;
const type=new Uint8Array(N), room=new Int8Array(N), openId=new Int8Array(N), sup=new Uint8Array(N), ret=new Uint8Array(N);
const supDx=new Int8Array(N), supDy=new Int8Array(N), supDz=new Int8Array(N), supSp=new Float64Array(N), itemOf=new Int16Array(N), sclass=new Uint8Array(N);
const AXY=2.1, AXZ=2.1, r2=(y,z)=>(y-AXY)**2+(z-AXZ)**2;
const inBox=(x,y,z,b)=> x>=b.x[0]&&x<b.x[1]&&y>=b.y[0]&&y<b.y[1]&&z>=b.z[0]&&z<b.z[1];
const ROOMS=[
  {id:'lab',  name:'Lab module (aisle)',       short:'Lab',      x0:0.3, x1:6.5,  test:(x,y,z)=>x>=0.3&&x<6.5&&Math.abs(y-AXY)<1.05&&Math.abs(z-AXZ)<1.05},
  {id:'rack', name:'Avionics rack bay',         short:'Rack bay', x0:1.2, x1:2.1,  test:(x,y,z)=>x>=1.2&&x<2.1&&y>=1.35&&y<2.85&&z>=3.35&&z<3.9},
  {id:'node', name:'Node and galley',           short:'Node',     x0:6.65,x1:9.5,  test:(x,y,z)=>x>=6.65&&x<9.5&&r2(y,z)<4.0},
  {id:'cqp',  name:'Crew quarters, port',       short:'CQ port',  x0:7.0, x1:8.2,  test:(x,y,z)=>x>=7.0&&x<8.2&&y>=1.0&&y<3.1&&z>=0.6&&z<1.05},
  {id:'cqs',  name:'Crew quarters, starboard',  short:'CQ stbd',  x0:7.0, x1:8.2,  test:(x,y,z)=>x>=7.0&&x<8.2&&y>=1.0&&y<3.1&&z>=3.15&&z<3.6},
  {id:'air',  name:'Airlock',                   short:'Airlock',  x0:9.65,x1:11.4, test:(x,y,z)=>x>=9.65&&x<11.4&&r2(y,z)<1.3225},
];
const SHELLS=[
  {name:'Port crew-quarters enclosure',      cls:3, test:(x,y,z)=>x>=6.85&&x<8.35&&y>=0.85&&y<3.25&&z>=0.45&&z<1.2},
  {name:'Starboard crew-quarters enclosure', cls:3, test:(x,y,z)=>x>=6.85&&x<8.35&&y>=0.85&&y<3.25&&z>=3.0&&z<3.75},
  {name:'Galley table',                      cls:3, test:(x,y,z)=>x>=8.4&&x<9.2&&y>=1.0&&y<1.15&&z>=1.6&&z<2.6},
];
const OPEN=[
  {id:'H1', name:'Lab–Node hatch',               test:(x,y,z)=>x>=6.5&&x<6.65&&Math.abs(y-AXY)<0.6&&Math.abs(z-AXZ)<0.6, open:true},
  {id:'H2', name:'Node–Airlock hatch',           test:(x,y,z)=>x>=9.5&&x<9.65&&Math.abs(y-AXY)<0.5&&Math.abs(z-AXZ)<0.5, open:true},
  {id:'C1', name:'Port crew-quarters door',      test:(x,y,z)=>x>=7.3&&x<7.9&&y>=1.5&&y<2.7&&z>=1.05&&z<1.2, open:true},
  {id:'C2', name:'Starboard crew-quarters door', test:(x,y,z)=>x>=7.3&&x<7.9&&y>=1.5&&y<2.7&&z>=3.0&&z<3.15, open:true},
  {id:'G1', name:'Avionics rack grilles',        test:(x,y,z)=>x>=1.35&&x<1.95&&z>=3.15&&z<3.35&&((y>=1.35&&y<1.65)||(y>=2.55&&y<2.85)), open:true},
];
const VENTS=[
  {kind:'sup', name:'Lab overhead diffusers', dir:[0,-1,0], sp:1,   room:'lab',  test:(x,y,z,k)=>((x>=1.0&&x<1.6)||(x>=3.0&&x<3.6)||(x>=5.0&&x<5.6))&&Math.abs(z-AXZ)<0.45&&type[k+SY]!==GAS},
  {kind:'sup', name:'Node overhead diffuser', dir:[0,-1,0], sp:1,   room:'node', test:(x,y,z,k)=>x>=7.0&&x<8.6&&Math.abs(z-AXZ)<0.4&&type[k+SY]!==GAS&&y>3},
  {kind:'sup', name:'Rack cooling fan',       dir:[0,1,0],  sp:0.3, room:'rack', test:(x,y,z,k)=>x>=1.5&&x<1.8&&z>=3.5&&z<3.8&&type[k-SY]!==GAS},
  {kind:'sup', name:'Port CQ fan',            dir:[0,-1,0], sp:0.4, room:'cqp',  test:(x,y,z,k)=>x>=7.3&&x<7.9&&z<0.9&&type[k+SY]!==GAS},
  {kind:'sup', name:'Starboard CQ fan',       dir:[0,-1,0], sp:0.4, room:'cqs',  test:(x,y,z,k)=>x>=7.3&&x<7.9&&z>=3.3&&type[k+SY]!==GAS},
  {kind:'ret', name:'Lab return grille',      room:'lab',  test:(x,y,z,k)=>x>=0.45&&x<0.9&&Math.abs(z-AXZ)<0.4&&type[k-SY]!==GAS},
  {kind:'ret', name:'Node return grille',     room:'node', test:(x,y,z,k)=>x>=8.9&&x<9.35&&Math.abs(z-AXZ)<0.4&&type[k-SY]!==GAS&&y<1.0},
];
// Possible fire origins: each is a real kind of spacecraft item with the materials it is commonly made of.
const ITEMS=[
  {id:'L1', name:'Avionics rack wire harness', where:'Lab · inside the starboard avionics rack', room:'rack', m:'pe', opts:['pe','ptfe','kapton','silicone'],
    x:[1.5,1.8], y:[1.5,2.7], z:[3.5,3.65], af:0.2, note:'Overheated wiring is the most likely spacecraft fire source. Real bundle ≈5 cm across, so 20% of the cell surface burns.'},
  {id:'L2', name:'Experiment rack front panel', where:'Lab · port rack face', room:'lab', m:'pc', opts:['pc','pmma','nomex'], onWall:true,
    x:[3.0,4.0], y:[1.3,2.9], z:[0.9,1.05]},
  {id:'L3', name:'Overhead stowage bags (CTBs)', where:'Lab · overhead rack face', room:'lab', m:'nomex', opts:['nomex','sibal','cotton'], onWall:true,
    x:[4.5,6.2], y:[3.15,3.3], z:[1.3,2.9]},
  {id:'L4', name:'Laptop foam packing', where:'Lab · deck, in the aisle', room:'lab', m:'pu', opts:['pu','nomex','cotton'],
    x:[2.2,2.7], y:[1.05,1.4], z:[1.3,1.8]},
  {id:'L5', name:'Wipes and checklists on worktable', where:'Lab · deck, starboard side of the aisle', room:'lab', m:'paper', opts:['paper','cotton'],
    x:[4.2,4.8], y:[1.05,1.2], z:[2.4,2.95]},
  {id:'L6', name:'Glovebox window', where:'Lab · starboard rack face', room:'lab', m:'pmma', opts:['pmma','pc'], onWall:true,
    x:[3.2,4.0], y:[1.6,2.4], z:[3.15,3.3]},
  {id:'L7', name:'Overhead cable tray', where:'Lab · overhead, starboard', room:'lab', m:'ptfe', opts:['ptfe','pe','kapton'], onWall:true,
    x:[1.8,4.2], y:[3.15,3.3], z:[2.85,3.15], af:0.3},
  {id:'N1', name:'Sleeping bag', where:'Node · port crew quarters', room:'cqp', m:'nomex', opts:['nomex','cotton','sibal'],
    x:[7.15,8.05], y:[1.3,2.9], z:[0.6,0.75]},
  {id:'N2', name:'Crew clothing', where:'Node · starboard crew quarters', room:'cqs', m:'cotton', opts:['cotton','nomex'],
    x:[7.2,7.9], y:[1.3,2.2], z:[3.45,3.6]},
  {id:'N3', name:'Velcro strips', where:'Node · forward bulkhead', room:'node', m:'nylon', opts:['nylon','nomex'], onWall:true,
    x:[9.5,9.65], y:[2.7,3.1], z:[1.2,3.0], af:0.3},
  {id:'N4', name:'Galley food packaging', where:'Node · on the galley table', room:'node', m:'paper', opts:['paper','pe'],
    x:[8.5,9.0], y:[1.15,1.4], z:[1.8,2.4]},
  {id:'N5', name:'Closeout curtain', where:'Node · port wall, aft of the hatch', room:'node', m:'sibal', opts:['sibal','nomex','cotton'],
    x:[8.4,9.3], y:[2.2,3.3], z:[0.85,1.0]},
  {id:'A1', name:'EVA suit outer layer', where:'Airlock', room:'air', m:'nomex', opts:['nomex','sibal','cotton'],
    x:[10.3,10.8], y:[1.4,2.8], z:[1.8,2.4]},
  {id:'A2', name:'Hatch seal', where:'Airlock · around the hatch', room:'air', m:'silicone', opts:['silicone','nylon'], onWall:true,
    test:(x,y,z)=>x>=9.5&&x<9.65&&Math.max(Math.abs(y-AXY),Math.abs(z-AXZ))>=0.5&&Math.max(Math.abs(y-AXY),Math.abs(z-AXZ))<0.65, af:0.25},
];

// ---------------- state ----------------
const P={g:cfg.g??0, X:cfg.X??21, Pk:cfg.Pk??101.3, U:cfg.U??40, vent:cfg.vent??true, lining:cfg.lining||'sibal'};
const qx=new Float64Array(N);   // imposed heat flux on a surface (electrical overheat), W/m²
const u=new Float64Array(N), v=new Float64Array(N), w=new Float64Array(N);
const u2=new Float64Array(N), v2=new Float64Array(N), w2=new Float64Array(N);
// last velocity seen while a cell was cold: the ambient/ventilation flow a surface flame sees (its own induced flow is subgrid, via U_b)
const ucx=new Float64Array(N), ucy=new Float64Array(N), ucz=new Float64Array(N);
// ventilation-only flow (no fire): the external flow a surface flame sees; its own entrainment is subgrid (U_b)
const uvx=new Float64Array(N), uvy=new Float64Array(N), uvz=new Float64Array(N);
const T=new Float64Array(N), YO=new Float64Array(N), YF=new Float64Array(N), YS=new Float64Array(N);
const tmp=new Float64Array(N), p=new Float64Array(N), rhs=new Float64Array(N), D=new Float64Array(N), nut=new Float64Array(N), rho=new Float64Array(N), hrr=new Float64Array(N);
const comp=new Int32Array(N); let comps=[];
// fuel
// wf: fraction of the module depth a fuel surface spans (2D depth-averaged section; 1 in 3D and for wall linings)
const wf=new Float64Array(N).fill(1);
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

function build(){
  type.fill(WALL); room.fill(-1); openId.fill(-1); sup.fill(0); ret.fill(0); supSp.fill(0); supDx.fill(0); supDy.fill(0); supDz.fill(0);
  mat.fill(-1); faces.fill(0); wf.fill(1); qx.fill(0); itemOf.fill(-1); sclass.fill(1);
  const C=fn=>{ for(let l=1;l<=NZi;l++)for(let j=1;j<=NYi;j++)for(let i=1;i<=NXi;i++) fn(id(i,j,l),cx(i),cy(j),cz(l)); };
  C((k,x,y,z)=>{ if((x>=6.5&&x<6.65)||(x>=9.5&&x<9.65)) sclass[k]=2; });
  C((k,x,y,z)=>{ ROOMS.forEach((r,ri)=>{ if(r.id!=='cqp'&&r.id!=='cqs'&&r.test(x,y,z)){ type[k]=GAS; room[k]=ri; } }); });
  C((k,x,y,z)=>{ for(const sh of SHELLS) if(sh.test(x,y,z)){ type[k]=WALL; room[k]=-1; sclass[k]=sh.cls; } });
  C((k,x,y,z)=>{ ROOMS.forEach((r,ri)=>{ if((r.id==='cqp'||r.id==='cqs')&&r.test(x,y,z)){ type[k]=GAS; room[k]=ri; } }); });
  OPEN.forEach((o,oi)=>{ o.cells=[]; C((k,x,y,z)=>{ if(type[k]===WALL&&o.test(x,y,z)){ o.cells.push(k); openId[k]=oi; } }); for(const k of o.cells) type[k]= o.open? GAS : WALL; });
  for(const vt of VENTS){ const ri=ROOMS.findIndex(r=>r.id===vt.room);
    C((k,x,y,z)=>{ if(type[k]!==GAS||room[k]!==ri||!vt.test(x,y,z,k)) return;
      if(vt.kind==='sup'){ sup[k]=1; supDx[k]=vt.dir[0]; supDy[k]=vt.dir[1]; supDz[k]=vt.dir[2]; supSp[k]=vt.sp; } else ret[k]=1; }); }
  ITEMS.forEach((it,ii)=>{ const mi=MKEYS.indexOf(it.m), ri=ROOMS.findIndex(r=>r.id===it.room); it.cells=[];
    C((k,x,y,z)=>{ if(!(it.test? it.test(x,y,z) : inBox(x,y,z,it))) return; if(openId[k]>=0||sup[k]||ret[k]) return;
      if(it.onWall? type[k]!==WALL : type[k]!==GAS) return;
      type[k]=FUEL; mat[k]=mi; faces[k]=63; itemOf[k]=ii; room[k]=ri; wf[k]=it.af||1; it.cells.push(k); }); });   // wf: real fuel area / cell face area
  fuelList=[]; for(let k=0;k<N;k++) if(type[k]===FUEL){
    let f=0; for(let d=0;d<6;d++) if((faces[k]>>d)&1 && type[k+OFF6[d]]===GAS) f|=1<<d; faces[k]=f;
    if(f) fuelList.push(k); else { type[k]=WALL; mat[k]=-1; itemOf[k]=-1; } }
  for(const it of ITEMS) it.cells=it.cells.filter(k=>type[k]===FUEL);
  ROOMS.forEach((r,ri)=>{ let top=0,sx=0,sy=0,sz=0,n=0; C((k,x,y,z)=>{ if(type[k]===GAS&&room[k]===ri){ if(y>top) top=y; sx+=x; sy+=y; sz+=z; n++; } }); r.ytop=top; r.y1=top+h/2; r.c=n?[sx/n,sy/n,sz/n]:[0,0,0]; });
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
function reset(){ build(); initFields(); ventFlow(); warmup(); }
function ventFlow(){
  const su=u.slice(), sv=v.slice(), sw=w.slice(), sp=p.slice(), sd=D.slice();
  u.fill(0); v.fill(0); w.fill(0); p.fill(0); D.fill(0); const it=cfg.iters; cfg.iters=400; velBC(); project(1.0); velBC(); cfg.iters=it;
  uvx.set(u); uvy.set(v); uvz.set(w); u.set(su); v.set(sv); w.set(sw); p.set(sp); D.set(sd);
}

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
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; if(sup[k]){ const s=uin*supSp[k]; u[k]=s*supDx[k]; v[k]=s*supDy[k]; w[k]=s*supDz[k]; } }
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
    if(sup[k]&&ventOn) div-=P.U/100*supSp[k]*ih;  // inflow through the diffuser face
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
    const zf=DIM===3?1:0;
    const S2=2*((dux*f)**2+(dvy*f)**2+zf*(dwz*f)**2)+((duy+dvx)*f)**2+zf*((duz+dwx)*f)**2+zf*((dvz+dwy)*f)**2;
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
  velBC(); project(dt); velBC(); if(DIM===2) w.fill(0);
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
    if(st===FL.NONE && prog[k]===0 && qx[k]===0){ // cheap skip for cold, unexposed fuel (never skip an overheated surface)
      let hot=false; for(let d=0;d<6;d++) if((faces[k]>>d)&1 && T[k+OFF6[d]]>T_AMB+15){ hot=true; break; }
      if(!hot && !nearFlame(k)) continue; }
    if(st===FL.BURNT) continue;
    // local gas state over exposed faces
    let Tg=0,yo=0,uu=0,vv=0,ww=0,c=0,ksoot=0, nrm=[0,0,0], ru=0,rv=0,rw=0, sm=0;
    for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d], nf=farGas(n,d); Tg+=T[nf]; yo=Math.max(yo,YO[nf]); uu+=uvx[n]; vv+=uvy[n]; ww+=uvz[n]; sm+=Math.hypot(uvx[n],uvy[n],uvz[n]); ru+=u[n]; rv+=v[n]; rw+=w[n]; c++; ksoot=Math.max(ksoot,SOOT_EXT*(rho[n]||1)*YS[n]); nrm[0]+=NB6[d][0]; nrm[1]+=NB6[d][1]; nrm[2]+=NB6[d][2]; }
    if(!c) continue;
    Tg/=c; uu/=c; vv/=c; ww/=c;
    const X=Xvol(yo), Pk=P.Pk, isItem=faces[k]===63||c>2;
    // remove the flow component normal to a single exposed face (flow along the surface)
    ru/=c; rv/=c; rw/=c;
    if(!isItem){ const nn=Math.hypot(...nrm)||1, nx_=nrm[0]/nn, ny_=nrm[1]/nn, nz_=nrm[2]/nn, dot=uu*nx_+vv*ny_+ww*nz_; uu-=dot*nx_; vv-=dot*ny_; ww-=dot*nz_;
      const rd=ru*nx_+rv*ny_+rw*nz_; ru-=rd*nx_; rv-=rd*ny_; rw-=rd*nz_; }
    const Ures= isItem? 100*sm/c : 100*Math.hypot(uu,vv,ww);   // items: mean speed over faces (vectors on opposite faces cancel)
    // every flame gets a buoyant induced flow; under a ceiling (downward-facing surface) buoyancy holds hot gas against
    // the surface instead of driving flow past it, so the effective buoyant forcing is reduced
    const gEff= (!isItem && nrm[1]<0)? 0.1*P.g : P.g;
    const alongG= isItem || nrm[1]===0;   // buoyancy pushes the flame along vertical surfaces only (not along ceilings or floors)
    const fs=flameState(m,X,Ures,Pk,Tg,gEff*9.81,Lup[k]);
    const total=mA[k]+m.m0*m.inert;
    if(st===FL.FLAME){
      if(!fs.exists && !(igT[k]>=0 && t-igT[k]<4 && igns.includes(k))){ fst[k]=FL.OUT; extMode= X<P.X-3? 'oxygen' : fs.mode==='quench'?'quenching':'blowoff'; continue; }
      // burning: mass loss from flame heat flux + external flux
      const qf=m.qfl*Math.max(0.2,(fs.Tf-m.Tv)/(TF_REF-m.Tv));
      // extra heat from a smoky hot layer only (the cell's own flame is already in qf)
      const Tl=Math.min(Tg,1100), qext=Math.max(0,epsLayer(ksoot)*SIGMA*(Tl**4-m.Tv**4))+qx[k];
      // subgrid surface spread to neighbouring fuel (same room only: rooms connect through the gas)
      // spread is driven by the resolved flow over the surface (e.g. the ceiling jet) plus buoyancy along walls;
      // flame existence above used the ventilation flow so a flame cannot blow itself out
      const resU=Math.min(150,100*Math.hypot(ru,rv,rw)), Usp=Math.hypot(resU, alongG? fs.UbL : 0);
      const vo=Vopp(m,fs,Tg,m.m0), vc=Vcon(m,Object.assign({},fs,{Us:Math.max(fs.Us*(alongG?1:0),Usp)}));
      const W=[ru*100+uu*100,(rv*100+vv*100+fs.UbL*(gEff>0&&alongG?1:0)),rw*100+ww*100], Wn=Math.hypot(W[0],W[1],W[2])||1;
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
        YF[n]+=wf[k]*dm*A*m.s/(r*V); YS[n]+=wf[k]*dm*A*m.ys/(r*V); flameAdj[n]=1; }
      Ts[k]=m.Tv;
      if(mA[k]<=1e-3*m.m0){ fst[k]=FL.BURNT; continue; }
    } else {
      // surface energy balance (thermally thin): convection + gas radiation + radiation from neighbouring flames − re-radiation
      let qn=0; for(const [,,,off] of NB26){ const n=k+off; if(n>=0&&n<N&&type[n]===FUEL&&fst[n]===FL.FLAME) qn+=1500; }
      // hot-layer emissivity from soot over a 0.5 m path (absorption ≈ 0.1 × extinction for soot-laden smoke)
      const epsg=epsLayer(ksoot);
      const qin=H_CONV*(Tg-Ts[k])+ epsg*SIGMA*(Tg**4-Ts[k]**4) + qn + qx[k] - 0.9*SIGMA*(Ts[k]**4-T_AMB**4);
      Ts[k]+=qin*dt/(total*m.cs);
      if(Ts[k]>=m.Tv){
        // pyrolysis without a pilot releases unburnt fuel vapour
        const mdot=Math.max(0,qin)/m.Lg, dm=Math.min(mA[k],mdot*dt); mA[k]-=dm; Ts[k]=m.Tv;
        // pyrolysis without flame: unburnt fuel vapour plus dense smoke (smouldering / overheated insulation)
        for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; const r=rho[n]||1; YF[n]+=wf[k]*dm*A*m.s/(r*V); YS[n]+=wf[k]*dm*A*Math.max(0.02,m.ys*1.5)/(r*V); }
        // a severe overheat (≥ 30 kW/m²) acts as a hot-surface pilot
        if(fs.exists && (Tg>T_AIT-150 || prog[k]>0.3 || qx[k]>=30e3)){ fst[k]=FL.FLAME; igT[k]=t; noteIgn(k,'hot gas'); }
        if(mA[k]<=1e-4*m.m0) fst[k]=FL.BURNT;
      } else if(st===FL.NONE && Ts[k]>T_AMB+30) fst[k]=FL.HEAT;
    }
  }
  for(const k of fuelList){ if(inc[k]<=0||fst[k]===FL.FLAME||fst[k]===FL.BURNT) continue;
    prog[k]+=inc[k]; if(fst[k]===FL.NONE) fst[k]=FL.HEAT;
    if(prog[k]>=1){ const m=MAT[MKEYS[mat[k]]];
      let Tg=0,yo=0,c=0; for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=farGas(k+OFF6[d],d); Tg+=T[n]; yo=Math.max(yo,YO[n]); c++; } Tg/=c||1;
      const fs=flameState(m,Xvol(yo),0,P.Pk,Tg,P.g*9.81,0);
      if(fs.Tf>=m.Tc){ fst[k]=FL.FLAME; igT[k]=t; Ts[k]=m.Tv; noteIgn(k,'spread'); } else prog[k]=0.95; } }
}
// The approach flow a surface flame draws on: the gas one cell beyond the flame cell (the flame cell itself holds its products).
function farGas(n,d){ const f=n+OFF6[d]; return (f>=0&&f<N&&type[f]===GAS)? f : n; }
function nearFlame(k){ for(let q=0;q<26;q++){ const n=k+NB26[q][3]; if(fst[n]===FL.FLAME&&type[n]===FUEL) return true; } return false; }
function epsLayer(K){ return Math.min(0.95,0.05+1-Math.exp(-0.1*K*0.5)); }
function noteIgn(k,how){ if(firstIgn<0) firstIgn=k; }

function warmup(){ const ig=igns; igns=[]; for(let i=0;i<30;i++) step(0.25); t=0; igns=ig; }

// ---------------- API ----------------
function ignite(k){ if(type[k]!==FUEL||fst[k]===FL.FLAME||fst[k]===FL.BURNT) return false;
  fst[k]=FL.FLAME; igT[k]=t; Ts[k]=MAT[MKEYS[mat[k]]].Tv; igns.push(k); if(firstIgn<0) firstIgn=k; return true; }
function toggleOpening(oi){ const o=OPEN[oi]; o.open=!o.open; for(const k of o.cells){ type[k]=o.open?GAS:WALL; if(!o.open){u[k]=v[k]=w[k]=0;} else { T[k]=T_AMB; YO[k]=Y0(); YF[k]=0; YS[k]=0; } } buildComps(); ventFlow(); return o.open; }
function igniteItem(ii,mode){ const it=ITEMS[ii]; const cs=it.cells.filter(k=>type[k]===FUEL&&fst[k]!==FL.BURNT); if(!cs.length) return false;
  if(mode==='flame') return ignite(cs[Math.floor(cs.length/2)]);
  const q= mode==='severe'? 40e3 : 15e3; for(const k of cs) qx[k]=Math.max(qx[k],q); if(firstIgn<0) firstIgn=cs[0]; return true; }
function stopOverheat(){ qx.fill(0); }
function setItemMaterial(ii,mk){ if(!MAT[mk]) return; ITEMS[ii].m=mk; reset(); }
function localFlow(it){ let sm=0,c=0; for(const k of it.cells) for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; sm+=Math.hypot(uvx[n],uvy[n],uvz[n]); c++; } return c? 100*sm/c : 0; }   // mean air speed over the exposed surface
function assess(){ return ITEMS.map((it,ii)=>{ const m=MAT[it.m], U=localFlow(it), g=P.g*9.81;
  const fs=flameState(m,P.X,U,P.Pk,T_AMB,g,0), lim=limitX(m,U,P.Pk,'con',g);
  const nf=flameState(m,P.X,0.3,P.Pk,T_AMB,g,0);   // the same spot with the fans off
  return {i:ii, U:+U.toFixed(1), exists:fs.exists, mode:fs.mode, Tf:Math.round(fs.Tf), lim:lim===null?null:+lim.toFixed(1), vo:+Vopp(m,fs,T_AMB,m.m0).toFixed(2), vc:+Vcon(m,fs).toFixed(2), noflow:nf.exists}; }); }
function matTable(){ const g=P.g*9.81; return MKEYS.map(k=>{ const m=MAT[k]; const c=curves(k,P.Pk).con.filter(x=>x!==null); const best=c.length?Math.min(...c):null;
  const fs10=flameState(m,P.X,10,P.Pk,T_AMB,g,0), fs20=flameState(m,P.X,20,P.Pk,T_AMB,g,0);
  return {k, name:m.name, loi:m.loi??null, best0g:best===null?null:+best.toFixed(1), burns10:fs10.exists, lim10:(x=>x===null?null:+x.toFixed(1))(limitX(m,10,P.Pk,'con',g)), vcon20:+Vcon(m,fs20).toFixed(2), vopp:+Vopp(m,fs10,T_AMB,m.m0).toFixed(2), ys:m.ys, refs:REFS[k]||[], src:m.src}; }); }
function setParams(q){ const relining= q.lining && q.lining!==P.lining, flow=(q.U!==undefined&&q.U!==P.U)||(q.vent!==undefined&&q.vent!==P.vent); Object.assign(P,q); if(relining){ reset(); } else if(flow) ventFlow(); }
function stats(){
  const r=ROOMS.map(()=>({flame:0,burnt:0,heat:0,Tmax:T_AMB,Xmin:100,soot:0,sootN:0,hrr:0,pbg:0,vis:99}));
  for(let k=0;k<N;k++){ const ri=room[k]; if(ri<0) continue; const R_=r[ri];
    if(type[k]===GAS){ if(T[k]>R_.Tmax)R_.Tmax=T[k]; const x=Xvol(YO[k]); if(x<R_.Xmin)R_.Xmin=x; R_.hrr+=hrr[k];
      const c=comp[k]; if(comps[c]) R_.pbg=Math.max(R_.pbg,comps[c].pbg);
      // detector band: top 25 cm of the room
      const j=Math.floor(k/nx)%ny; if(cy(j)>=ROOMS[ri].ytop-0.3){ R_.soot+=SOOT_EXT*rho[k]*YS[k]; R_.sootN++; } }
    else if(type[k]===FUEL){ const s=fst[k]; if(s===FL.FLAME) R_.flame++; else if(s===FL.BURNT||s===FL.OUT) R_.burnt++; else if(s===FL.HEAT) R_.heat++; } }
  for(const R_ of r){ const K=R_.sootN? R_.soot/R_.sootN : 0; R_.ext=K; R_.vis= K>1e-4? Math.min(99,3/K) : 99; R_.Xmin=Math.min(R_.Xmin,P.X); }
  return r;
}
reset();
return {
  info:{nx,ny,nz,N,h,NXi,NYi,NZi,LX,LY,LZ,SY,SZ,DIM,AXY,AXZ}, MAT, MKEYS, ROOMS, OPEN, ITEMS, P, FL,
  type, room, openId, sup, ret, mat, faces, fst, prog, igT, Ts, mA, T, YO, YF, YS, u, v, w, hrr,
  get t(){return t;}, get lastDt(){return lastDt;}, get fuelList(){return fuelList;}, get firstIgn(){return firstIgn;}, get extMode(){return extMode;}, get igns(){return igns;},
  step, reset, ignite, toggleOpening, setParams, stats, id, Xvol, igniteItem, stopOverheat, setItemMaterial, assess, matTable, sclass, itemOf, supDx, supDy, supDz, VENTS, qx,
  probe(k){ const m=MAT[MKEYS[mat[k]]]; let Tg=0,yo=0,uu=0,vv=0,c=0; const ds=[];
    for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d], nf=farGas(n,d); ds.push(d); Tg+=T[nf]; yo=Math.max(yo,YO[nf]); uu+=uvx[n]; vv+=uvy[n]; c++; }
    Tg/=c; uu/=c; vv/=c; const X=Xvol(yo), Ures=100*Math.hypot(uu,vv); const fs=flameState(m,X,Ures,P.Pk,Tg,P.g*9.81,Lup[k]);
    return {faces:ds, X:+X.toFixed(2), Ures:+Ures.toFixed(2), Tg:+Tg.toFixed(0), Tf:+fs.Tf.toFixed(0), Tc:+m.Tc.toFixed(0), U:+fs.U.toFixed(1), bc:+fs.bc.toFixed(1), exists:fs.exists, mode:fs.mode}; },
  model:{flameState, Vopp, Vcon, Tflame, Ubo, Ubuoy, KAPPA, T_AMB, TF_REF, LB}, curves, loiVsG, validate, limitX,
};
}
if(typeof module!=='undefined') module.exports={createSolver};
