// Smoke particles and ventilation streamlines. Particles are advected by a simple cabin flow
// field (inlet overhead at -X, return on the deck at +X), rise with buoyancy only when there is
// gravity, and stay inside the cabin aisle or the fire's enclosure.
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

function softDisc() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const x = c.getContext('2d'), g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.5, 'rgba(255,255,255,.45)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 64, 64);
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
    this.uniforms = { uMap: { value: softDisc() }, uColor: { value: new THREE.Color(0.6, 0.6, 0.6) }, uScale: { value: 300 }, uLife: { value: 150 }, uOpacity: { value: 0.5 } };
    this.points = new THREE.Points(g, new THREE.ShaderMaterial({
      uniforms: this.uniforms, transparent: true, depthWrite: false,
      vertexShader: `attribute float age; attribute float seed; uniform float uScale, uLife; varying float vA; varying float vS;
        void main(){ vA=age; vS=seed; vec4 mv=modelViewMatrix*vec4(position,1.); float a=max(age,0.);
          float size=(0.05+0.55*sqrt(a/uLife))*(0.7+0.6*seed);
          gl_PointSize = age<0. ? 0. : size*uScale/ -mv.z; gl_Position=projectionMatrix*mv; }`,
      fragmentShader: `uniform sampler2D uMap; uniform vec3 uColor; uniform float uLife, uOpacity; varying float vA; varying float vS;
        void main(){ if(vA<0.) discard; float t=vA/uLife; float a=texture2D(uMap,gl_PointCoord).a;
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

  reset() { this.age.fill(-1); this.cursor = 0; this.carry = 0; this._upload(); }

  _upload() { this.points.geometry.attributes.position.needsUpdate = true; this.points.geometry.attributes.age.needsUpdate = true; }

  // dtSim: simulated seconds this frame; row: interpolated time-series sample
  step(dtSim, row) {
    if (!this.cfg || dtSim <= 0) return;
    const c = this.cfg, n = this.n, pos = this.pos, age = this.age;
    const vent = row && row.vent ? c.vent : 0;
    const life = this.uniforms.uLife.value;
    // emission proportional to heat release x sootiness
    const rate = row ? Math.min(28, row.hrr_kw * (0.3 + c.soot) * 6 + (row.flame > 0.02 ? 2 : 0)) : 0;
    this.carry += rate * dtSim;
    while (this.carry >= 1) {
      this.carry -= 1;
      const i = this.cursor; this.cursor = (this.cursor + 1) % (this.budget || n);
      pos[i * 3] = this.anchor.x + (Math.random() - 0.5) * 0.06;
      pos[i * 3 + 1] = this.anchor.y + 0.05 + Math.random() * 0.05;
      pos[i * 3 + 2] = this.anchor.z + (Math.random() - 0.5) * 0.06;
      age[i] = 0;
    }
    const sub = Math.min((this.budget || n) > 1500 ? 3 : 1, Math.ceil(dtSim / 0.5));
    const h = dtSim / sub;
    const f = this.tmp, p = this.p;
    const buoy = 0.1 * Math.sqrt(c.g);           // m/s plume rise at full gravity, scaled
    const enclosed = c.enclosure !== 'open';
    const lim = this.budget || n;
    for (let i = 0; i < lim; i++) {
      if (age[i] < 0) continue;
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
        // diffusion / turbulence (slow in quiescent microgravity)
        const turb = 0.004 + 0.02 * (vent * 3 + Math.sqrt(c.g) * 0.5);
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
    this._upload();
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
