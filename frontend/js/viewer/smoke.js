// Smoke particles and ventilation streamlines. Particles are advected by a simple cabin flow
// field (inlet overhead at -X, return on the deck at +X), rise with buoyancy only when there is
// gravity, and stay inside the cabin aisle or the fire's enclosure. On top of the mean flow every
// particle is carried by a divergence-free (curl) turbulence field that grows with its age, so the
// plume rises, bends, billows and breaks up instead of running down the cabin as a straight line.
import * as THREE from 'three';

const HALF = 0.98;          // cabin aisle half-width (m)
const XMIN = -3.6, XMAX = 3.6;

export function cabinFlow(p, vent, out) {
  // axial flow from the inlet (-X, overhead) to the return (+X, deck) with a gentle swirl
  const s = (p.x - XMIN) / (XMAX - XMIN);
  const vy = -0.9 * Math.sin(Math.PI * s) * 0.35 - (p.y - (0.6 - 1.2 * s)) * 0.25;
  const vz = 0.18 * Math.sin(p.x * 1.3) - p.z * 0.12;
  out.set(1, vy, vz).multiplyScalar(vent);
  return out;
}

// divergence-free turbulence: the curl of a vector potential made of a few sine waves in three
// octaves (wavelengths ~0.45, 0.2 and 0.1 m). Cheap and smooth; velocity in units of 1.
const KS = [14, 30, 64], WT = [1, 0.6, 0.35];
const DIR = [
  [[0.62, 0.31, -0.72], [-0.35, 0.81, 0.47], [0.55, -0.58, 0.6]],
  [[-0.71, 0.52, 0.47], [0.28, -0.44, 0.85], [0.8, 0.4, -0.45]],
  [[0.4, 0.78, -0.48], [-0.66, -0.3, 0.69], [0.23, 0.59, 0.77]],
];
const KV = DIR.map((o, j) => o.map((d) => d.map((c) => c * KS[j])));
export function curlNoise(p, t, out) {
  let vx = 0, vy = 0, vz = 0;
  for (let j = 0; j < 3; j++) {
    const a = WT[j] / KS[j];
    for (let c = 0; c < 3; c++) {
      const k = KV[j][c], cs = Math.cos(k[0] * p.x + k[1] * p.y + k[2] * p.z + t * (0.3 + 0.2 * j) + 1.7 * j + 2.1 * c) * a;
      if (c === 0) { vy += cs * k[2]; vz -= cs * k[1]; }
      else if (c === 1) { vx -= cs * k[2]; vz += cs * k[0]; }
      else { vx += cs * k[1]; vy -= cs * k[0]; }
    }
  }
  return out.set(vx, vy, vz);
}

// a soft, irregular puff (a cluster of blobs with a faded edge), the same for every particle; each
// particle turns it by its own angle
function puffTexture() {
  const S = 128, c = document.createElement('canvas'); c.width = c.height = S;
  const x = c.getContext('2d');
  let s = 20261115; const r = () => ((s = (s * 1103515245 + 12345) >>> 0) / 4294967296);
  x.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 16; i++) {
    const a = r() * 6.2832, d = Math.sqrt(r()) * 0.2 * S, cx = S / 2 + Math.cos(a) * d, cy = S / 2 + Math.sin(a) * d, rad = (0.2 + 0.14 * r()) * S;
    const g = x.createRadialGradient(cx, cy, 0, cx, cy, rad);
    g.addColorStop(0, 'rgba(255,255,255,.2)'); g.addColorStop(0.55, 'rgba(255,255,255,.08)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = g; x.fillRect(0, 0, S, S);
  }
  x.globalCompositeOperation = 'destination-in';
  const m = x.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
  m.addColorStop(0, 'rgba(0,0,0,1)'); m.addColorStop(0.62, 'rgba(0,0,0,1)'); m.addColorStop(1, 'rgba(0,0,0,0)');
  x.fillStyle = m; x.fillRect(0, 0, S, S);
  return new THREE.CanvasTexture(c);
}

export class Smoke {
  constructor(scene, count = 4000) {
    this.n = count;
    this.pos = new Float32Array(count * 3);
    this.age = new Float32Array(count).fill(-1);
    this.seed = new Float32Array(count).map(() => Math.random());
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('age', new THREE.BufferAttribute(this.age, 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('seed', new THREE.BufferAttribute(this.seed, 1));
    this.uniforms = { uMap: { value: puffTexture() }, uColor: { value: new THREE.Color(0.6, 0.6, 0.6) }, uScale: { value: 300 }, uLife: { value: 150 }, uOpacity: { value: 0.5 } };
    this.points = new THREE.Points(g, new THREE.ShaderMaterial({
      uniforms: this.uniforms, transparent: true, depthWrite: false,
      vertexShader: `attribute float age; attribute float seed; uniform float uScale, uLife; varying float vA; varying float vS;
        void main(){ vA=age; vS=seed; vec4 mv=modelViewMatrix*vec4(position,1.); float a=max(age,0.);
          float size=(0.09+0.6*sqrt(a/uLife))*(0.7+0.6*seed);
          gl_PointSize = age<0. ? 0. : size*uScale/ -mv.z; gl_Position=projectionMatrix*mv; }`,
      fragmentShader: `uniform sampler2D uMap; uniform vec3 uColor; uniform float uLife, uOpacity; varying float vA; varying float vS;
        void main(){ if(vA<0.) discard; float t=vA/uLife;
          vec2 c=gl_PointCoord-0.5; float ang=vS*6.2831+vA*0.05*(vS-0.5); float cs=cos(ang), sn=sin(ang);
          float a=texture2D(uMap,vec2(cs*c.x-sn*c.y, sn*c.x+cs*c.y)+0.5).a;
          float fade=smoothstep(0.,0.008,t)*(1.-smoothstep(0.55,1.,t));
          gl_FragColor=vec4(uColor*(0.8+0.4*vS), a*fade*uOpacity*(0.55+0.45*vS)); }`,
    }));
    this.points.frustumCulled = false;
    this.points.renderOrder = 5;
    scene.add(this.points);
    this.cursor = 0;
    this.tmp = new THREE.Vector3();
    this.p = new THREE.Vector3();
    this.cfg = null;
    this.carry = 0;
    this.t = 0;
    this.q = new THREE.Vector3();
  }

  setBudget(n) { this.budget = Math.min(n, this.n); }

  configure(anchor, result, gravityFrac, enclosure) {
    this.anchor = new THREE.Vector3(...anchor);
    const soot = result.flame.soot_index;
    const shade = THREE.MathUtils.clamp(0.82 - soot * 0.55, 0.12, 0.85);
    this.uniforms.uColor.value.setRGB(shade, shade * 0.98, shade * 0.95);
    this.uniforms.uOpacity.value = 0.14 + Math.min(0.26, soot * 0.22);
    this.cfg = { g: gravityFrac, enclosure, vent: result.inputs.vent_cm_s / 100, soot };
    this.reset();
  }

  reset() { this.age.fill(-1); this.cursor = 0; this.carry = 0; this.t = 0; this._upload(); this.uploadedLive = false; }

  _upload() { this.points.geometry.attributes.position.needsUpdate = true; this.points.geometry.attributes.age.needsUpdate = true; }

  // dtSim: simulated seconds this frame; row: interpolated time-series sample
  step(dtSim, row) {
    if (!this.cfg || dtSim <= 0) return;
    const c = this.cfg, n = this.n, pos = this.pos, age = this.age;
    const vent = row && row.vent ? c.vent : 0;
    const life = this.uniforms.uLife.value;
    // emission proportional to heat release x sootiness
    // visible smoke scales with the soot yield: a nearly soot-free fuel (Delrin) makes almost none
    const rate = row ? Math.min(28, row.hrr_kw * c.soot * 9 + (row.flame > 0.02 ? 0.6 + 2 * c.soot : 0)) : 0;
    this.carry += rate * dtSim;
    let live = 0;
    while (this.carry >= 1) {
      this.carry -= 1;
      const i = this.cursor; this.cursor = (this.cursor + 1) % (this.budget || n);
      pos[i * 3] = this.anchor.x + (Math.random() - 0.5) * 0.06;
      pos[i * 3 + 1] = this.anchor.y + 0.05 + Math.random() * 0.05;
      pos[i * 3 + 2] = this.anchor.z + (Math.random() - 0.5) * 0.06;
      age[i] = 0; live++;
    }
    this.t += dtSim;
    const sub = Math.min((this.budget || n) > 1500 ? 3 : 1, Math.ceil(dtSim / 0.5));
    const h = dtSim / sub;
    const f = this.tmp, p = this.p;
    const buoy = 0.1 * Math.sqrt(c.g);           // m/s plume rise at full gravity, scaled
    const enclosed = c.enclosure !== 'open';
    const lim = this.budget || n;
    for (let i = 0; i < lim; i++) {
      if (age[i] < 0) continue;
      live++;
      age[i] += dtSim;
      if (age[i] > life) { age[i] = -1; continue; }
      for (let k = 0; k < sub; k++) {
        p.set(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
        cabinFlow(p, vent, f);
        const young = Math.exp(-age[i] / 20);
        // enclosure: flow inside a rack/fülke is slower; smoke leaks out gradually
        const local = enclosed && p.distanceTo(this.anchor) < 0.45 ? 0.25 : 1;
        f.multiplyScalar(local);
        f.y += buoy * (0.3 + young);
        // the hot gas leaves the flame upwards and is bent over by the flow (only where there is gravity)
        f.y += 0.28 * Math.exp(-age[i] / 3.2) * Math.min(1, c.g * 4);
        // curl turbulence, growing with age: wisps near the flame, billows further on
        const swirl = (0.015 + 0.85 * vent + 0.08 * Math.sqrt(c.g)) * (1 - Math.exp(-age[i] / 6)) * (enclosed && local < 1 ? 0.4 : 1);
        curlNoise(p, this.t, this.q);
        f.addScaledVector(this.q, swirl);
        // diffusion (slow in quiescent microgravity)
        const turb = 0.002 + 0.008 * (vent * 3 + Math.sqrt(c.g) * 0.5);
        f.x += (Math.random() - 0.5) * turb * 2; f.y += (Math.random() - 0.5) * turb * 2; f.z += (Math.random() - 0.5) * turb * 2;
        p.addScaledVector(f, h);
        // walls of the aisle: smoke spreads along the ceiling instead of passing through
        if (p.y > HALF) p.y = HALF - Math.random() * 0.02;
        if (p.y < -HALF) p.y = -HALF + 0.01;
        if (p.z > HALF) p.z = HALF - 0.01;
        if (p.z < -HALF - (enclosed ? 0.8 : 0)) p.z = -HALF - (enclosed ? 0.8 : 0) + 0.01;
        if (p.x > XMAX) { age[i] = -1; break; }      // removed by the return filter
        if (p.x < XMIN) p.x = XMIN;
        pos[i * 3] = p.x; pos[i * 3 + 1] = p.y; pos[i * 3 + 2] = p.z;
      }
    }
    // no particle alive now or at the last upload: the GPU copy is already right
    if (live || this.uploadedLive) this._upload();
    this.uploadedLive = live > 0;
  }

  resize(h) { this.uniforms.uScale.value = h * 0.9; }
}

export class Airflow {
  constructor(scene) {
    this.group = new THREE.Group();
    this.group.visible = false;
    scene.add(this.group);
    this.uniforms = { uTime: { value: 0 }, uOn: { value: 1 } };
    this.build();
  }

  build() {
    const lines = [], sArr = [];
    const f = new THREE.Vector3(), p = new THREE.Vector3();
    let seed = 11; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let k = 0; k < 70; k++) {
      p.set(-3.3, 0.55 + rnd() * 0.4, (rnd() - 0.5) * 1.6);
      let s = 0;
      for (let i = 0; i < 160; i++) {
        const a = p.clone();
        cabinFlow(p, 1, f);
        f.y += (rnd() - 0.5) * 0.08; f.z += (rnd() - 0.5) * 0.08;
        p.addScaledVector(f.normalize(), 0.05);
        p.y = THREE.MathUtils.clamp(p.y, -0.95, 0.95); p.z = THREE.MathUtils.clamp(p.z, -0.95, 0.95);
        lines.push(a.x, a.y, a.z, p.x, p.y, p.z);
        sArr.push(s, s + 0.05); s += 0.05;
        if (p.x > 3.3) break;
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(lines, 3));
    g.setAttribute('arc', new THREE.Float32BufferAttribute(sArr, 1));
    const m = new THREE.ShaderMaterial({
      uniforms: this.uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `attribute float arc; varying float vS; void main(){ vS=arc; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
      fragmentShader: `uniform float uTime, uOn; varying float vS; void main(){ float w=fract(vS*1.6-uTime*0.6); float a=smoothstep(0.0,0.08,w)*(1.-smoothstep(0.1,0.45,w));
        gl_FragColor=vec4(vec3(0.35,0.85,0.95)*a*(0.25+0.75*uOn),1.); }`,
    });
    this.group.add(new THREE.LineSegments(g, m));
  }

  update(t, ventOn) { this.uniforms.uTime.value = t; this.uniforms.uOn.value = ventOn ? 1 : 0.05; }
}
