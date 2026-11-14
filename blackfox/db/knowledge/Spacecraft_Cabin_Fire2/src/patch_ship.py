# Turns the shared habitat solver (copied from fire_sim_2d) into the spacecraft solver:
# cylindrical modules, spacecraft materials, directional vents, electrical overheat and per-location assessment.
import pathlib
p = pathlib.Path(__file__).parent / "solver.js"
s = p.read_text(encoding="utf-8")

def rep(a, b, n=1):
    global s
    c = s.count(a)
    assert c == n, (c, a[:100])
    s = s.replace(a, b)

def cut(start, end, new):
    global s
    i = s.index(start); j = s.index(end, i)
    s = s[:i] + new + s[j:]

rep("// Habitat fire solver v4 (2D edition) — variable-density LES-style fire model of a two-deck habitat.",
    "// Spacecraft cabin fire solver (v4 physics) — 3D variable-density LES-style fire model of a crewed spacecraft:\n// US-Lab-style module with rack ring and central aisle, a node with crew quarters and galley, and an airlock.")

# ---------------- spacecraft materials ----------------
rep("""    src:{quench:'ASSUMED: 0 g limits up to 4% O₂ below 1 g (ntrs-20080034883)', boOpp:'ASSUMED: 1 g LOI ~28–29%', boCon:'assumed'}},
};""", """    src:{quench:'ASSUMED: 0 g limits up to 4% O₂ below 1 g (ntrs-20080034883)', boOpp:'ASSUMED: 1 g LOI ~28–29%', boCon:'assumed'}},
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
  pc:['ntrs-20205004657'], pu:['ntrs-20140006585','ntrs-20040084186'], nylon:['ntrs-19870010085','ntrs-20230004106'], cotton:['ntrs-20140006585','ntrs-20260001992']};""")

# ---------------- spacecraft grid and geometry ----------------
cut("// ---------------- grid ----------------", "// ---------------- state ----------------", r'''// ---------------- grid: spacecraft (Lab module – Node with crew quarters – Airlock) ----------------
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
    x:[1.5,1.8], y:[1.5,2.7], z:[3.5,3.65], note:'Overheated wiring is the most likely spacecraft fire source.'},
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
    x:[1.8,4.2], y:[3.15,3.3], z:[2.85,3.15]},
  {id:'N1', name:'Sleeping bag', where:'Node · port crew quarters', room:'cqp', m:'nomex', opts:['nomex','cotton','sibal'],
    x:[7.15,8.05], y:[1.3,2.9], z:[0.6,0.75]},
  {id:'N2', name:'Crew clothing', where:'Node · starboard crew quarters', room:'cqs', m:'cotton', opts:['cotton','nomex'],
    x:[7.2,7.9], y:[1.3,2.2], z:[3.45,3.6]},
  {id:'N3', name:'Velcro strips', where:'Node · forward bulkhead', room:'node', m:'nylon', opts:['nylon','nomex'], onWall:true,
    x:[9.5,9.65], y:[2.7,3.1], z:[1.2,3.0]},
  {id:'N4', name:'Galley food packaging', where:'Node · on the galley table', room:'node', m:'paper', opts:['paper','pe'],
    x:[8.5,9.0], y:[1.15,1.4], z:[1.8,2.4]},
  {id:'N5', name:'Closeout curtain', where:'Node · port wall, aft of the hatch', room:'node', m:'sibal', opts:['sibal','nomex','cotton'],
    x:[8.4,9.3], y:[2.2,3.3], z:[0.85,1.0]},
  {id:'A1', name:'EVA suit outer layer', where:'Airlock', room:'air', m:'nomex', opts:['nomex','sibal','cotton'],
    x:[10.3,10.8], y:[1.4,2.8], z:[1.8,2.4]},
  {id:'A2', name:'Hatch seal', where:'Airlock · around the hatch', room:'air', m:'silicone', opts:['silicone','nylon'], onWall:true,
    test:(x,y,z)=>x>=9.5&&x<9.65&&Math.max(Math.abs(y-AXY),Math.abs(z-AXZ))>=0.5&&Math.max(Math.abs(y-AXY),Math.abs(z-AXZ))<0.65},
];

''')
rep("const P={g:cfg.g??0.165, X:cfg.X??34, Pk:cfg.Pk??56.5, U:cfg.U??10, vent:cfg.vent??true, lining:cfg.lining||'sibal'};",
    "const P={g:cfg.g??0, X:cfg.X??21, Pk:cfg.Pk??101.3, U:cfg.U??20, vent:cfg.vent??true, lining:cfg.lining||'sibal'};\nconst qx=new Float64Array(N);   // imposed heat flux on a surface (electrical overheat), W/m²")

# ---------------- build ----------------
cut("function inside(b,i,j,l){", "function buildComps(){", r'''function build(){
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
      type[k]=FUEL; mat[k]=mi; faces[k]=63; itemOf[k]=ii; room[k]=ri; it.cells.push(k); }); });
  fuelList=[]; for(let k=0;k<N;k++) if(type[k]===FUEL){
    let f=0; for(let d=0;d<6;d++) if((faces[k]>>d)&1 && type[k+OFF6[d]]===GAS) f|=1<<d; faces[k]=f;
    if(f) fuelList.push(k); else { type[k]=WALL; mat[k]=-1; itemOf[k]=-1; } }
  for(const it of ITEMS) it.cells=it.cells.filter(k=>type[k]===FUEL);
  ROOMS.forEach((r,ri)=>{ let top=0; C((k,x,y,z)=>{ if(type[k]===GAS&&room[k]===ri&&y>top) top=y; }); r.ytop=top; });
  buildComps();
}
''')
rep("const wf=new Float64Array(N).fill(1);", "const wf=new Float64Array(N).fill(1);")

# ---------------- directional vents ----------------
cut("function velBC(){", "const sumC=[]", r'''function velBC(){
  const uin=P.vent?P.U/100:0;
  for(let q=0;q<solidList.length;q++){ const k=solidList[q]; u[k]=0;v[k]=0;w[k]=0; }
  for(let q=0;q<gasList.length;q++){ const k=gasList[q]; if(sup[k]){ const s=uin*supSp[k]; u[k]=s*supDx[k]; v[k]=s*supDy[k]; w[k]=s*supDz[k]; } }
}
''')
rep("    if(sup[k]&&ventOn) div-=P.U/100*ih;          // inflow through the supply face",
    "    if(sup[k]&&ventOn) div-=P.U/100*supSp[k]*ih;  // inflow through the diffuser face")

# ---------------- electrical overheat ----------------
rep("      const Tl=Math.min(Tg,1100), qext=Math.max(0,epsLayer(ksoot)*SIGMA*(Tl**4-m.Tv**4));",
    "      const Tl=Math.min(Tg,1100), qext=Math.max(0,epsLayer(ksoot)*SIGMA*(Tl**4-m.Tv**4))+qx[k];")
rep("      const qin=H_CONV*(Tg-Ts[k])+ epsg*SIGMA*(Tg**4-Ts[k]**4) + qn - 0.9*SIGMA*(Ts[k]**4-T_AMB**4);",
    "      const qin=H_CONV*(Tg-Ts[k])+ epsg*SIGMA*(Tg**4-Ts[k]**4) + qn + qx[k] - 0.9*SIGMA*(Ts[k]**4-T_AMB**4);")
rep("        for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; YF[n]+=wf[k]*dm*A*m.s/((rho[n]||1)*V); }\n        if(fs.exists && (Tg>T_AIT-150 || prog[k]>0.3)){",
    "        // pyrolysis without flame: unburnt fuel vapour plus dense smoke (smouldering / overheated insulation)\n        for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; const r=rho[n]||1; YF[n]+=wf[k]*dm*A*m.s/(r*V); YS[n]+=wf[k]*dm*A*Math.max(0.02,m.ys*1.5)/(r*V); }\n        // a severe overheat (≥ 30 kW/m²) acts as a hot-surface pilot\n        if(fs.exists && (Tg>T_AIT-150 || prog[k]>0.3 || qx[k]>=30e3)){")

# ---------------- detectors, API ----------------
rep("const j=Math.floor(k/nx)%ny; if(cy(j)>=ROOMS[ri].y1-0.25){", "const j=Math.floor(k/nx)%ny; if(cy(j)>=ROOMS[ri].ytop-0.3){")
rep("function setParams(q){",
r'''function igniteItem(ii,mode){ const it=ITEMS[ii]; const cs=it.cells.filter(k=>type[k]===FUEL&&fst[k]!==FL.BURNT); if(!cs.length) return false;
  if(mode==='flame') return ignite(cs[Math.floor(cs.length/2)]);
  const q= mode==='severe'? 40e3 : 15e3; for(const k of cs) qx[k]=Math.max(qx[k],q); if(firstIgn<0) firstIgn=cs[0]; return true; }
function stopOverheat(){ qx.fill(0); }
function setItemMaterial(ii,mk){ if(!MAT[mk]) return; ITEMS[ii].m=mk; reset(); }
function localFlow(it){ let uu=0,vv=0,ww=0,c=0; for(const k of it.cells) for(let d=0;d<6;d++) if((faces[k]>>d)&1){ const n=k+OFF6[d]; uu+=uvx[n]; vv+=uvy[n]; ww+=uvz[n]; c++; } return c? 100*Math.hypot(uu/c,vv/c,ww/c) : 0; }
function assess(){ return ITEMS.map((it,ii)=>{ const m=MAT[it.m], U=localFlow(it), g=P.g*9.81;
  const fs=flameState(m,P.X,U,P.Pk,T_AMB,g,0), lim=limitX(m,U,P.Pk,'con',g);
  return {i:ii, U:+U.toFixed(1), exists:fs.exists, mode:fs.mode, Tf:Math.round(fs.Tf), lim:lim===null?null:+lim.toFixed(1), vo:+Vopp(m,fs,T_AMB,m.m0).toFixed(2), vc:+Vcon(m,fs).toFixed(2)}; }); }
function matTable(){ const g=P.g*9.81; return MKEYS.map(k=>{ const m=MAT[k]; const c=curves(k,P.Pk).con.filter(x=>x!==null); const best=c.length?Math.min(...c):null;
  const fs10=flameState(m,P.X,10,P.Pk,T_AMB,g,0), fs20=flameState(m,P.X,20,P.Pk,T_AMB,g,0);
  return {k, name:m.name, loi:m.loi??null, best0g:best===null?null:+best.toFixed(1), burns10:fs10.exists, lim10:(x=>x===null?null:+x.toFixed(1))(limitX(m,10,P.Pk,'con',g)), vcon20:+Vcon(m,fs20).toFixed(2), vopp:+Vopp(m,fs10,T_AMB,m.m0).toFixed(2), ys:m.ys, refs:REFS[k]||[], src:m.src}; }); }
function setParams(q){''')
rep("  step, reset, ignite, toggleOpening, setParams, stats, id, Xvol,",
    "  step, reset, ignite, toggleOpening, setParams, stats, id, Xvol, igniteItem, stopOverheat, setItemMaterial, assess, matTable, sclass, itemOf, supDx, supDy, supDz, VENTS, qx,")
rep("  info:{nx,ny,nz,N,h,NXi,NYi,NZi,LX,LY,LZ,SY,SZ,DIM},", "  info:{nx,ny,nz,N,h,NXi,NYi,NZi,LX,LY,LZ,SY,SZ,DIM,AXY,AXZ},")
p.write_text(s, encoding="utf-8")
print("solver patched", len(s))
