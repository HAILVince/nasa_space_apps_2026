// Geometry layouts for the shared fire engine (fire_core/engine.js).
// A layout is a function of a small context and returns the domain size, compartments (ROOMS), solid furnishings
// (SHELLS), closable openings (OPEN), ventilation (VENTS), possible fire origins (ITEMS), vent-to-vacuum valves
// (VALVES), crew start positions (CREW) and the compartment graph used for crew movement (GRAPH).
// Coordinates are metres; x runs along the vehicle, y is "up" when there is gravity.
const FIRE_LAYOUTS={};

// ---------------- crewed spacecraft: Lab module – Node with crew quarters – Airlock ----------------
FIRE_LAYOUTS.ship=function(ctx){
  const AXY=2.1, AXZ=2.1, r2=(y,z)=>(y-AXY)**2+(z-AXZ)**2;
  return {
    name:'Spacecraft: Lab module, Node with crew quarters, Airlock', LX:11.5, LY:4.2, LZ:4.2, AXY, AXZ,
    sclass:(x,y,z)=> ((x>=6.5&&x<6.65)||(x>=9.5&&x<9.65))? 2 : 1,   // 2 = bulkhead, 1 = hull / rack structure
    ROOMS:[
      {id:'lab',  name:'Lab module (aisle)',      short:'Lab',      x0:0.3, x1:6.5,  test:(x,y,z)=>x>=0.3&&x<6.5&&Math.abs(y-AXY)<1.05&&Math.abs(z-AXZ)<1.05},
      {id:'rack', name:'Avionics rack bay',        short:'Rack bay', x0:1.2, x1:2.1,  test:(x,y,z)=>x>=1.2&&x<2.1&&y>=1.35&&y<2.85&&z>=3.35&&z<3.9},
      {id:'node', name:'Node and galley',          short:'Node',     x0:6.65,x1:9.5,  test:(x,y,z)=>x>=6.65&&x<9.5&&r2(y,z)<4.0},
      {id:'cqp',  name:'Crew quarters, port',      short:'CQ port',  x0:7.0, x1:8.2,  late:true, test:(x,y,z)=>x>=7.0&&x<8.2&&y>=1.0&&y<3.1&&z>=0.6&&z<1.05},
      {id:'cqs',  name:'Crew quarters, starboard', short:'CQ stbd',  x0:7.0, x1:8.2,  late:true, test:(x,y,z)=>x>=7.0&&x<8.2&&y>=1.0&&y<3.1&&z>=3.15&&z<3.6},
      {id:'air',  name:'Airlock',                  short:'Airlock',  x0:9.65,x1:11.4, test:(x,y,z)=>x>=9.65&&x<11.4&&r2(y,z)<1.3225},
    ],
    SHELLS:[
      {name:'Port crew-quarters enclosure',      cls:3, test:(x,y,z)=>x>=6.85&&x<8.35&&y>=0.85&&y<3.25&&z>=0.45&&z<1.2},
      {name:'Starboard crew-quarters enclosure', cls:3, test:(x,y,z)=>x>=6.85&&x<8.35&&y>=0.85&&y<3.25&&z>=3.0&&z<3.75},
      {name:'Galley table',                      cls:3, test:(x,y,z)=>x>=8.4&&x<9.2&&y>=1.0&&y<1.15&&z>=1.6&&z<2.6},
    ],
    OPEN:[
      {id:'H1', name:'Lab–Node hatch',               test:(x,y,z)=>x>=6.5&&x<6.65&&Math.abs(y-AXY)<0.6&&Math.abs(z-AXZ)<0.6, open:true, walk:true},
      {id:'H2', name:'Node–Airlock hatch',           test:(x,y,z)=>x>=9.5&&x<9.65&&Math.abs(y-AXY)<0.5&&Math.abs(z-AXZ)<0.5, open:true, walk:true},
      {id:'C1', name:'Port crew-quarters door',      test:(x,y,z)=>x>=7.3&&x<7.9&&y>=1.5&&y<2.7&&z>=1.05&&z<1.2, open:true, walk:true},
      {id:'C2', name:'Starboard crew-quarters door', test:(x,y,z)=>x>=7.3&&x<7.9&&y>=1.5&&y<2.7&&z>=3.0&&z<3.15, open:true, walk:true},
      {id:'G1', name:'Avionics rack grilles',        test:(x,y,z)=>x>=1.35&&x<1.95&&z>=3.15&&z<3.35&&((y>=1.35&&y<1.65)||(y>=2.55&&y<2.85)), open:true},
    ],
    VENTS:[
      {kind:'sup', name:'Lab overhead diffusers', dir:[0,-1,0], sp:1,   room:'lab',  test:(x,y,z,k)=>((x>=1.0&&x<1.6)||(x>=3.0&&x<3.6)||(x>=5.0&&x<5.6))&&Math.abs(z-AXZ)<0.45&&ctx.solid(k+ctx.SY)},
      {kind:'sup', name:'Node overhead diffuser', dir:[0,-1,0], sp:1,   room:'node', test:(x,y,z,k)=>x>=7.0&&x<8.6&&Math.abs(z-AXZ)<0.4&&ctx.solid(k+ctx.SY)&&y>3},
      {kind:'sup', name:'Rack cooling fan',       dir:[0,1,0],  sp:0.3, room:'rack', test:(x,y,z,k)=>x>=1.5&&x<1.8&&z>=3.5&&z<3.8&&ctx.solid(k-ctx.SY)},
      {kind:'sup', name:'Port CQ fan',            dir:[0,-1,0], sp:0.4, room:'cqp',  test:(x,y,z,k)=>x>=7.3&&x<7.9&&z<0.9&&ctx.solid(k+ctx.SY)},
      {kind:'sup', name:'Starboard CQ fan',       dir:[0,-1,0], sp:0.4, room:'cqs',  test:(x,y,z,k)=>x>=7.3&&x<7.9&&z>=3.3&&ctx.solid(k+ctx.SY)},
      {kind:'ret', name:'Lab return grille',      room:'lab',  test:(x,y,z,k)=>x>=0.45&&x<0.9&&Math.abs(z-AXZ)<0.4&&ctx.solid(k-ctx.SY)},
      {kind:'ret', name:'Node return grille',     room:'node', test:(x,y,z,k)=>x>=8.9&&x<9.35&&Math.abs(z-AXZ)<0.4&&ctx.solid(k-ctx.SY)&&y<1.0},
    ],
    // Vent-to-vacuum valves for emergency depressurisation (last-resort response). Effective area is an assumption:
    // NTRS 20260003546 notes real module venting is about ten times slower than the "within minutes to 4 psia" requirement.
    VALVES:[
      {room:'lab',  name:'Lab vent valve',     area:0.0004, test:(x,y,z)=>x>=0.45&&x<0.75&&y>=3.0&&Math.abs(z-AXZ)<0.2},
      {room:'node', name:'Node vent valve',    area:0.0004, test:(x,y,z)=>x>=8.0&&x<8.3&&y<1.25&&Math.abs(z-AXZ)<0.2},
      {room:'air',  name:'Airlock depress valve', area:0.0004, test:(x,y,z)=>x>=11.0&&x<11.3&&Math.abs(y-AXY)<0.2&&Math.abs(z-AXZ)<0.2},
    ],
    ITEMS:[
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
    ],
    // crew start positions (head height); asleep crew react later to alarms
    CREW:[
      {id:'CDR', name:'Commander',          room:'lab',  pos:[3.4,2.2,2.1]},
      {id:'FE1', name:'Flight engineer 1',  room:'node', pos:[8.3,2.3,2.1]},
      {id:'FE2', name:'Flight engineer 2',  room:'cqp',  pos:[7.6,2.2,0.85], asleep:true},
      {id:'FE3', name:'Flight engineer 3',  room:'cqs',  pos:[7.6,2.2,3.35], asleep:true},
    ],
    // compartments the crew can move between, through which opening
    GRAPH:[['lab','node','H1'],['node','air','H2'],['node','cqp','C1'],['node','cqs','C2']],
    havens:['lab','node','air'],
  };
};

// ---------------- crewed spacecraft, 2D: a longitudinal vertical section (x along the vehicle, y up), one cell deep ----------------
// Same compartments, items, vents, valves and crew as the 3D ship, laid out in the section plane. Every item spans the slice depth,
// so quantities are per slice of depth h. Valve areas are scaled to the slice depth so venting takes as long as in 3D.
FIRE_LAYOUTS.ship2d=function(ctx,cfg){
  const h=cfg.h||0.075, depth=2.1, zA=[0,10];
  const W=(x0,x1,y0,y1)=>(x,y)=>x>=x0&&x<x1&&y>=y0&&y<y1;
  const it=(o)=>Object.assign({z:zA},o);
  return {
    dim:2, name:'Spacecraft section (2D): Lab module, Node with crew quarters, Airlock', LX:11.5, LY:4.2, LZ:h, AXY:2.1, AXZ:h/2,
    sclass:(x,y,z)=> ((x>=6.5&&x<6.65)||(x>=9.5&&x<9.65))? 2 : 1,
    ROOMS:[
      {id:'lab',  name:'Lab module (aisle)',      short:'Lab',      x0:0.3, x1:6.5,  test:W(0.3,6.5,1.05,3.15)},
      {id:'rack', name:'Avionics rack bay',        short:'Rack bay', x0:1.2, x1:2.1,  test:W(1.2,2.1,0.45,0.9)},
      {id:'node', name:'Node and galley',          short:'Node',     x0:6.65,x1:9.5,  test:W(6.65,9.5,0.1,4.1)},
      {id:'cqp',  name:'Crew quarters, port',      short:'CQ port',  x0:7.0, x1:8.2,  late:true, test:W(7.0,8.2,2.9,3.85)},
      {id:'cqs',  name:'Crew quarters, starboard', short:'CQ stbd',  x0:7.0, x1:8.2,  late:true, test:W(7.0,8.2,0.35,1.3)},
      {id:'air',  name:'Airlock',                  short:'Airlock',  x0:9.65,x1:11.4, test:W(9.65,11.4,1.15,3.05)},
    ],
    SHELLS:[
      {name:'Port crew-quarters enclosure',      cls:3, test:W(6.85,8.35,2.75,4.0)},
      {name:'Starboard crew-quarters enclosure', cls:3, test:W(6.85,8.35,0.2,1.45)},
      {name:'Galley table',                      cls:3, test:W(8.4,9.2,1.9,2.05)},
    ],
    OPEN:[
      {id:'H1', name:'Lab–Node hatch',               test:W(6.5,6.65,1.5,2.7), open:true, walk:true},
      {id:'H2', name:'Node–Airlock hatch',           test:W(9.5,9.65,1.6,2.6), open:true, walk:true},
      {id:'C1', name:'Port crew-quarters door',      test:W(7.3,7.9,2.75,2.9), open:true, walk:true},
      {id:'C2', name:'Starboard crew-quarters door', test:W(7.3,7.9,1.3,1.45), open:true, walk:true},
      {id:'G1', name:'Avionics rack grilles',        test:(x,y)=>y>=0.9&&y<1.05&&((x>=1.35&&x<1.5)||(x>=1.8&&x<1.95)), open:true},
    ],
    VENTS:[
      {kind:'sup', name:'Lab overhead diffusers', dir:[0,-1,0], sp:1,   room:'lab',  test:(x,y,z,k)=>((x>=1.0&&x<1.6)||(x>=3.0&&x<3.6)||(x>=5.0&&x<5.6))&&ctx.solid(k+ctx.SY)},
      {kind:'sup', name:'Node overhead diffuser', dir:[0,-1,0], sp:1,   room:'node', test:(x,y,z,k)=>x>=8.6&&x<9.3&&y>3.5&&ctx.solid(k+ctx.SY)},
      {kind:'sup', name:'Rack cooling fan',       dir:[1,0,0],  sp:0.3, room:'rack', test:(x,y,z,k)=>x>=1.2&&x<1.2+h&&y>=0.5&&y<0.85},
      {kind:'sup', name:'Port CQ fan',            dir:[0,-1,0], sp:0.4, room:'cqp',  test:(x,y,z,k)=>x>=7.3&&x<7.9&&ctx.solid(k+ctx.SY)},
      {kind:'sup', name:'Starboard CQ fan',       dir:[0,1,0],  sp:0.4, room:'cqs',  test:(x,y,z,k)=>x>=7.3&&x<7.9&&ctx.solid(k-ctx.SY)},
      {kind:'ret', name:'Lab return grille',      room:'lab',  test:(x,y,z,k)=>x>=0.45&&x<0.9&&ctx.solid(k-ctx.SY)},
      {kind:'ret', name:'Node return grille',     room:'node', test:(x,y,z,k)=>x>=8.9&&x<9.35&&y<0.6&&ctx.solid(k-ctx.SY)},
    ],
    VALVES:[
      {room:'lab',  name:'Lab vent valve',        area:0.0004*h/depth, test:W(0.45,0.75,2.9,3.15)},
      {room:'node', name:'Node vent valve',       area:0.0004*h/depth, test:W(8.0,8.3,0.1,0.5)},
      {room:'air',  name:'Airlock depress valve', area:0.0004*h/depth, test:W(11.0,11.3,2.0,2.2)},
    ],
    ITEMS:[
      it({id:'L1', name:'Avionics rack wire harness', where:'Lab · inside the avionics rack under the deck', room:'rack', m:'pe', opts:['pe','ptfe','kapton','silicone'], x:[1.5,1.8], y:[0.55,0.8], af:0.2,
        note:'Overheated wiring is the most likely spacecraft fire source. Real bundle ≈5 cm across, so 20% of the cell surface burns.'}),
      it({id:'L2', name:'Experiment rack front panel', where:'Lab · deck rack face', room:'lab', m:'pc', opts:['pc','pmma','nomex'], onWall:true, x:[3.0,4.0], y:[0.9,1.05]}),
      it({id:'L3', name:'Overhead stowage bags (CTBs)', where:'Lab · overhead rack face', room:'lab', m:'nomex', opts:['nomex','sibal','cotton'], onWall:true, x:[4.5,6.2], y:[3.15,3.3]}),
      it({id:'L4', name:'Laptop foam packing', where:'Lab · deck, in the aisle', room:'lab', m:'pu', opts:['pu','nomex','cotton'], x:[2.2,2.7], y:[1.05,1.4]}),
      it({id:'L5', name:'Wipes and checklists on worktable', where:'Lab · deck, aft of the panel', room:'lab', m:'paper', opts:['paper','cotton'], x:[4.2,4.8], y:[1.05,1.2]}),
      it({id:'L6', name:'Glovebox window', where:'Lab · overhead rack face', room:'lab', m:'pmma', opts:['pmma','pc'], onWall:true, x:[3.2,4.0], y:[3.15,3.3]}),
      it({id:'L7', name:'Overhead cable tray', where:'Lab · overhead, aft', room:'lab', m:'ptfe', opts:['ptfe','pe','kapton'], onWall:true, x:[1.8,3.1], y:[3.15,3.3], af:0.3}),
      it({id:'N1', name:'Sleeping bag', where:'Node · port crew quarters', room:'cqp', m:'nomex', opts:['nomex','cotton','sibal'], x:[7.15,8.05], y:[3.55,3.7]}),
      it({id:'N2', name:'Crew clothing', where:'Node · starboard crew quarters', room:'cqs', m:'cotton', opts:['cotton','nomex'], x:[7.2,7.9], y:[0.4,0.55]}),
      it({id:'N3', name:'Velcro strips', where:'Node · forward bulkhead', room:'node', m:'nylon', opts:['nylon','nomex'], onWall:true, x:[9.5,9.65], y:[2.75,3.5], af:0.3}),
      it({id:'N4', name:'Galley food packaging', where:'Node · on the galley table', room:'node', m:'paper', opts:['paper','pe'], x:[8.5,9.0], y:[2.05,2.3]}),
      it({id:'N5', name:'Closeout curtain', where:'Node · aft bulkhead, above the hatch', room:'node', m:'sibal', opts:['sibal','nomex','cotton'], onWall:true, x:[6.5,6.65], y:[3.0,3.9]}),
      it({id:'A1', name:'EVA suit outer layer', where:'Airlock', room:'air', m:'nomex', opts:['nomex','sibal','cotton'], x:[10.3,10.8], y:[1.4,2.8]}),
      it({id:'A2', name:'Hatch seal', where:'Airlock · around the hatch', room:'air', m:'silicone', opts:['silicone','nylon'], onWall:true, test:(x,y)=>x>=9.5&&x<9.65&&((y>=1.45&&y<1.6)||(y>=2.6&&y<2.75)), af:0.25}),
    ],
    CREW:[
      {id:'CDR', name:'Commander',          room:'lab',  pos:[3.4,2.2,h/2]},
      {id:'FE1', name:'Flight engineer 1',  room:'node', pos:[8.0,2.4,h/2]},
      {id:'FE2', name:'Flight engineer 2',  room:'cqp',  pos:[7.6,3.3,h/2], asleep:true},
      {id:'FE3', name:'Flight engineer 3',  room:'cqs',  pos:[7.6,0.85,h/2], asleep:true},
    ],
    GRAPH:[['lab','node','H1'],['node','air','H2'],['node','cqp','C1'],['node','cqs','C2']],
    havens:['lab','node','air'],
  };
};

// ---------------- Saffire-style test: a sample in a flow duct inside a sealed Cygnus-like cabin ----------------
// cfg.saffire = {L: sample length m, W: width m, m: material key, vol: free volume m³, sides: 1|2, thick: m (PMMA)}
FIRE_LAYOUTS.saffire=function(ctx,cfg){
  const s=Object.assign({L:0.5,W:0.4,m:'sibal',vol:17.9,sides:2},cfg.saffire||{});
  const h=cfg.h||0.1, LX=3.2, LY=2.5, LZ=Math.max(1.6,s.vol/(LX*LY)+0.06);
  const yc=1.25, zc=LZ/2, x0=0.75, x1=x0+s.L;
  // the Saffire flow unit: an open duct ~0.5 m wide and ~0.4 m tall; the fan at its upstream end gives 20 cm/s
  const dz=Math.max(0.3,s.W/2+0.1), dy=0.22;
  return {
    name:'Saffire flow unit in a sealed cabin', LX, LY, LZ, AXY:yc, AXZ:zc,
    sclass:()=>1,
    ROOMS:[{id:'cab', name:'Test cabin', short:'Cabin', x0:0, x1:LX, test:()=>true}],
    SHELLS:[
      {name:'duct top',    cls:3, test:(x,y,z)=>x>=0.35&&x<x1+0.55&&y>=yc+dy&&y<yc+dy+h&&Math.abs(z-zc)<dz+h},
      {name:'duct bottom', cls:3, test:(x,y,z)=>x>=0.35&&x<x1+0.55&&y<yc-dy&&y>=yc-dy-h&&Math.abs(z-zc)<dz+h},
      {name:'duct sides',  cls:3, test:(x,y,z)=>x>=0.35&&x<x1+0.55&&y>=yc-dy-h&&y<yc+dy+h&&Math.abs(z-zc)>=dz&&Math.abs(z-zc)<dz+h},
      ...(s.sides===1? [{name:'backing plate', cls:3, test:(x,y,z)=>x>=x0&&x<x1&&y<yc-h/2&&y>=yc-1.5*h&&Math.abs(z-zc)<s.W/2}] : []),
    ],
    OPEN:[], VALVES:[],
    VENTS:[{kind:'sup', name:'Flow unit fan', dir:[1,0,0], sp:1, room:'cab', test:(x,y,z)=>x>=0.35&&x<0.35+h&&Math.abs(y-yc)<dy&&Math.abs(z-zc)<dz}],
    ITEMS:[{id:'S1', name:'Saffire sample', where:'flow unit', room:'cab', m:s.m, opts:[s.m], x:[x0,x1], y:[yc-h/2,yc+h/2], z:[zc-s.W/2,zc+s.W/2], m0:s.m0}],
    CREW:[], GRAPH:[], havens:[],
    probe:[LX-0.35, yc, zc],   // far-field diagnostic (FFD) downstream of the flow unit
    sample:{x0,x1,yc,zc},
  };
};
if(typeof module!=='undefined') module.exports={FIRE_LAYOUTS};
