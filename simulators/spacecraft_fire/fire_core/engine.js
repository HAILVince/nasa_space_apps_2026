// Fire engine v5 — shared 3D variable-density LES-style fire model for crewed spacecraft (geometry from layouts.js).
// Pure JS, no DOM: runs in a Web Worker in the pages and in Node for tests and validation.
// Gas phase: incompressible momentum with density-ratio buoyancy, Smagorinsky SGS viscosity, approximate projection with
//   thermal-expansion and mass-source divergence, semi-Lagrangian advection, sealed-compartment background pressure.
// Combustion: mixing-controlled with an FDS-style critical flame temperature, diluent (CO₂) heat-capacity correction.
// Radiation: P1 (diffusion) approximation for the incident radiation G with soot + gas absorption and Marshak walls.
// Species: O₂, fuel (as O₂ demand), soot, CO, HCN, HF, CO₂ extinguisher agent, water-mist liquid.
// Solids: thin surfaces (lumped) and thick panels (implicit 1D conduction); subgrid flame existence from a flame-temperature
//   model, de Ris opposed spread, Saffire-calibrated concurrent spread (thin linear-in-flow; thick ∝ U q″²/kρc ΔT²).
// Suppression: CO₂ and fine-water-mist extinguishers, vent-to-vacuum depressurisation. Crew: movement and FED dose (ISO 13571).
function createSolver(cfg){
'use strict';
const LAYOUTS=(typeof FIRE_LAYOUTS!=='undefined')? FIRE_LAYOUTS : require('./layouts.js').FIRE_LAYOUTS;
// ---------------- constants ----------------
const SIGMA=5.670e-8, CP=1100, DH_O2=13.1e6, T_AMB=295, CHI_R=0.30, T_CFT=1600, T_AIT=700,
      LAMBDA_G=0.06, H_CONV=10, KAPPA=95, UD=0.5, TA=15000, LB=0.012, GAMMA=1.4, M_AIR=0.0288, RU=8.314,
      SOOT_EXT=8700, Y_SOOT_RXN=0, CP_MIX=1300, T_CELL_MAX=1500, U_CAP=2.5,
      EPS_S=0.9, BETA_W=EPS_S/(2*(2-EPS_S)), RHO_SOOT=1800, LV=2.26e6, CPW=4180, V_DEP=0.15, NL=8, CD_VALVE=0.8;
const TF_REF=T_AMB+KAPPA*21;               // adiabatic reference flame temperature in air, K
const E_AMB=4*SIGMA*T_AMB**4;
const HV=cfg.hv??1500;   // W/m³/K, calibrated on the Saffire IV-1 pressure rise (validate_saffire.js)

// ---------------- materials ----------------
// m0: areal mass kg/m², inert: non-combustible fraction, cs: J/kg/K, Tv: pyrolysis K, s: kg O₂ per kg fuel (ΔHc/13.1 MJ),
// Lg: heat of gasification J/kg, qfl: flame heat flux to own surface W/m², ys: soot yield,
// yco: CO yield in 1 g (well ventilated), yco0: CO yield in 0 g, yhcn / yhf: HCN and HF yields, thick: {k W/m/K, rho kg/m³}.
const MAT={
  sibal:{name:'SIBAL cotton-fiberglass fabric', id:'sibal', m0:0.18, inert:0.25, cs:1300, Tv:620, s:1.23, Lg:2.0e6, qfl:15e3, ys:0.010,
    yco:0.004, yco0:0.034, ys0:0.0006, quench:[[1,21],[5,16]], boOpp:[28,21], boCon:[80,21],
    src:{quench:'BASS-II quench speeds 1–5 cm/s at 21–16% O₂ (ntrs-20150008962)', boOpp:'1 g downward self-extinguishes in air, Lunar g burns (LUCI / FM2)', boCon:'BASS burned at 40 cm/s in air; assumed 80 cm/s', co:'0 g CO yield calibrated on the Saffire IV-1 CO rise (77 ppm in 17.9 m³, ntrs-20260001992)', smoke:'0 g aerosol yield calibrated on the Saffire IV-1 time to the 2 mg/m³ alarm'}},
  pmma:{name:'PMMA (acrylic) panel, 3 mm', id:'pmma', m0:3.57, inert:0, cs:1500, Tv:630, s:1.92, Lg:1.6e6, qfl:18e3, ys:0.022,
    yco:0.010, yco0:0.06, thick:{k:0.19,rho:1190}, Rset:0.35, xmin:16.6, boOpp:[30,18], boCon:[60,18],
    src:{quench:'R assumed; X_min set so the 0 g opposed limit is ~17% (pmc-5760683)', boOpp:'1 g downward limit ~18% (pmc-5760683)', boCon:'Marcum 2016 linear O₂–flow boundary, assumed point', co:'0 g CO yield estimated from Saffire VI-3 (338 ppm, ~3 kW)'}},
  paper:{name:'Thin cellulose (paper, packaging)', id:'cellulose', m0:0.08, inert:0.05, cs:1300, Tv:600, s:1.23, Lg:2.0e6, qfl:15e3, ys:0.010,
    yco:0.004, yco0:0.034, ys0:0.0006, Rset:0.5, xmin:14.5, boOpp:[34,19], boCon:[90,21],
    src:{quench:'R assumed', boOpp:'paper burns downward in 1 g air; partial g easier (ntrs-19930040901)', boCon:'assumed', co:'cellulose: same 0 g yield as SIBAL'}},
  nomex:{name:'Nomex fabric', id:'nomex_iii', m0:0.22, inert:0.40, cs:1200, Tv:800, s:2.1, Lg:3.0e6, qfl:15e3, ys:0.030,
    yco:0.03, yhcn:0.010, Rset:0.45, xmin:24.0, boOpp:[30,28.5], boCon:[60,28],
    src:{quench:'ASSUMED: 0 g limits up to 4% O₂ below 1 g (ntrs-20080034883)', boOpp:'ASSUMED: 1 g LOI ~28–29%', boCon:'assumed'}},
  // Spacecraft materials below start from typical 1 g limiting oxygen indices (ASTM D2863 handbook values); where the
  // knowledge base has NASA-STD-6001 Test 1 upward limits (ntrs-20110008636) those set the 1 g concurrent limit instead.
  pe:{name:'Polyethylene wire insulation', id:'pe', m0:0.30, inert:0, cs:2300, Tv:650, s:3.3, Lg:2.2e6, qfl:20e3, ys:0.06,
    yco:0.024, Rset:0.45, xmin:16.0, boOpp:[30,17.6], boCon:[70,17.4], loi:17.4,
    src:{quench:'ASSUMED from handbook LOI 17.4%', boOpp:'1 g LOI', boCon:'assumed'}},
  ptfe:{name:'PTFE (Teflon) wire insulation', id:'ptfe', m0:0.60, inert:0, cs:1000, Tv:800, s:0.38, Lg:1.8e6, qfl:10e3, ys:0.002,
    yco:0.10, yhf:0.5, Rset:0.45, xmin:92, boOpp:[30,95], boCon:[70,95], loi:95,
    src:{quench:'handbook LOI ~95%: does not burn in any cabin atmosphere', boOpp:'1 g LOI', boCon:'assumed', hf:'HF yield from overheated fluoropolymer insulation: ASSUMED 0.5 kg/kg (ntrs-20140000850 reports significant HF)'}},
  kapton:{name:'Kapton (polyimide) film / wire wrap', id:'kapton', m0:0.07, inert:0.5, cs:1100, Tv:850, s:1.9, Lg:2.5e6, qfl:15e3, ys:0.01,
    yco:0.02, yhcn:0.005, Rset:0.45, xmin:34, boOpp:[30,37], boCon:[70,37], test1:26.5, loi:37,
    src:{quench:'ASSUMED from handbook LOI ~37%', boOpp:'1 g LOI', boCon:'NASA-STD-6001 Test 1 MOC 26–27% for 0.005 in. Kapton HN (ntrs-20110008636)'}},
  silicone:{name:'Silicone rubber (seals, cable jacket)', id:'silicone', m0:1.4, inert:0.6, cs:1300, Tv:700, s:1.15, Lg:2.5e6, qfl:15e3, ys:0.03,
    yco:0.02, thick:{k:0.22,rho:1150}, Rset:0.45, xmin:20.0, boOpp:[30,29], boCon:[70,29], test1:22, loi:29,
    src:{quench:'ASSUMED from handbook LOI 26–30%', boOpp:'1 g LOI', boCon:'NASA-STD-6001 Test 1 MOC 22% for 1 mm silicone (ntrs-20110008636)'}},
  pc:{name:'Polycarbonate panel, 3 mm', id:'pc', m0:3.6, inert:0.2, cs:1300, Tv:700, s:2.35, Lg:2.1e6, qfl:18e3, ys:0.10,
    yco:0.054, thick:{k:0.20,rho:1200}, Rset:0.40, xmin:24.0, boOpp:[30,26.5], boCon:[70,26.5], loi:26.5,
    src:{quench:'ASSUMED from handbook LOI 25–28%', boOpp:'1 g LOI', boCon:'assumed'}},
  pu:{name:'Pyrell polyurethane foam (packing)', id:'pyrell', m0:0.30, inert:0.05, cs:1400, Tv:560, s:2.0, Lg:1.4e6, qfl:20e3, ys:0.10,
    yco:0.031, yhcn:0.010, Rset:0.50, xmin:20.0, boOpp:[30,22.5], boCon:[70,22], loi:22,
    src:{quench:'ASSUMED: flame-retarded PU, LOI ~22%', boOpp:'1 g LOI', boCon:'assumed'}},
  nylon:{name:'Nylon Velcro / webbing', id:'nylon', m0:0.30, inert:0, cs:1700, Tv:700, s:2.3, Lg:2.4e6, qfl:18e3, ys:0.03,
    yco:0.038, yhcn:0.016, Rset:0.45, xmin:18.5, boOpp:[30,24.5], boCon:[70,24], test1:20, loi:24,
    src:{quench:'ASSUMED from handbook LOI 24%; nylon Velcro burned at 30% O₂, 70 kPa in drop tests (ntrs-19870010085)', boOpp:'1 g LOI', boCon:'NASA-STD-6001 Test 1 MOC 20% for Nylon 101 (ntrs-20110008636)'}},
  cotton:{name:'Cotton clothing / towels', id:'cotton', m0:0.15, inert:0.03, cs:1300, Tv:600, s:1.23, Lg:2.0e6, qfl:15e3, ys:0.012,
    yco:0.004, yco0:0.034, ys0:0.0006, Rset:0.50, xmin:16.5, boOpp:[30,18.5], boCon:[70,18.5], loi:18.5,
    src:{quench:'ASSUMED from handbook LOI ~18.5%', boOpp:'1 g LOI', boCon:'assumed', co:'cellulose: same 0 g yield as SIBAL'}},
};
MAT.sibal.loi=19; MAT.pmma.loi=17.3; MAT.paper.loi=18.5; MAT.nomex.loi=28.5;
for(const k in MAT){ const m=MAT[k]; if(m.yco0===undefined) m.yco0=Math.min(0.12,6*m.yco); if(m.ys0===undefined) m.ys0=m.ys; m.yhcn=m.yhcn||0; m.yhf=m.yhf||0; }   // 0 g ≈ 6× 1 g CO yield (Saffire cellulose ~11×, PMMA ~6×)
const REFS={sibal:['ntrs-20150008962','ntrs-20170008805','ntrs-20260001992'], pmma:['pmc-5760683','ntrs-20210017838','ntrs-20260001992'], paper:['ntrs-19930040901'], nomex:['ntrs-20240002981','ntrs-20080034883'],
  pe:['epmc-ppr-ppr477634','ntrs-20140000850'], ptfe:['epmc-med-27501881','ntrs-20140006585','ntrs-20140000850'], kapton:['ntrs-20110008636','ntrs-20040053602'], silicone:['ntrs-20110008636','ntrs-20040053602'],
  pc:['ntrs-20205004657'], pu:['ntrs-20140006585','ntrs-20040084186'], nylon:['ntrs-20110008636','ntrs-19870010085'], cotton:['ntrs-20140006585','ntrs-20260001992']};
const MKEYS=Object.keys(MAT);

// ---------------- flame model (also exported for maps and validation) ----------------
function Tflame(m,X,U,P,Tg){ return Tg + KAPPA*X*(1 - m.R*(101.3/P)/(U+UD)); }
function Ubo(ref,X,P,Tf){ return ref*Math.sqrt(Math.max(0,(P/101.3)*(X/21)))*Math.exp(-(TA/2)*(1/Math.max(Tf,300)-1/TF_REF)); }
function Ubuoy(g,L,Tf,Tg){ return 100*Math.sqrt(Math.max(0,g*(LB+L)*(1-Tg/Math.max(Tf,Tg+1)))); }  // cm/s, Froude scaling
function flameState(m,X,Ures,P,Tg,g,Lup){
  let Tf=Tg+KAPPA*X, U=Ures, Ub=0;
  for(let it=0;it<3;it++){ Ub=Ubuoy(g,0,Tf,Tg); U=Math.hypot(Ures,Ub); Tf=Tflame(m,X,U,P,Tg); }
  const UbL=Ubuoy(g,Lup||0,Tf,Tg), Us=Math.hypot(Ures,UbL);
  const bc=Ubo(m.UboC,X,P,Tf), bo=Ubo(m.UboO,X,P,Tf);
  const rad= Tf>=m.Tc;
  return {Tf,U,Ub,UbL,Us,exists: rad && U<=bc, oppOK: rad && U<=bo, bc, bo, mode: (rad && U<=bc)? 'ok' : U<(m.Uopt||8)? 'quench':'blowoff'};
}
function Vopp(m,fs,Tg,mArea){ // mm/s, de Ris thin-fuel with exact π/4 factor (Delichatsios) and Damköhler factor
  if(!fs.oppOK) return 0;
  // gas conductivity at the flame film temperature (de Ris evaluates gas properties at the flame), air: λ ≈ 0.0241 (T/273)^0.82
  const lam=0.0241*Math.pow(Math.max(300,(fs.Tf+m.Tv)/2)/273,0.82);
  const V=(Math.PI/4)*lam*(fs.Tf-m.Tv)/((mArea||m.m0)*m.cs*Math.max(20,m.Tv-Tg));
  return 1000*V*Math.sqrt(Math.max(0,1-fs.U/fs.bo));
}
function qflame(m,Tf){ return m.qfl*Math.max(0.2,(Tf-m.Tv)/(TF_REF-m.Tv)); }
function Vcon(m,fs){ // mm/s
  if(!fs.exists) return 0;
  const phi=Math.min(4,Math.max(0,(fs.Tf-m.Tc)/(TF_REF-m.Tc))), damk=Math.sqrt(Math.max(0,1-fs.U/fs.bc)), Us=fs.Us||fs.U;
  if(m.thick){ // thick fuel: V = 4 q″² δ_f /(π kρc (Tv−T∞)²) with flame length δ_f ∝ U (laminar), calibrated to Saffire VI-3
    const q=qflame(m,fs.Tf), kpc=m.thick.k*m.thick.rho*m.cs; return m.kt*Us*q*q/(kpc*(m.Tv-T_AMB)**2)*damk; }
  return m.kc*Us*Math.pow(phi,NX)*damk;   // thin fuel: linear in flow (BASS); coefficient from Saffire-1, O₂ exponent from Saffire VI-2
}
// ---- calibration from knowledge-base targets ----
let NX=1;
function calibrate(){
  for(const k of MKEYS){ const m=MAT[k];
    if(m.quench){ const [[U1,X1],[U2,X2]]=m.quench; m.R=(X1-X2)/(X1/(U1+UD)-X2/(U2+UD)); m.Tc=T_AMB+KAPPA*X1*(1-m.R/(U1+UD)); }
    else { m.R=m.Rset; m.Tc=T_AMB+KAPPA*m.xmin; }
    const solveRef=([Ut,Xt])=>{ const Tf=Tflame(m,Xt,Ut,101.3,T_AMB); return Ut/Ubo(1,Xt,101.3,Tf); };
    m.UboO=solveRef(m.boOpp); m.UboC=solveRef(m.boCon);
    if(m.test1){ // 1 g upward (NASA-STD-6001 Test 1): set the radiative-extinction oxygen level so the buoyant concurrent limit is the MOC
      const bc=[70,m.test1+1]; m.UboC=solveRef(bc);
      let lo=5, hi=60; for(let i=0;i<40;i++){ m.xmin=(lo+hi)/2; m.Tc=T_AMB+KAPPA*m.xmin; m.UboC=solveRef(bc); const x=limitX(m,0,101.3,'con',9.81); if(x===null||x>m.test1) hi=m.xmin; else lo=m.xmin; }
      m.Tc=T_AMB+KAPPA*m.xmin; m.UboC=solveRef(bc); }
  }
  // thin concurrent spread: Saffire-1 (SIBAL, 0 g, 21.7%, 101 kPa, 20 cm/s → 1.8 mm/s) sets the coefficient, Saffire VI-2
  // (SIBAL, 31%, 54.1 kPa → 4.05 mm/s) sets the oxygen exponent of the flame-temperature factor
  const s=MAT.sibal, fs=flameState(s,21.7,20,101.3,T_AMB,0,0), f6=flameState(s,31,20,54.1,T_AMB,0,0);
  const ph=x=>(x.Tf-s.Tc)/(TF_REF-s.Tc), dk=x=>Math.sqrt(Math.max(0,1-x.U/x.bc));
  NX=Math.log((4.05/1.8)*dk(fs)/dk(f6))/Math.log(ph(f6)/ph(fs));
  s.kc=1; s.kc=1.8/Vcon(s,fs);
  for(const k of MKEYS){ if(k==='sibal') continue; const m=MAT[k];
    m.kc=s.kc*(m.qfl/s.qfl)*(s.m0*s.cs*(s.Tv-T_AMB))/(m.m0*m.cs*(m.Tv-T_AMB)); }
  const p=MAT.pmma; p.kt=1; const fp=flameState(p,30,20,54.4,T_AMB,0,0); p.kt=0.38/Vcon(p,fp);   // Saffire VI-3: 10 mm PMMA, 30%, 54.4 kPa → 0.38 mm/s
  for(const k of MKEYS) if(MAT[k].thick) MAT[k].kt=p.kt;
}
// ---- limits, curves and validation ----
function limitX(m,U,P,mode,g){ const ok=X=>{ const fs=flameState(m,X,U,P,T_AMB,g||0,0); return mode==='opp'? fs.oppOK : fs.exists; };
  let lo=5, hi=80; if(!ok(hi)) return null; if(ok(lo)) return lo;
  for(let i=0;i<40;i++){ const mid=(lo+hi)/2; if(ok(mid)) hi=mid; else lo=mid; } return hi; }
calibrate();
function quenchU(m,X,P){ const ok=U=>flameState(m,X,U,P,T_AMB,0,0).exists; let lo=0.01, hi=-1;
  for(let U=0.05;U<=60;U*=1.15){ if(ok(U)){ hi=U; break; } lo=U; } if(hi<0) return null; if(ok(0.01)) return 0;
  for(let i=0;i<40;i++){ const mid=(lo+hi)/2; if(ok(mid)) hi=mid; else lo=mid; } return hi; }
for(const k of MKEYS){ const m=MAT[k]; let best=1e9, ub=8; for(let U=0.5;U<=80;U+=0.5){ const x=limitX(m,U,101.3,'con',0); if(x!==null&&x<best){best=x;ub=U;} } m.Uopt=ub; }
function curves(mk,P){ const m=MAT[mk], U=[], con=[], opp=[]; for(let u=0.25;u<=60;u+=0.25){ U.push(u); con.push(limitX(m,u,P,'con',0)); opp.push(limitX(m,u,P,'opp',0)); } return {U,con,opp}; }
function loiVsG(mk,P){ const m=MAT[mk], G=[], down=[], up=[]; for(let g=0;g<=1.0001;g+=0.01){ G.push(+g.toFixed(2)); down.push(limitX(m,0,P,'opp',g*9.81)); up.push(limitX(m,0,P,'con',g*9.81)); } return {G,down,up}; }
function validate(){
  const S_=MAT.sibal, PM=MAT.pmma, rows=[];
  const fsA=(m,X,U,P,g)=>flameState(m,X,U,P,T_AMB,(g||0)*9.81,0);
  const row=(name,cond,meas,model,unit,use,src,note,mv)=>rows.push({name,cond,meas,model,unit,use,src,note,mv});
  const v1=Vcon(S_,fsA(S_,21.7,20,101.3));
  row('Concurrent spread, SIBAL','0 g · 21.7% · 101 kPa · 20 cm/s','1.8',v1.toFixed(2),'mm/s','calibration','Saffire-1 (NTRS 20170008805)','sets the thin concurrent coefficient',[1.8,v1]);
  const v2=Vcon(S_,fsA(S_,22.1,20,101.3)), v25=Vcon(S_,fsA(S_,22.1,25,101.3));
  row('Concurrent spread, SIBAL 5 cm strip','0 g · 22.1% · 101 kPa · 20 cm/s','2.1',v2.toFixed(2),'mm/s','independent','Saffire-2 (NTRS 20170008805)','narrow strip, not used in fitting',[2.1,v2]);
  row('Concurrent spread, SIBAL 5 cm strip','0 g · 22.1% · 101 kPa · 25 cm/s','2.6',v25.toFixed(2),'mm/s','independent','Saffire-2 (NTRS 20170008805)','',[2.6,v25]);
  const vo1=Vopp(S_,fsA(S_,21.7,20,101.3),T_AMB,S_.m0);
  row('Opposed spread, SIBAL','0 g · 21.7% · 101 kPa · 20 cm/s','1.3',vo1.toFixed(2),'mm/s','independent','Saffire-1 opposed test (NTRS 20170008805)','',[1.3,vo1]);
  for(const [nm,X,P,meas,use] of [['IV-1',23,98,3.6,'independent'],['VI-2',31,54.1,4.05,'calibration']]){ const v=Vcon(S_,fsA(S_,X,20,P)); row('Concurrent spread, SIBAL 40 cm',`0 g · ${X}% · ${P} kPa · 20 cm/s`,String(meas),v.toFixed(2),'mm/s',use,`Saffire ${nm} (NTRS 20260001992)`,use==='calibration'?`sets the O₂ exponent (n = ${NX.toFixed(2)})`:'',use==='independent'?[meas,v]:undefined); }
  const C_=MAT.cotton, vc2=Vcon(C_,fsA(C_,28,20,74.1)); row('Concurrent spread, cotton jersey','0 g · 28% · 74.1 kPa · 20 cm/s','3.4',vc2.toFixed(2),'mm/s','independent','Saffire V-2 (NTRS 20260001992)','cotton areal mass is a handbook value',[3.4,vc2]);
  const q21=quenchU(S_,21,101.3), q16=quenchU(S_,16,101.3);
  row('Quench flow speed, SIBAL','0 g · 21% · 101 kPa','≈1',q21===null?'none':q21.toFixed(2),'cm/s','calibration','BASS-II (ntrs-20150008962)','');
  row('Quench flow speed, SIBAL','0 g · 16% · 101 kPa','≈5',q16===null?'none':q16.toFixed(2),'cm/s','calibration','BASS-II (ntrs-20150008962)','');
  const lu=fsA(S_,21,0,101.3,0.165), vl=Vopp(S_,lu,T_AMB,S_.m0);
  row('Downward spread, SIBAL','Lunar g · air · quiescent','0.92–1.1',vl.toFixed(2),'mm/s','independent','LUCI, preliminary (ntrs-20250010653)','flame base 0.92, tip 1.1 mm/s',[1.0,vl]);
  const e1=fsA(S_,21,0,101.3,1);
  row('Downward burning, SIBAL','1 g · air · quiescent','self-extinguishes',e1.oppOK?'burns ('+Vopp(S_,e1,T_AMB,S_.m0).toFixed(2)+' mm/s)':'extinguishes','','calibration','LUCI / FM2 (ntrs-20240015307)','sets the opposed blowoff constant');
  const p0=limitX(PM,5,101.3,'opp',0), p1=limitX(PM,0,101.3,'opp',9.81);
  row('Opposed-flow limit, PMMA','0 g · 101 kPa · ~5 cm/s','≈17',p0===null?'none':p0.toFixed(1),'% O₂','calibration','ISS PMMA cylinders (pmc-5760683)','');
  row('Downward limit, PMMA','1 g · 101 kPa · quiescent','≈18',p1===null?'none':p1.toFixed(1),'% O₂','calibration','ISS vs 1 g PMMA (pmc-5760683)','');
  // NASA-STD-6001 Test 1 (1 g upward) maximum oxygen concentrations
  const pu=limitX(PM,0,101.3,'con',9.81);
  row('Upward limit (Test 1 MOC), PMMA rod','1 g · 101 kPa · quiescent','18–19',pu===null?'none':pu.toFixed(1),'% O₂','independent','NASA-STD-6001 Test 1 (ntrs-20110008636)','',[18.5,pu]);
  for(const k of ['kapton','silicone','nylon']){ const m=MAT[k], x=limitX(m,0,101.3,'con',9.81);
    row(`Upward limit (Test 1 MOC), ${m.name.split(' (')[0]}`,'1 g · 101 kPa · quiescent',String(m.test1),x===null?'none':x.toFixed(1),'% O₂','calibration','NASA-STD-6001 Test 1 (ntrs-20110008636)','sets this material\'s quench parameter'); }
  // thick PMMA concurrent growth in Saffire IV–VI
  const thk=(X,P)=>Vcon(PM,fsA(PM,X,20,P));
  row('Concurrent growth, 10 mm PMMA 2-sided','0 g · 30% · 54.4 kPa · 20 cm/s','0.38',thk(30,54.4).toFixed(2),'mm/s','calibration','Saffire VI-3 (NTRS 20260001992)','sets the thick-fuel coefficient');
  for(const [nm,X,P,meas,sd] of [['IV-2',22,100,0.22,'2-sided'],['V-3',26,74.5,0.26,'1-sided'],['VI-4',29,55,0.27,'1-sided']]){ const v=thk(X,P);
    row(`Concurrent growth, PMMA ${sd}`,`0 g · ${X}% · ${P} kPa · 20 cm/s`,String(meas),v.toFixed(2),'mm/s','independent',`Saffire ${nm} (NTRS 20260001992)`,'',[meas,v]); }
  const rib=Object.assign({},PM,{m0:1.19,thick:null});
  const vr=Vopp(rib,flameState(rib,26.9,20,76,T_AMB,0,0),T_AMB,1.19);
  row('Opposed edge spread, PMMA rib','0 g · 26.9% · 76 kPa · 20 cm/s','0.88',vr.toFixed(2),'mm/s','independent','Saffire V (ntrs-20210017838)','1 mm rib edge; flat-sheet theory misses edge heating',[0.88,vr]);
  const lg=loiVsG('sibal',101.3); let gmin=0,xmin=1e9; lg.G.forEach((g,i)=>{ const x=lg.down[i]; if(x!==null&&x<xmin){xmin=x;gmin=g;} });
  row('Gravity of easiest burning, SIBAL downward','air pressure, quiescent','near Lunar g (~0.16 g)',gmin.toFixed(2)+' g','','qualitative','LPSC 2026 Ferkul et al. (ntrs-20260000646)','');
  const l1=limitX(S_,0,101.3,'con',9.81), l0=Math.min(...curves('sibal',101.3).con.filter(x=>x!==null));
  row('1 g minus best 0 g limit, SIBAL','101 kPa','up to 4',(l1-l0).toFixed(1),'% O₂ pts','qualitative','Exploration atmospheres (ntrs-20080034883)','');
  return rows;
}

// ---------------- grid from the layout ----------------
const GAS=0, WALL=1, FUEL=2;
const ctx={SY:0, solid:k=>type[k]!==GAS};
const LYT=LAYOUTS[cfg.layout||'ship'](ctx,cfg);
// dim 2: a vertical (x–y) section one cell deep; the front and back faces are symmetry planes (no flux, no wall losses)
const DIM=LYT.dim||3; const h=cfg.h||0.15, LX=LYT.LX, LY=LYT.LY, LZ= DIM===2? h : LYT.LZ, AXY=LYT.AXY, AXZ= DIM===2? h/2 : LYT.AXZ;
const NXi=Math.round(LX/h), NYi=Math.round(LY/h), NZi= DIM===2? 1 : Math.round(LZ/h);
const nx=NXi+2, ny=NYi+2, nz=NZi+2, N=nx*ny*nz, SY=nx, SZ=nx*ny, V=h*h*h, A=h*h; ctx.SY=SY;
const id=(i,j,l)=>i+nx*(j+ny*l);
const ci=x=>Math.min(NXi,Math.max(1,Math.floor(x/h+1e-9)+1));
const cj=y=>Math.min(NYi,Math.max(1,Math.floor(y/h+1e-9)+1));
const ck=z=>Math.min(NZi,Math.max(1,Math.floor(z/h+1e-9)+1));
const cx=i=>(i-0.5)*h, cy=j=>(j-0.5)*h, cz=l=>(l-0.5)*h;
const type=new Uint8Array(N), room=new Int8Array(N), openId=new Int8Array(N), sup=new Uint8Array(N), ret=new Uint8Array(N);
const supDx=new Int8Array(N), supDy=new Int8Array(N), supDz=new Int8Array(N), supSp=new Float64Array(N), itemOf=new Int16Array(N), sclass=new Uint8Array(N);
const inBox=(x,y,z,b)=> x>=b.x[0]&&x<b.x[1]&&y>=b.y[0]&&y<b.y[1]&&z>=b.z[0]&&z<b.z[1];
const ROOMS=LYT.ROOMS, SHELLS=LYT.SHELLS, OPEN=LYT.OPEN, VENTS=LYT.VENTS, ITEMS=LYT.ITEMS, VALVES=LYT.VALVES||[];
for(const it of ITEMS) it.on= it.on!==false;

// ---------------- state ----------------
const P={g:cfg.g??0, X:cfg.X??21, Pk:cfg.Pk??101.3, U:cfg.U??40, vent:cfg.vent??true};
const qx=new Float64Array(N);   // imposed heat flux on a surface (electrical overheat), W/m²
const u=new Float64Array(N), v=new Float64Array(N), w=new Float64Array(N);
const u2=new Float64Array(N), v2=new Float64Array(N), w2=new Float64Array(N);
const uvx=new Float64Array(N), uvy=new Float64Array(N), uvz=new Float64Array(N);   // ventilation-only flow
const T=new Float64Array(N), YO=new Float64Array(N), YF=new Float64Array(N), YS=new Float64Array(N);
const YC=new Float64Array(N), YN=new Float64Array(N), YH=new Float64Array(N), YD=new Float64Array(N), YW=new Float64Array(N);
const Grad=new Float64Array(N).fill(E_AMB), kap=new Float64Array(N), Erad=new Float64Array(N), Ewall=new Float64Array(N);
const tmp=new Float64Array(N), p=new Float64Array(N), rhs=new Float64Array(N), D=new Float64Array(N), Dx=new Float64Array(N), nut=new Float64Array(N), rho=new Float64Array(N), hrr=new Float64Array(N), qv=new Float64Array(N);
const comp=new Int32Array(N); let comps=[];
const roomPf=new Float64Array(ROOMS.length).fill(1), roomPbg=new Float64Array(ROOMS.length);
const wf=new Float64Array(N).fill(1), M0=new Float64Array(N);
const mat=new Int8Array(N).fill(-1), faces=new Uint8Array(N), mA=new Float64Array(N), Ts=new Float64Array(N), fst=new Uint8Array(N),
      prog=new Float64Array(N), igT=new Float64Array(N), Lup=new Float64Array(N), flameAdj=new Uint8Array(N), inc=new Float64Array(N);
const thickOff=new Int32Array(N).fill(-1); let TN=new Float64Array(0);
let fuelList=[], t=0, firstIgn=-1, igns=[], extMode=null, events=[], radOn=false, sprays=[], script=[], actions=[], crew=[];
const FL={NONE:0, HEAT:1, FLAME:2, OUT:3, BURNT:4};
const NB6=[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]];
const OFF6=NB6.map(([a,b,c])=>a+b*SY+c*SZ);
const NB26=[]; for(let c=-1;c<=1;c++)for(let b=-1;b<=1;b++)for(let a=-1;a<=1;a++){ if(a||b||c) NB26.push([a,b,c,a+b*SY+c*SZ,Math.hypot(a,b,c)]); }
const Y0=()=>{ const X=P.X/100; return X*32/(X*32+(1-X)*28); };
const Xvol=y=>{ const n=y/32, r=(1-y)/28; return 100*n/(n+r); };
const xCO2=y=>{ const n=y/44, r=(1-y)/28.8; return n/(n+r); };
const ppm=(y,M)=>y*28.8/M*1e6;
const SC=[YO,YF,YS,YC,YN,YH,YD,YW];

function build(){
  type.fill(WALL); room.fill(-1); openId.fill(-1); sup.fill(0); ret.fill(0); supSp.fill(0); supDx.fill(0); supDy.fill(0); supDz.fill(0);
  mat.fill(-1); faces.fill(0); wf.fill(1); qx.fill(0); itemOf.fill(-1); sclass.fill(1); thickOff.fill(-1);
  const C=fn=>{ for(let l=1;l<=NZi;l++)for(let j=1;j<=NYi;j++)for(let i=1;i<=NXi;i++) fn(id(i,j,l),cx(i),cy(j),cz(l)); };
  C((k,x,y,z)=>{ sclass[k]=LYT.sclass(x,y,z); });
  C((k,x,y,z)=>{ ROOMS.forEach((r,ri)=>{ if(!r.late&&r.test(x,y,z)){ type[k]=GAS; room[k]=ri; } }); });
  C((k,x,y,z)=>{ for(const sh of SHELLS) if(sh.test(x,y,z)){ type[k]=WALL; room[k]=-1; sclass[k]=sh.cls; } });
  C((k,x,y,z)=>{ ROOMS.forEach((r,ri)=>{ if(r.late&&r.test(x,y,z)){ type[k]=GAS; room[k]=ri; } }); });
  OPEN.forEach((o,oi)=>{ o.cells=[]; C((k,x,y,z)=>{ if(type[k]===WALL&&o.test(x,y,z)){ o.cells.push(k); openId[k]=oi; } }); for(const k of o.cells) type[k]= o.open? GAS : WALL;
    let sx=0,sy=0,sz=0; for(const k of o.cells){ sx+=cx(k%nx); sy+=cy(Math.floor(k/nx)%ny); sz+=cz(Math.floor(k/SZ)); } const n=o.cells.length||1; o.c=[sx/n,sy/n,sz/n]; });
  for(const vt of VENTS){ const ri=ROOMS.findIndex(r=>r.id===vt.room);
    C((k,x,y,z)=>{ if(type[k]!==GAS||room[k]!==ri||!vt.test(x,y,z,k)) return;
      if(vt.kind==='sup'){ sup[k]=1; supDx[k]=vt.dir[0]; supDy[k]=vt.dir[1]; supDz[k]=vt.dir[2]; supSp[k]=vt.sp; } else ret[k]=1; }); }
  ITEMS.forEach((it,ii)=>{ const mi=MKEYS.indexOf(it.m), ri=ROOMS.findIndex(r=>r.id===it.room); it.cells=[]; if(!it.on) return;
    C((k,x,y,z)=>{ if(!(it.test? it.test(x,y,z) : inBox(x,y,z,it))) return; if(openId[k]>=0||sup[k]||ret[k]) return;
      if(it.onWall? type[k]!==WALL : type[k]!==GAS) return;
      type[k]=FUEL; mat[k]=mi; faces[k]=63; itemOf[k]=ii; room[k]=ri; wf[k]=it.af||1; M0[k]=it.m0||MAT[it.m].m0; it.cells.push(k); }); });
  fuelList=[]; let nThick=0;
  for(let k=0;k<N;k++) if(type[k]===FUEL){
    let f=0; for(let d=0;d<6;d++) if((faces[k]>>d)&1 && type[k+OFF6[d]]===GAS) f|=1<<d; faces[k]=f;
    if(f){ fuelList.push(k); if(MAT[MKEYS[mat[k]]].thick) thickOff[k]=(nThick++)*NL; } else { type[k]=WALL; mat[k]=-1; itemOf[k]=-1; } }
  TN=new Float64Array(nThick*NL);
  for(const it of ITEMS) it.cells=it.cells.filter(k=>type[k]===FUEL);
  for(const vl of VALVES){ const ri=ROOMS.findIndex(r=>r.id===vl.room); vl.cells=[]; C((k,x,y,z)=>{ if(type[k]===GAS&&room[k]===ri&&vl.test(x,y,z)) vl.cells.push(k); }); vl.active=vl.active||false; }
  ROOMS.forEach((r,ri)=>{ let top=0,sx=0,sy=0,sz=0,n=0; C((k,x,y,z)=>{ if(type[k]===GAS&&room[k]===ri){ if(y>top) top=y; sx+=x; sy+=y; sz+=z; n++; } }); r.ytop=top; r.y1=top+h/2; r.c=n?[sx/n,sy/n,sz/n]:[0,0,0]; r.cells=n; r.vol=n*V; });
  buildComps();
}
function buildComps(){
  comp.fill(-1); comps=[];
  for(let k=0;k<N;k++){ if(type[k]!==GAS||comp[k]>=0) continue;
    const c={vol:0, outlet:false, pbg:0, pf:1, cells:0, venting:false, rooms:new Set()}; const ci_=comps.length; comps.push(c);
    const st=[k]; comp[k]=ci_; let sp=0, sb=0, nr=0;
    while(st.length){ const q=st.pop(); c.cells++; if(ret[q]) c.outlet=true; const ri=room[q]; if(ri>=0){ c.rooms.add(ri); sp+=roomPf[ri]; sb+=roomPbg[ri]; nr++; }
      for(let d=0;d<6;d++){ const n=q+OFF6[d]; if(type[n]===GAS&&comp[n]<0){ comp[n]=ci_; st.push(n); } } }
    c.vol=c.cells*V; if(nr){ c.pf=sp/nr; c.pbg=sb/nr; } for(const ri of c.rooms){ roomPf[ri]=c.pf; roomPbg[ri]=c.pbg; } }
  for(const vl of VALVES) if(vl.active) for(const k of vl.cells) if(comp[k]>=0) comps[comp[k]].venting=true;
  buildLists();
}
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
  u.fill(0);v.fill(0);w.fill(0);p.fill(0);T.fill(T_AMB);YO.fill(y0);YF.fill(0);YS.fill(0);YC.fill(0);YN.fill(0);YH.fill(0);YD.fill(0);YW.fill(0);hrr.fill(0);Grad.fill(E_AMB);
  for(const k of fuelList){ const m=MAT[MKEYS[mat[k]]]; mA[k]=M0[k]*(1-m.inert); Ts[k]=T_AMB; fst[k]=FL.NONE; prog[k]=0; igT[k]=-1; const o=thickOff[k]; if(o>=0) TN.fill(T_AMB,o,o+NL); }
  roomPf.fill(1); roomPbg.fill(0); for(const c of comps){ c.pf=1; c.pbg=0; }
  t=0; firstIgn=-1; igns=[]; extMode=null; events=[]; sprays=[]; actions=[]; scriptPos=0; radOn=false;
  initCrew();
}
function reset(){ for(const vl of VALVES) vl.active=false; build(); initFields(); ventFlow(); warmup(); }
function ventFlow(){
  const su=u.slice(), sv=v.slice(), sw=w.slice(), sp=p.slice(), sd=D.slice();
  u.fill(0); v.fill(0); w.fill(0); p.fill(0); D.fill(0); const it=cfg.iters; cfg.iters=400; velBC(); project(1.0); velBC(); cfg.iters=it;
  uvx.set(u); uvy.set(v); uvz.set(w); u.set(su); v.set(sv); w.set(sw); p.set(sp); D.set(sd);
}

// ---------------- helpers ----------------
function ghost(f,def){
  for(let q=0;q<border.length;q++){ const k=border[q]; let s=0,c=0;
    for(let d=0;d<6;d++){ const n=k+OFF6[d]; if(n>=0&&n<N&&type[n]===GAS){ s+=f[n]; c++; } }
    f[k]= c? s/c : def; }
}
function sample(f,x,y,z){
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
    if(sup[k]&&ventOn) div-=P.U/100*supSp[k]*ih;
    rhs[k]=(div-D[k])*idt; }
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
const pAbs=k=>{ const c=comps[comp[k]]; return c? P.Pk*1000*c.pf+c.pbg : P.Pk*1000; };   // local absolute pressure, Pa

// ---------------- P1 radiation ----------------
// −∇·(Γ∇G) + κG = E,  Γ = 1/(3κ);  walls: −Γ ∂G/∂n = β (G − 4σT_w⁴), β = ε/(2(2−ε)).  Red-black SOR, warm-started each step.
function radiation(){
  const ih2=1/(h*h), bh=BETA_W/h;
  for(let q=0;q<border.length;q++){ const k=border[q]; const Tw= type[k]===FUEL? Ts[k] : T_AMB; Ewall[k]=4*SIGMA*Tw*Tw*Tw*Tw; }
  for(let it=0;it<6;it++) for(let pass=0;pass<2;pass++){ const L=pass?black:red;
    for(let q=0;q<L.length;q++){ const k=L[q], m=nbMask[k], ka=kap[k], Gk=1/(3*ka);
      let aS=0, aG=0;
      for(let d=0;d<6;d++){ const n=k+OFF6[d];
        if((m>>d)&1){ const a=0.5*(Gk+1/(3*kap[n]))*ih2; aS+=a; aG+=a*Grad[n]; }
        else if(DIM===3||d<4){ aS+=bh; aG+=bh*Ewall[n]; } }
      const Gn=(aG+Erad[k])/(aS+ka); Grad[k]+=1.6*(Gn-Grad[k]); if(Grad[k]<0) Grad[k]=0; } }
}

// ---------------- one time step ----------------
let lastDt=0.1, scriptPos=0;
function step(dtMax){
  while(scriptPos<script.length && script[scriptPos].t<=t){ command(script[scriptPos], true); scriptPos++; }
  const g=P.g*9.81, y0=Y0(), ventOn=P.vent&&P.U>0;
  let umax=0.05; for(let q=0;q<gasList.length;q++){ const k=gasList[q]; const a=Math.abs(u[k])+Math.abs(v[k])+Math.abs(w[k]); if(a>umax) umax=a; }
  const dt=Math.max(0.03,Math.min(dtMax, 2.0*h/umax)); lastDt=dt;
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; rho[k]=pAbs(k)*M_AIR/(RU*T[k]); }
  // ---- momentum
  smagorinsky(dt);
  advect(u,u2,dt); advect(v,v2,dt); advect(w,w2,dt); u.set(u2); v.set(v2); w.set(w2);
  if(g>0) for(let q=0;q<gasList.length;q++){ const k=gasList[q]; v[k]+=dt*g*(T[k]/T_AMB-1); }
  diffuse(u,dt,1,1.6e-5); diffuse(v,dt,1,1.6e-5); diffuse(w,dt,1,1.6e-5);
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; const s=Math.abs(u[k])+Math.abs(v[k])+Math.abs(w[k]); if(s>U_CAP){ const f=U_CAP/s; u[k]*=f; v[k]*=f; w[k]*=f; } }
  velBC(); project(dt); velBC(); if(DIM===2) w.fill(0);
  // ---- scalars
  ghost(T,T_AMB); for(const f of SC) ghost(f, f===YO? y0 : 0);
  advect(T,tmp,dt); T.set(tmp); for(const f of SC){ advect(f,tmp,dt); f.set(tmp); }
  diffuse(T,dt,2,2.2e-5); for(const f of SC) diffuse(f,dt,2,f===YS||f===YW?1e-5:2.0e-5);
  if(ventOn) recirculate();
  Dx.fill(0);
  // ---- solids: surface heating, flame existence, burning, spread
  solids(dt,g);
  // ---- extinguishers, water mist evaporation and venting
  suppression(dt);
  // ---- gas combustion
  hrr.fill(0); let anyHot=false;
  for(let q=0;q<gasList.length;q++){ const k=gasList[q];
    const r=rho[k]; let qq=0; const yf=YF[k], yo=YO[k];
    if(yf>1e-7 && yo>1e-5){
      const cpe=CP_MIX*(1+0.6*xCO2(YD[k])), Tpot=T[k]+yo*DH_O2/cpe;
      if(flameAdj[k] || (T[k]>T_AIT && Tpot>=T_CFT)){
        const sp=Math.hypot(u[k],v[k],w[k]);
        const tau= flameAdj[k]? 0.05 : Math.min(2,Math.max(0.1,h/(sp+Math.sqrt(Math.max(g,0.05)*h))));
        const dd=Math.min(yf,yo)*(1-Math.exp(-dt/tau));
        YF[k]-=dd; YO[k]-=dd; YS[k]+=Y_SOOT_RXN*dd;
        qq=r*dd*DH_O2/dt;
      } }
    qv[k]=qq; hrr[k]=qq*V; if(qq>0||T[k]>340) anyHot=true;
    // absorption: soot (Planck mean 1862 f_v T) + combustion gases; emission: χr q̇ in reacting cells, 4κσT⁴ elsewhere
    const fv=r*YS[k]/RHO_SOOT, Tk=T[k];
    kap[k]=0.03+Math.min(30,1862*fv*Tk)+0.3*Math.max(0,1-yo/y0);
    Erad[k]= qq>0? CHI_R*qq : 4*kap[k]*SIGMA*Tk**4;
  }
  if(anyHot||radOn){ radiation(); radOn=anyHot; }
  else { for(let q=0;q<gasList.length;q++) Grad[gasList[q]]=E_AMB; }
  // ---- energy, expansion source and sealed-compartment pressure
  D.fill(0);
  const qComp=new Float64Array(comps.length);
  for(let q=0;q<gasList.length;q++){ const k=gasList[q];
    const r=rho[k], qq=qv[k], Tk=T[k];
    const qrad=kap[k]*Grad[k]-Erad[k];
    const m=nbMask[k]; let nw=0; for(let d=0;d<(DIM===2?4:6);d++) if(!((m>>d)&1)) nw++;
    const qwall=nw*H_CONV*A*(Tk-T_AMB)/V;
    // cargo, racks and stowage: a distributed heat sink with a large surface area (Saffire IV-1 pressure rise), not inside flames
    const qsink= qq>0? 0 : HV*(Tk-T_AMB);
    const qnet=qq+qrad-qwall-qsink;
    T[k]=Math.max(T_AMB-40,Math.min(T_CELL_MAX,Tk+qnet*dt/(r*CP)));
    D[k]=qnet/(r*CP*T[k])+Dx[k];
    qComp[comp[k]]+=qnet*V;
    if(YO[k]<0) YO[k]=0; if(YF[k]<0) YF[k]=0;
  }
  for(let c=0;c<comps.length;c++){ const C=comps[c];
    if(C.venting){ const tau=C.vol/(CD_VALVE*valveArea(c)*199); const f=Math.exp(-dt/tau); C.pf*=f; C.pbg*=f; }
    else if(C.outlet&&ventOn) C.pbg=0; else C.pbg+=(GAMMA-1)*qComp[c]/C.vol*dt;
    for(const ri of C.rooms){ roomPf[ri]=C.pf; roomPbg[ri]=C.pbg; } }
  t+=dt;
  updateCrew(dt);
  return dt;
}
// Recirculating ventilation (as on the ISS): return air is drawn through the return grilles, passes a particulate (HEPA)
// filter and the cooler, and is blown back through the diffusers. CO, HCN, HF, CO₂ and the O₂ deficit stay in the cabin.
// Compartments without a return grille (crew quarters, rack) recirculate their own air.
const RC=new Float64Array(SC.length), FILTER_SOOT=0.99;
let compSum=null;
function recirculate(){
  const nc=comps.length; if(!compSum||compSum.length<nc*(SC.length+2)) compSum=new Float64Array(nc*(SC.length+2)*2);
  compSum.fill(0); const W=SC.length+1;
  RC.fill(0); let nr=0;
  for(let q=0;q<gasList.length;q++){ const k=gasList[q], c=comp[k];
    if(ret[k]){ for(let f=0;f<SC.length;f++) RC[f]+=SC[f][k]; nr++; }
    const b=c*W; for(let f=0;f<SC.length;f++) compSum[b+f]+=SC[f][k]; compSum[b+SC.length]++; }
  if(nr) for(let f=0;f<SC.length;f++) RC[f]/=nr;
  for(let c=0;c<nc;c++){ const b=c*W; comps[c].yo=compSum[b]/(compSum[b+SC.length]||1); }
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; if(!sup[k]) continue; const c=comp[k];
    const useRet= nr>0 && comps[c].outlet, b=c*W, n=compSum[b+SC.length]||1;
    for(let f=0;f<SC.length;f++){ const F=SC[f]; F[k]= useRet? RC[f] : compSum[b+f]/n; }
    YS[k]*=1-FILTER_SOOT; YW[k]=0; YF[k]*=0.5; T[k]=T_AMB; }
}
function valveArea(c){ let a=0; for(const vl of VALVES) if(vl.active&&vl.cells.some(k=>comp[k]===c)) a+=vl.area; return Math.max(a,1e-6); }

// ---------------- thick solids: implicit 1D conduction through the panel (insulated back / symmetry plane) ----------------
const ta=new Float64Array(NL), tb_=new Float64Array(NL), tc=new Float64Array(NL), td=new Float64Array(NL);
function conduct(k,dt,qin,fixTs){ // returns [surface T, conduction flux into the solid W/m²]
  const m=MAT[MKEYS[mat[k]]], o=thickOff[k], nf=Math.max(1,popc(faces[k]));
  const del=Math.max(2e-4,M0[k]/(m.thick.rho*nf)), dx=del/(NL-1), kk=m.thick.k, rc=m.thick.rho*m.cs, a=kk/dx;
  for(let i=0;i<NL;i++){ const cap=rc*dx*((i===0||i===NL-1)?0.5:1)/dt; ta[i]=i>0?-a:0; tc[i]=i<NL-1?-a:0; tb_[i]=cap+(i>0?a:0)+(i<NL-1?a:0); td[i]=cap*TN[o+i]; }
  if(fixTs!==undefined){ ta[0]=0; tc[0]=0; tb_[0]=1; td[0]=fixTs; } else td[0]+=qin;
  for(let i=1;i<NL;i++){ const f=ta[i]/tb_[i-1]; tb_[i]-=f*tc[i-1]; td[i]-=f*td[i-1]; }
  TN[o+NL-1]=td[NL-1]/tb_[NL-1]; for(let i=NL-2;i>=0;i--) TN[o+i]=(td[i]-tc[i]*TN[o+i+1])/tb_[i];
  return [TN[o], a*(TN[o]-TN[o+1])];
}
const firstFace=k=>{ for(let d=0;d<6;d++) if((faces[k]>>d)&1) return d; return 0; };
const popc=b=>{ let c=0; while(b){ c+=b&1; b>>=1; } return c; };

function solids(dt,g){
  flameAdj.fill(0); inc.fill(0);
  for(const k of fuelList){ const b=k-SY; Lup[k]= (fst[b]===FL.FLAME && type[b]===FUEL)? Math.min(1, (Lup[b]||0)+h) : 0; }
  const gfac=Math.sqrt(Math.min(1,P.g));   // CO yield: 0 g value at g = 0, 1 g value at g ≥ 1
  for(const k of fuelList){
    const m=MAT[MKEYS[mat[k]]]; const st=fst[k];
    if(st===FL.NONE && prog[k]===0 && qx[k]===0){
      let hot=false; for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; if(T[n]>T_AMB+15||Grad[n]>E_AMB*1.15||YW[n]>1e-6){ hot=true; break; } }
      if(!hot && !nearFlame(k)) continue; }
    if(st===FL.BURNT) continue;
    let Tg=0,yo=0,yd=0,uu=0,vv=0,ww=0,c=0, nrm=[0,0,0], ru=0,rv=0,rw=0, sm=0, Gs=0, Gf=0, wet=0, pk=0, phi=0, yfA=0, yoA=0;
    for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d], nf=farGas(n,d); Tg+=T[nf]; yo=Math.max(yo,YO[nf]); yd=Math.max(yd,YD[n]); uu+=uvx[n]; vv+=uvy[n]; ww+=uvz[n];
      sm+=Math.hypot(uvx[n],uvy[n],uvz[n]); ru+=u[n]; rv+=v[n]; rw+=w[n]; c++; Gs+=Grad[n]; Gf+=Grad[nf]; wet+=(rho[n]||1)*YW[n]*V_DEP; pk+=pAbs(n); phi=Math.max(phi,YF[nf]/Math.max(1e-6,YO[nf])); yfA+=YF[n]; yoA+=YO[n];
      nrm[0]+=NB6[d][0]; nrm[1]+=NB6[d][1]; nrm[2]+=NB6[d][2]; }
    if(!c) continue;
    Tg/=c; uu/=c; vv/=c; ww/=c; Gs/=c; Gf/=c; wet/=c; pk/=c*1000;
    const X=Xvol(yo)/(1+0.6*xCO2(yd)), isItem=faces[k]===63||c>2;
    ru/=c; rv/=c; rw/=c;
    if(!isItem){ const nn=Math.hypot(...nrm)||1, nx_=nrm[0]/nn, ny_=nrm[1]/nn, nz_=nrm[2]/nn, dot=uu*nx_+vv*ny_+ww*nz_; uu-=dot*nx_; vv-=dot*ny_; ww-=dot*nz_;
      const rd=ru*nx_+rv*ny_+rw*nz_; ru-=rd*nx_; rv-=rd*ny_; rw-=rd*nz_; }
    const Ures= isItem? 100*sm/c : 100*Math.hypot(uu,vv,ww);
    const gEff= (!isItem && nrm[1]<0)? 0.1*P.g : P.g;
    const alongG= isItem || nrm[1]===0;
    const fs=flameState(m,X,Ures,pk,Tg,gEff*9.81,Lup[k]);
    const total=mA[k]+M0[k]*m.inert, qmist=wet*(LV+CPW*(373-T_AMB));
    if(wet>0) for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; YW[n]=Math.max(0,YW[n]-V_DEP*YW[n]*A*dt/V); }
    if(st===FL.FLAME){
      const early= igT[k]>=0 && t-igT[k]<4 && igns.includes(k);
      if(!fs.exists && !early){ fst[k]=FL.OUT; extMode= yd>0.05? 'co2' : pk<P.Pk*0.8? 'pressure' : X<P.X-3? 'oxygen' : fs.mode==='quench'?'quenching':'blowoff'; continue; }
      // an oxygen-starved flame (fuel piling up in the flame-zone cell) stands off the surface and heats it less
      const phiA=yfA/Math.max(1e-6,yoA), starve=1/(1+Math.max(0,phiA-1));
      const qf=qflame(m,fs.Tf)*starve;
      // external radiation from the P1 field one cell out (the own flame is in q_fl), at most 40 kW/m²
      const qext=Math.min(40e3,Math.max(0,BETA_W*(Gf-4*SIGMA*m.Tv**4)));
      if(qmist>0 && qf+qext-qmist<0.35*qf && !early){ fst[k]=FL.OUT; extMode='mist'; continue; }
      const resU=Math.min(150,100*Math.hypot(ru,rv,rw)), Usp=Math.hypot(resU, alongG? fs.UbL : 0);
      const vo=Vopp(m,fs,Tg,M0[k]), vc=Vcon(m,Object.assign({},fs,{Us:Math.max(fs.Us*(alongG?1:0),Usp)}));
      const W=[ru*100+uu*100,(rv*100+vv*100+fs.UbL*(gEff>0&&alongG?1:0)),rw*100+ww*100], Wn=Math.hypot(W[0],W[1],W[2])||1;
      let tLeft=0;
      for(let q=0;q<26;q++){ const nb=NB26[q], n=k+nb[3]; if(type[n]!==FUEL||fst[n]===FL.FLAME||fst[n]===FL.BURNT) continue;
        if(room[n]!==room[k]) continue;
        const len=nb[4], cos=(nb[0]*W[0]+nb[1]*W[1]+nb[2]*W[2])/(len*Wn);
        const mn=MAT[MKEYS[mat[n]]]; const scale=Math.min(4,(M0[k]*m.cs)/(M0[n]*mn.cs));
        const vel=(cos>=0? vo+(vc-vo)*cos*cos*cos*cos : vo)*scale;
        if(vel<=0.02) continue; const di=dt*vel/(1000*h*len); if(di>inc[n]) inc[n]=di;
        const tl=(1-prog[n])*1000*h*len/vel; if(tl>tLeft) tLeft=tl; }
      // the front must also cross this cell itself (matters at the downstream edge of an item, where no neighbour is left)
      const vf=Math.max(vo,vc); if(vf>0.02){ const ts=1000*h/vf-(t-igT[k]); if(ts>tLeft) tLeft=ts; }
      // burning rate: every exposed face burns; thick panels lose part of the heat into the solid
      let qnet=Math.max(0.05*qf,qf+qext-qmist);
      if(thickOff[k]>=0){ const [,qc]=conduct(k,dt,0,m.Tv); qnet=Math.max(0.05*qf,qnet-qc); }
      // every exposed face burns; an electrical overheat heats the item once (from the conductor), not per face
      const rate=(c*qnet+qx[k])/m.Lg, m0c=M0[k]*(1-m.inert), tb=m0c/rate;
      const mdot=Math.min(rate, mA[k]/(Math.min(tb,mA[k]/rate)+Math.min(tLeft,900)));
      const dm=Math.min(mA[k],mdot*dt); mA[k]-=dm;
      // under-ventilated burning raises the CO yield toward ~0.2 (Gottuk & Lattimer); the compartment-mean O₂ stands in for the
      // global equivalence ratio (the flame sheet itself is always locally fuel-rich)
      const Cm=comps[comp[k+OFF6[firstFace(k)]]], xr=Cm&&Cm.yo!==undefined? Cm.yo/Math.max(1e-6,Y0()) : 1;
      const ycoG=m.yco0+(m.yco-m.yco0)*gfac, Sphi=Math.min(1,Math.max(0,(0.85-xr)/0.4)), yco=ycoG+(0.2-ycoG)*Sphi;
      // soot yield: 0 g value at g = 0; laminar diffusion flames make soot roughly ∝ P (P¹–P²) below one atmosphere
      const dmf=wf[k]*dm*A/c, ysG=(m.ys0+(m.ys-m.ys0)*gfac)*Math.min(1.5,pk/101.3);
      for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; const r=rho[n]||1, iv=dmf/(r*V);
        YF[n]+=iv*m.s; YS[n]+=iv*ysG; YC[n]+=iv*yco; YN[n]+=iv*m.yhcn; YH[n]+=iv*m.yhf*0.2; flameAdj[n]=1; }
      Ts[k]=m.Tv;
      if(mA[k]<=1e-3*M0[k]){ fst[k]=FL.BURNT; continue; }
    } else {
      // surface energy balance: convection + radiation (P1 field, Marshak) + overheat − mist cooling
      const qin=H_CONV*(Tg-Ts[k]) + BETA_W*(Gs-4*SIGMA*Ts[k]**4) + qx[k] - qmist;
      let pyro=false, qpy=0; const o=thickOff[k];
      if(o>=0){ if(TN[o]>=m.Tv-0.01){ const [,qc]=conduct(k,dt,0,m.Tv); qpy=Math.max(0,qin-qc); Ts[k]=m.Tv; pyro=qin>qc; if(!pyro){ Ts[k]=conduct(k,dt,qin)[0]; } }
        else { Ts[k]=conduct(k,dt,qin)[0]; if(Ts[k]>=m.Tv){ Ts[k]=m.Tv; TN[o]=m.Tv; pyro=true; } } }
      else { Ts[k]+=qin*dt/(total*m.cs); if(Ts[k]>=m.Tv){ pyro=true; qpy=Math.max(0,qin); } }
      if(Ts[k]<T_AMB-30) Ts[k]=T_AMB-30;
      if(pyro){
        const dm=Math.min(mA[k],c*qpy/m.Lg*dt); mA[k]-=dm; Ts[k]=m.Tv;
        const dmf=wf[k]*dm*A/c;
        for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; const r=rho[n]||1, iv=dmf/(r*V);
          YF[n]+=iv*m.s; YS[n]+=iv*Math.max(0.02,m.ys*1.5); YC[n]+=iv*0.05; YN[n]+=iv*m.yhcn*0.5; YH[n]+=iv*m.yhf; }
        if(fs.exists && qmist<=0 && (Tg>T_AIT-150 || prog[k]>0.3 || qx[k]>=30e3)){ fst[k]=FL.FLAME; igT[k]=t; noteIgn(k,'hot gas'); }
        if(mA[k]<=1e-4*M0[k]) fst[k]=FL.BURNT;
      } else if(st===FL.NONE && Ts[k]>T_AMB+30) fst[k]=FL.HEAT;
    }
  }
  for(const k of fuelList){ if(inc[k]<=0||fst[k]===FL.FLAME||fst[k]===FL.BURNT) continue;
    prog[k]+=inc[k]; if(fst[k]===FL.NONE) fst[k]=FL.HEAT;
    if(prog[k]>=1){ const m=MAT[MKEYS[mat[k]]];
      let Tg=0,yo=0,yd=0,c=0,pk=0,wet=0,sm=0; for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n0=k+OFF6[d], n=farGas(n0,d); Tg+=T[n]; yo=Math.max(yo,YO[n]); yd=Math.max(yd,YD[n0]); pk+=pAbs(n0); wet+=YW[n0]; sm+=Math.hypot(uvx[n0],uvy[n0],uvz[n0]); c++; } Tg/=c||1; pk/=(c||1)*1000;
      // the new flame must be able to exist in the same local ventilation flow the existence test uses
      const fs=flameState(m,Xvol(yo)/(1+0.6*xCO2(yd)),100*sm/(c||1),pk,Tg,P.g*9.81,0);
      if(fs.exists && wet<1e-4){ fst[k]=FL.FLAME; igT[k]=t; Ts[k]=m.Tv; if(thickOff[k]>=0) TN[thickOff[k]]=m.Tv; noteIgn(k,'spread'); } else prog[k]=0.95; } }
}
function farGas(n,d){ const f=n+OFF6[d]; return (f>=0&&f<N&&type[f]===GAS)? f : n; }
function nearFlame(k){ for(let q=0;q<26;q++){ const n=k+NB26[q][3]; if(fst[n]===FL.FLAME&&type[n]===FUEL) return true; } return false; }
function noteIgn(k,how){ if(firstIgn<0) firstIgn=k; }

// ---------------- suppression: extinguishers, water-mist evaporation, vent to vacuum ----------------
// CO₂ portable extinguisher: ~2.7 kg discharged over 45 s (representative of the ISS US-segment PFE; it must halve the O₂ in a
// rack within 60 s, NTRS 20050215297). Fine water mist PFE: ~2 kg of water over 50 s (representative, NTRS 20130011664).
const AGENTS={co2:{name:'CO₂ extinguisher', mass:2.7, dur:45}, mist:{name:'Water-mist extinguisher', mass:2.0, dur:50}};
function sprayCells(ii){ const it=ITEMS[ii], ri=ROOMS.findIndex(r=>r.id===it.room); const cs=it.cells.length? it.cells : [];
  let sx=0,sy=0,sz=0; for(const k of cs){ sx+=cx(gi[k]); sy+=cy(gj[k]); sz+=cz(gl[k]); } const n=cs.length||1, c=[sx/n,sy/n,sz/n];
  for(const R of [0.6,0.9,1.3]){ const out=[]; for(let q=0;q<gasList.length;q++){ const k=gasList[q]; if(room[k]!==ri) continue;
    if(Math.hypot(cx(gi[k])-c[0],cy(gj[k])-c[1],cz(gl[k])-c[2])<=R) out.push(k); } if(out.length>=6||R===1.3) return out; } return []; }
function suppression(dt){
  for(const s of sprays){ if(t>=s.t0+s.dur||!s.cells.length) continue;
    const dmc=s.mass/s.dur*dt/s.cells.length;
    for(const k of s.cells){ const r=rho[k], m=r*V;
      if(s.kind==='co2'){ const f=dmc/(m+dmc); for(const F of SC) if(F!==YD&&F!==YW) F[k]*=1-f; YD[k]=YD[k]*(1-f)+f;
        const cool=dmc*(571e3+840*(T[k]-195)); T[k]-=cool/((m+dmc)*CP); Dx[k]+=dmc/(m*dt)-cool/(m*CP*T[k]*dt);
        const C=comps[comp[k]]; if(C&&!C.outlet) C.pbg+=pAbs(k)*dmc/(C.vol*r); }
      else { YW[k]+=dmc/m; Dx[k]+=0.2*dmc/(m*dt); } } }
  // water-mist droplets evaporate on heat that is available above ambient; the vapour dilutes O₂ and the gas cools
  let any=false; for(const s of sprays) if(s.kind==='mist') any=true;
  if(any) for(let q=0;q<gasList.length;q++){ const k=gasList[q]; const yw=YW[k]; if(yw<=1e-8) continue;
    const r=rho[k], m=r*V, Tk=T[k];
    const avail=Math.max(0,Tk-T_AMB+3)*m*CP, need=LV+CPW*Math.max(0,Math.min(373,Tk)-T_AMB);
    const dme=Math.min(yw*m, avail/need*(1-Math.exp(-dt/0.25)) + yw*m*dt/600);
    if(dme<=0) continue; YW[k]-=dme/m; const f=dme/(m+dme); YO[k]*=1-f; YF[k]*=1-f;
    const cool=dme*need; T[k]-=cool/(m*CP); Dx[k]+=dme*1.6/(m*dt)-cool/(m*CP*T[k]*dt); }
  // venting: the whole compartment expands as its pressure falls, and the gas leaves through the valve cells
  for(const vl of VALVES){ if(!vl.active||!vl.cells.length) continue; const c=comp[vl.cells[0]]; if(c<0) continue; const C=comps[c];
    const tau=C.vol/(CD_VALVE*valveArea(c)*199), rate=1/tau;
    for(let q=0;q<gasList.length;q++){ const k=gasList[q]; if(comp[k]===c) Dx[k]+=rate; }
    const frac=vl.area/valveArea(c); for(const k of vl.cells) Dx[k]-=rate*C.vol*frac/(vl.cells.length*V); }
}

// ---------------- crew: movement to a safe haven and fractional effective dose (Purser / ISO 13571) ----------------
let alarmT=-1, crewMasks=-1, alerted=-1;
function initCrew(){ crew=(LYT.CREW||[]).map(c=>({id:c.id,name:c.name,room:c.room,pos:c.pos.slice(),asleep:!!c.asleep,
  state:'normal',react:-1,path:[],goal:null,fed:0,fedCO:0,fedCN:0,fedO:0,fedHeat:0,fec:0,mask:-1,safeAt:null,blocked:false,why:'',spd:0}));
  alarmT=-1; crewMasks=-1; alerted=-1; fireMem=-1; }
const ri_=id=>ROOMS.findIndex(r=>r.id===id);
function cellAt(x,y,z){ let k=id(ci(x),cj(y),ck(z)); if(type[k]===GAS) return k; for(const o of OFF6){ if(type[k+o]===GAS) return k+o; } for(const nb of NB26){ if(type[k+nb[3]]===GAS) return k+nb[3]; } return -1; }
function route(from,to){ // BFS over compartments through walkable openings that are open
  const G=LYT.GRAPH||[], prev={[from]:null}, q=[from];
  while(q.length){ const a=q.shift(); if(a===to) break;
    for(const [x,y,oid] of G){ const b= x===a? y : y===a? x : null; if(b===null||b in prev) continue; const o=OPEN.find(o=>o.id===oid); prev[b]={a,o}; q.push(b); } }
  if(!(to in prev)) return null; const steps=[]; let c=to; while(prev[c]){ steps.unshift({room:c,via:prev[c].o}); c=prev[c].a; } return steps; }
// the compartment the crew treat as the fire location: where flames are now, otherwise where they last were (or the smokiest at alarm)
let fireMem=-1;
function fireRoom(){ const st=roomFire(); let best=-1,bv=0; st.forEach((v_,i)=>{ if(v_>bv){bv=v_;best=i;} });
  const flames=st.some(x=>x>=10); if(flames||fireMem<0) fireMem= best>=0? best : fireMem; return fireMem; }
function roomFire(){ const r=ROOMS.map(()=>0); for(const k of fuelList) if(fst[k]===FL.FLAME&&room[k]>=0) r[room[k]]+=10;
  if(!r.some(x=>x>0) && lastStats) lastStats.forEach((s,i)=>{ r[i]=s.ext; }); return r; }
const MAIN={rack:'lab',cqp:'node',cqs:'node'};
function pickHaven(fr){ const H=LYT.havens||[]; if(!H.length) return null; const f=ROOMS[fr]? (MAIN[ROOMS[fr].id]||ROOMS[fr].id) : null;
  const order= f==='lab'? ['node','air'] : f==='air'? ['lab','node'] : ['lab','air']; for(const o of order) if(H.includes(o)) return o; return H[0]; }
let lastStats=null;
function updateCrew(dt){
  if(!crew.length) return;
  if(alarmT<0){ const st=lastStats; let fireSeen=false; for(const k of fuelList) if(fst[k]===FL.FLAME){ fireSeen=true; break; }
    if((st&&st.some(r=>r.ext>=0.1))||fireSeen) alarmT=t; }
  const fr=fireRoom();
  for(const c of crew){
    if(crewMasks>=0 && c.mask<0 && c.state!=='incapacitated') c.mask=Math.max(crewMasks,t);
    const k=cellAt(...c.pos); if(k<0) continue;
    const r=rho[k]||1.2, Pk=pAbs(k)/1000, Tc=T[k]-273.15;
    // dose rates per minute
    const masked= c.mask>=0 && t-c.mask>=30 && t-c.mask<900+30;
    const co=ppm(YC[k],28)*Pk/101.3, cn=ppm(YN[k],27)*Pk/101.3, hf=ppm(YH[k],20)*Pk/101.3;
    const dO=Math.max(0,Y0()*(1-YD[k])-YO[k]), co2=100*xCO2(YD[k]+dO*1.375*0.9)*Pk/101.3, o2eq=Xvol(YO[k])*Pk/101.3;
    const vco2= co2>2? Math.exp(co2/5) : 1;
    const rCO= masked?0: 2.764e-5*Math.pow(co,1.036), rCN= masked?0: Math.max(0,Math.exp(cn/43)/220-0.0045), rO= masked?0: (o2eq<20.9? 1/Math.exp(8.13-0.54*(20.9-o2eq)) : 0);
    const rH= Tc>45? 1/(5e7*Math.pow(Tc,-3.4)) : 0, qrad=Math.max(0,(Grad[k]/4-SIGMA*T_AMB**4)/1000), rR= qrad>1.7? Math.pow(qrad,1.56)/6.9 : 0;
    const dm=dt/60;
    c.fedCO+=rCO*vco2*dm; c.fedCN+=rCN*vco2*dm; c.fedO+=rO*dm; c.fedHeat+=(rH+rR)*dm;
    c.fed=c.fedCO+c.fedCN+c.fedO+c.fedHeat; c.fec= masked?0: hf/500;
    c.now={co:+co.toFixed(0),cn:+cn.toFixed(1),hf:+hf.toFixed(1),co2:+co2.toFixed(2),o2:+o2eq.toFixed(1),T:+Tc.toFixed(0),vis:+(Math.min(99,3/Math.max(1e-4,SOOT_EXT*r*YS[k]))).toFixed(1),masked};
    if(c.fed>=1){ c.state='incapacitated'; c.why= c.fedO>=c.fedCO+c.fedCN&&c.fedO>c.fedHeat? 'hypoxia' : c.fedHeat>c.fedCO+c.fedCN? 'heat' : 'toxic gases'; continue; }
    if(c.state==='normal'&&alarmT>=0){ const delay=(c.asleep?60:15)*(alerted>=0?0.5:1); if(c.react<0) c.react=Math.max(alarmT,alerted>=0?alerted:alarmT)+delay; if(t>=c.react) c.state='moving'; }
    if(c.state==='moving'||c.state==='blocked'){
      if(!c.goal || (t%10<dt)){ const hv=pickHaven(fr); if(hv&&hv!==c.goal){ c.goal=hv; c.path=null; } }
      if(c.goal && c.room===c.goal && !c.path?.length){ const tgt=ROOMS[ri_(c.goal)].c; const d=Math.hypot(tgt[0]-c.pos[0],tgt[1]-c.pos[1],tgt[2]-c.pos[2]); if(d<0.3){ c.state='safe'; if(c.safeAt===null) c.safeAt=t; continue; } c.path=[{room:c.goal,target:tgt}]; }
      if(!c.path||!c.path.length){ const rt=route(c.room,c.goal); if(!rt){ c.state='blocked'; c.blocked=true; continue; }
        c.path=[]; for(const s of rt){ c.path.push({room:null,target:s.via.c,via:s.via}); c.path.push({room:s.room,target:ROOMS[ri_(s.room)].c}); } }
      const wp=c.path[0];
      if(wp.via && !wp.via.open){ c.state='blocked'; c.blocked=true; continue; } else if(c.state==='blocked') c.state='moving';
      const vis=Math.min(99,3/Math.max(1e-4,SOOT_EXT*r*YS[k])), sp=(P.g>0.05?0.6:0.4)*Math.min(1,Math.max(0.3,vis/5))*(c.fed>0.3?0.5:1); c.spd=sp;
      const dx_=wp.target[0]-c.pos[0], dy_=wp.target[1]-c.pos[1], dz_=wp.target[2]-c.pos[2], d=Math.hypot(dx_,dy_,dz_);
      if(d<=sp*dt){ c.pos=wp.target.slice(); if(wp.room) c.room=wp.room; c.path.shift(); }
      else { c.pos[0]+=dx_/d*sp*dt; c.pos[1]+=dy_/d*sp*dt; c.pos[2]+=dz_/d*sp*dt; }
    }
    if(c.state==='safe' && fr>=0 && (MAIN[ROOMS[fr].id]||ROOMS[fr].id)===c.room){ c.state='moving'; c.goal=null; c.path=null; }
  }
}

// ---------------- API ----------------
function ignite(k){ if(type[k]!==FUEL||fst[k]===FL.FLAME||fst[k]===FL.BURNT) return false;
  fst[k]=FL.FLAME; igT[k]=t; Ts[k]=MAT[MKEYS[mat[k]]].Tv; if(thickOff[k]>=0) TN[thickOff[k]]=Ts[k]; igns.push(k); if(firstIgn<0) firstIgn=k; return true; }
function toggleOpening(oi){ const o=OPEN[oi]; o.open=!o.open; for(const k of o.cells){ type[k]=o.open?GAS:WALL; if(!o.open){u[k]=v[k]=w[k]=0;} else { T[k]=T_AMB; YO[k]=Y0(); for(const F of SC) if(F!==YO) F[k]=0; Grad[k]=E_AMB; } } buildComps(); ventFlow(); return o.open; }
function igniteItem(ii,mode){ const it=ITEMS[ii]; const cs=it.cells.filter(k=>type[k]===FUEL&&fst[k]!==FL.BURNT); if(!cs.length) return false;
  if(mode==='flame') return ignite(cs[Math.floor(cs.length/2)]);
  const q= mode==='severe'? 40e3 : 15e3; for(const k of cs) qx[k]=Math.max(qx[k],q); if(firstIgn<0) firstIgn=cs[0]; return true; }
function stopOverheat(){ qx.fill(0); }
function setItemMaterial(ii,mk){ if(!MAT[mk]) return; ITEMS[ii].m=mk; reset(); }
function setDepress(rid,on){ const vl=VALVES.find(v_=>v_.room===rid); if(!vl) return false; vl.active=!!on; buildComps(); return vl.active; }
function discharge(kind,ii){ if(!AGENTS[kind]||!ITEMS[ii]) return false; const cells=sprayCells(ii); if(!cells.length) return false;
  sprays.push({kind,item:ii,cells,t0:t,dur:AGENTS[kind].dur,mass:AGENTS[kind].mass}); return true; }
// command dispatcher (UI actions and scenario scripts). Every action is logged with its time so a run can be saved and replayed.
function command(c,fromScript){
  let ok=true;
  switch(c.do){
    case 'igniteItem': ok=igniteItem(c.i,c.mode||'flame'); break;
    case 'ignite': ok=ignite(c.k); break;
    case 'power': stopOverheat(); break;
    case 'fans': setParams({vent:!!c.on}); break;
    case 'opening': { const oi=OPEN.findIndex(o=>o.id===c.id); if(oi>=0&&OPEN[oi].open!==!!c.open) toggleOpening(oi); else ok=oi>=0; break; }
    case 'co2': case 'mist': ok=discharge(c.do,c.i); break;
    case 'depress': ok=setDepress(c.room,c.on!==false); break;
    case 'masks': if(crewMasks<0) crewMasks=t; break;
    case 'alert': if(alerted<0) alerted=t; if(alarmT<0) alarmT=t; break;
    case 'set': setParams(c.params||{}); break;
    default: ok=false;
  }
  if(ok) actions.push(Object.assign({},c,{t:+t.toFixed(2)}));
  return ok;
}
function setScript(list){ script=(list||[]).slice().sort((a,b)=>a.t-b.t); scriptPos=0; while(scriptPos<script.length&&script[scriptPos].t<t) scriptPos++; }
function localFlow(it){ let sm=0,c=0; for(const k of it.cells) for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; sm+=Math.hypot(uvx[n],uvy[n],uvz[n]); c++; } return c? 100*sm/c : 0; }
function assess(){ return ITEMS.map((it,ii)=>{ const m=MAT[it.m], U=localFlow(it), g=P.g*9.81;
  const fs=flameState(m,P.X,U,P.Pk,T_AMB,g,0), lim=limitX(m,U,P.Pk,'con',g);
  const nf=flameState(m,P.X,0.3,P.Pk,T_AMB,g,0);
  return {i:ii, U:+U.toFixed(1), exists:fs.exists, mode:fs.mode, Tf:Math.round(fs.Tf), lim:lim===null?null:+lim.toFixed(1), vo:+Vopp(m,fs,T_AMB,it.m0||m.m0).toFixed(2), vc:+Vcon(m,fs).toFixed(2), noflow:nf.exists, thick:!!m.thick}; }); }
function matTable(){ const g=P.g*9.81; return MKEYS.map(k=>{ const m=MAT[k]; const c=curves(k,P.Pk).con.filter(x=>x!==null); const best=c.length?Math.min(...c):null;
  const fs10=flameState(m,P.X,10,P.Pk,T_AMB,g,0), fs20=flameState(m,P.X,20,P.Pk,T_AMB,g,0);
  return {k, name:m.name, loi:m.loi??null, test1:m.test1??null, best0g:best===null?null:+best.toFixed(1), burns10:fs10.exists, lim10:(x=>x===null?null:+x.toFixed(1))(limitX(m,10,P.Pk,'con',g)), vcon20:+Vcon(m,fs20).toFixed(2), vopp:+Vopp(m,fs10,T_AMB,m.m0).toFixed(2), ys:m.ys, yco:+(m.yco0+(m.yco-m.yco0)*Math.sqrt(Math.min(1,P.g))).toFixed(3), yhcn:m.yhcn, yhf:m.yhf, thick:!!m.thick, refs:REFS[k]||[], src:m.src}; }); }
function setParams(q){ const flow=(q.U!==undefined&&q.U!==P.U)||(q.vent!==undefined&&q.vent!==P.vent); Object.assign(P,q); if(flow) ventFlow(); }
function stats(){
  const r=ROOMS.map(()=>({flame:0,burnt:0,heat:0,Tmax:T_AMB,Xmin:100,soot:0,sootN:0,rs:0,rn:0,sm:0,hrr:0,pbg:0,vis:99,co:0,coMean:0,hcn:0,hf:0,co2:0,agent:0,mist:0,Pk:P.Pk,n:0,qrad:0}));
  for(let k=0;k<N;k++){ const ri=room[k]; if(ri<0) continue; const R_=r[ri];
    if(type[k]===GAS){ if(T[k]>R_.Tmax)R_.Tmax=T[k]; const x=Xvol(YO[k]); if(x<R_.Xmin)R_.Xmin=x; R_.hrr+=hrr[k];
      const c=comp[k]; if(comps[c]){ R_.pbg=Math.max(R_.pbg,comps[c].pbg); R_.Pk=(P.Pk*1000*comps[c].pf+comps[c].pbg)/1000; }
      const co=ppm(YC[k],28); if(co>R_.co) R_.co=co; R_.coMean+=co; R_.n++;
      const cn=ppm(YN[k],27); if(cn>R_.hcn) R_.hcn=cn; const hf=ppm(YH[k],20); if(hf>R_.hf) R_.hf=hf;
      const dO=Math.max(0,Y0()*(1-YD[k])-YO[k]), co2=100*xCO2(YD[k]+dO*1.375*0.9); if(co2>R_.co2) R_.co2=co2; const ag=100*xCO2(YD[k]); if(ag>R_.agent) R_.agent=ag;
      if(YW[k]>R_.mist) R_.mist=YW[k]; const qr=Grad[k]/4-SIGMA*T_AMB**4; if(qr>R_.qrad) R_.qrad=qr;
      if(cy(gj[k])>=ROOMS[ri].ytop-0.3){ R_.soot+=SOOT_EXT*rho[k]*YS[k]; R_.sootN++; }
      if(ret[k]){ R_.rs+=SOOT_EXT*rho[k]*YS[k]; R_.rn++; } R_.sm+=SOOT_EXT*rho[k]*YS[k]; }
    else if(type[k]===FUEL){ const s=fst[k]; if(s===FL.FLAME) R_.flame++; else if(s===FL.BURNT||s===FL.OUT) R_.burnt++; else if(s===FL.HEAT) R_.heat++; } }
  // smoke detectors: overhead band and (on the ISS) in the ventilation return; visibility from the room-mean extinction
  for(const R_ of r){ const K=R_.sootN? R_.soot/R_.sootN : 0, Kr=R_.rn? R_.rs/R_.rn : 0, Km=R_.n? R_.sm/R_.n : 0; R_.ext=Math.max(K,Kr); R_.vis= Math.max(K,Km)>1e-4? Math.min(99,3/Math.max(K,Km)) : 99;
    R_.Xmin=Math.min(R_.Xmin,P.X); R_.coMean=R_.n?R_.coMean/R_.n:0; for(const x of ['soot','sootN','rs','rn','sm']) delete R_[x]; }
  lastStats=r; return r;
}
function probeAt(x,y,z){ const k=cellAt(x,y,z); if(k<0) return null; const r=rho[k]||1.2;
  return {T:T[k], aerosol:r*YS[k]*1e6, co:ppm(YC[k],28), X:Xvol(YO[k]), G:Grad[k]}; }
function mean(f,pred){ let s=0,n=0; for(let q=0;q<gasList.length;q++){ const k=gasList[q]; if(pred&&!pred(k)) continue; s+=f(k); n++; } return n?s/n:0; }
function crewOut(){ return crew.map(c=>({id:c.id,name:c.name,room:c.room,pos:c.pos.map(x=>+x.toFixed(2)),state:c.state,fed:+c.fed.toFixed(3),fedCO:+c.fedCO.toFixed(3),fedCN:+c.fedCN.toFixed(3),fedO:+c.fedO.toFixed(3),fedHeat:+c.fedHeat.toFixed(3),fec:+c.fec.toFixed(2),why:c.why,safeAt:c.safeAt,blocked:c.blocked,asleep:c.asleep,goal:c.goal,mask:c.mask>=0,now:c.now||null})); }
function warmup(){ const ig=igns; igns=[]; for(let i=0;i<30;i++) step(0.25); t=0; igns=ig; initCrew(); actions=[]; }
reset();
return {
  info:{nx,ny,nz,N,h,NXi,NYi,NZi,LX,LY,LZ,SY,SZ,DIM,AXY,AXZ,layout:cfg.layout||'ship',name:LYT.name}, MAT, MKEYS, ROOMS, OPEN, ITEMS, VALVES, AGENTS, P, FL, LYT,
  type, room, openId, sup, ret, mat, faces, fst, prog, igT, Ts, mA, T, YO, YF, YS, YC, YN, YH, YD, YW, G:Grad, u, v, w, hrr,
  get t(){return t;}, get lastDt(){return lastDt;}, get fuelList(){return fuelList;}, get firstIgn(){return firstIgn;}, get extMode(){return extMode;}, get igns(){return igns;},
  get actions(){return actions;}, get sprays(){return sprays.map(s=>({kind:s.kind,item:s.item,t0:s.t0,dur:s.dur,active:t<s.t0+s.dur}));}, get alarmT(){return alarmT;},
  step, reset, ignite, toggleOpening, setParams, stats, id, Xvol, igniteItem, stopOverheat, setItemMaterial, assess, matTable, sclass, itemOf, supDx, supDy, supDz, VENTS, qx,
  command, setScript, setDepress, discharge, crew:crewOut, probeAt, mean, ppm, cellAt,
  roomPk:()=>ROOMS.map((r,i)=>P.Pk*roomPf[i]+roomPbg[i]/1000),
  model:{flameState, Vopp, Vcon, Tflame, Ubo, Ubuoy, KAPPA, T_AMB, TF_REF, LB}, curves, loiVsG, validate, limitX,
};
}
if(typeof module!=='undefined') module.exports={createSolver};
