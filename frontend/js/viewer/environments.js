// Backdrops and lighting for the five environments. Planets and sky live in a separate
// background scene rendered with a camera that only copies the main camera's rotation, so
// astronomical distances need no huge depth range; terrain lives in the main scene.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const NOISE = /* glsl */`
float h3(vec3 p){ p=fract(p*0.3183099+.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float vnoise(vec3 x){ vec3 i=floor(x), f=fract(x); f=f*f*(3.0-2.0*f);
  return mix(mix(mix(h3(i),h3(i+vec3(1,0,0)),f.x),mix(h3(i+vec3(0,1,0)),h3(i+vec3(1,1,0)),f.x),f.y),
             mix(mix(h3(i+vec3(0,0,1)),h3(i+vec3(1,0,1)),f.x),mix(h3(i+vec3(0,1,1)),h3(i+vec3(1,1,1)),f.x),f.y),f.z); }
float fbm(vec3 p){ float a=.5, s=0.; for(int i=0;i<OCT;i++){ s+=a*vnoise(p); p=p*2.03+vec3(1.7,9.2,3.1); a*=.5; } return s; }
`;

function earthMaterial(sunDir) {
  return new THREE.ShaderMaterial({
    uniforms: { uSun: { value: sunDir }, uTime: { value: 0 } },
    defines: { OCT: 4 },
    vertexShader: /* glsl */`
      varying vec3 vN; varying vec3 vP; varying vec3 vW;
      void main(){ vN=normalize(mat3(modelMatrix)*normal); vP=position; vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz;
        gl_Position=projectionMatrix*viewMatrix*w; }`,
    fragmentShader: /* glsl */`
      uniform vec3 uSun; uniform float uTime; varying vec3 vN; varying vec3 vP; varying vec3 vW;
      ${NOISE}
      void main(){
        vec3 n=normalize(vN); vec3 p=normalize(vP);
        float c=fbm(p*6.0)+0.5*fbm(p*19.0)-0.62;          // continents
        float land=smoothstep(0.12,0.16,c);
        float lat=abs(p.y);
        vec3 ocean=mix(vec3(0.003,0.014,0.045),vec3(0.006,0.03,0.07),fbm(p*30.));
        vec3 veg=mix(vec3(0.025,0.04,0.015),vec3(0.08,0.07,0.04),smoothstep(0.1,0.5,fbm(p*28.+3.)));
        vec3 desert=vec3(0.17,0.12,0.07);
        vec3 ground=mix(veg,desert,smoothstep(0.55,0.75,fbm(p*11.+7.))*(1.-smoothstep(0.55,0.8,lat)));
        ground=mix(ground,vec3(0.6,0.62,0.65),smoothstep(0.8,0.88,lat));
        vec3 col=mix(ocean,ground,land);
        float cl=smoothstep(0.6,0.88,fbm(p*15.0+vec3(uTime*0.004,0.,0.))+0.25*fbm(p*52.));
        float nd=dot(n,uSun);
        float day=smoothstep(-0.12,0.25,nd);
        vec3 V=normalize(cameraPosition-vW);
        vec3 H=normalize(uSun+V);
        float glint=pow(max(dot(n,H),0.),90.)*(1.-land)*(1.-cl)*2.5;
        vec3 lit=col*max(nd,0.)*1.0 + glint*vec3(1.,.9,.75)*0.35;
        lit=mix(lit, vec3(0.55,0.57,0.6)*max(nd,0.), cl*0.85);
        // city lights on the night side
        float city=smoothstep(0.62,0.9,fbm(p*110.))*land*(1.-smoothstep(-0.05,0.05,nd))*(1.-cl);
        lit+=city*vec3(1.0,0.62,0.25)*0.6;
        float fres=pow(1.-max(dot(n,V),0.),5.0);
        vec3 atm=vec3(0.12,0.3,0.8)*fres*(0.1+0.9*smoothstep(-0.25,0.4,nd));
        atm+=vec3(1.0,0.45,0.15)*fres*smoothstep(0.25,0.0,abs(nd))*0.5;   // terminator glow
        gl_FragColor=vec4(lit*day+lit*0.02+atm,1.);
      }`,
  });
}

function starField(count = 5200, radius = 4000) {
  const g = new THREE.BufferGeometry();
  const pos = new Float32Array(count * 3), col = new Float32Array(count * 3), size = new Float32Array(count);
  let s = 7;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < count; i++) {
    const u = rnd() * 2 - 1, a = rnd() * Math.PI * 2, r = Math.sqrt(1 - u * u);
    pos.set([radius * r * Math.cos(a), radius * u, radius * r * Math.sin(a)], i * 3);
    const m = rnd() ** 6;
    const tint = rnd();
    col.set(tint < 0.2 ? [0.75, 0.82, 1] : tint > 0.9 ? [1, 0.85, 0.7] : [1, 1, 1], i * 3);
    size[i] = 0.6 + 3.2 * m;
  }
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  g.setAttribute('size', new THREE.BufferAttribute(size, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uFade: { value: 1 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `attribute float size; attribute vec3 color; varying vec3 vC; varying float vS;
      void main(){ vC=color; vS=size; vec4 mv=modelViewMatrix*vec4(position,1.); gl_PointSize=size*1.4; gl_Position=projectionMatrix*mv; }`,
    fragmentShader: `uniform float uFade; varying vec3 vC; varying float vS; void main(){ vec2 d=gl_PointCoord-.5; float a=smoothstep(.5,0.,length(d));
      gl_FragColor=vec4(vC*a*min(1.,vS*.45)*uFade,1.); }`,
  });
  return new THREE.Points(g, mat);
}

function marsSky() {
  return new THREE.Mesh(new THREE.SphereGeometry(3000, 48, 32), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, uniforms: { uSun: { value: new THREE.Vector3() } },
    vertexShader: `varying vec3 vD; void main(){ vD=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
    fragmentShader: `uniform vec3 uSun; varying vec3 vD;
      void main(){ float h=vD.y; float sd=max(dot(normalize(vD),uSun),0.);
        vec3 zen=vec3(0.30,0.20,0.15), hor=vec3(0.80,0.58,0.40), low=vec3(0.55,0.36,0.24);
        vec3 c=mix(hor,zen,smoothstep(0.0,0.75,h)); c=mix(low,c,smoothstep(-0.2,0.02,h));
        c+=vec3(0.55,0.62,0.75)*pow(sd,40.)*0.7 + vec3(0.9,0.75,0.6)*pow(sd,6.)*0.25;    // blue sunset halo
        c+=vec3(1.0,0.97,0.9)*smoothstep(0.9993,0.9997,sd)*4.;
        gl_FragColor=vec4(c,1.); }`,
  }));
}

function studio() {
  return new THREE.Mesh(new THREE.SphereGeometry(3000, 32, 16), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    vertexShader: `varying vec3 vD; void main(){ vD=normalize(position); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
    fragmentShader: `varying vec3 vD; void main(){ float h=vD.y; vec3 c=mix(vec3(0.035,0.04,0.045),vec3(0.012,0.014,0.016),smoothstep(-0.1,0.6,h)); gl_FragColor=vec4(c,1.); }`,
  }));
}

function sunDisc(color = 0xfff6e8, size = 60) {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d'); const g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.12, 'rgba(255,250,235,1)'); g.addColorStop(0.2, 'rgba(255,240,210,.35)');
  g.addColorStop(1, 'rgba(255,230,200,0)'); x.fillStyle = g; x.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
  s.scale.setScalar(size); return s;
}

const SUN = {
  leo: new THREE.Vector3(0.55, 0.42, 0.72), lunar_orbit: new THREE.Vector3(-0.6, 0.35, 0.72),
  moon: new THREE.Vector3(-0.72, 0.16, 0.67), mars: new THREE.Vector3(0.45, 0.62, 0.64), earth: new THREE.Vector3(0.4, 0.8, 0.45),
};

export class Environments {
  constructor(viewer) {
    this.v = viewer;
    this.bg = new THREE.Scene();
    this.bgCamera = new THREE.PerspectiveCamera(45, 1, 1, 20000);
    this.loader = new THREE.TextureLoader();
    this.stars = starField();
    this.bg.add(this.stars);
    this.sunDir = new THREE.Vector3();
    this.sunSprite = sunDisc();
    this.bg.add(this.sunSprite);
    // Earth (LEO: huge, below; elsewhere: small and far)
    this.earth = new THREE.Mesh(new THREE.SphereGeometry(1000, 160, 120), earthMaterial(this.sunDir));
    this.bg.add(this.earth);
    this.moonGlobe = null;
    this.marsSky = marsSky();
    this.studio = studio();
    this.bg.add(this.marsSky, this.studio);
    // main-scene lights
    this.sun = new THREE.DirectionalLight(0xffffff, 3);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    this.sun.shadow.bias = -0.0004;
    this.sun.shadow.normalBias = 0.02;
    this.hemi = new THREE.HemisphereLight(0x8899aa, 0x222222, 0.4);
    viewer.scene.add(this.sun, this.sun.target, this.hemi);
    this.terrain = {};
    this.terrainGroup = new THREE.Group();
    viewer.scene.add(this.terrainGroup);
    this.current = null;
  }

  // only what every scene needs is loaded up front; the Moon globe (Gateway) and the rock models
  // (surface scenes) come on first use or from prefetch() once the page is idle
  async preload(progress) {
    this.bgSun = new THREE.DirectionalLight(0xffffff, 3.2);
    this.bgAmb = new THREE.AmbientLight(0x404650, 0.05);
    this.bg.add(this.bgSun, this.bgAmb);
    progress?.(0.2);
  }

  moon() {
    return this._moon || (this._moon = Promise.all([
      this.loader.loadAsync('./assets/3d/moon_globe.webp'), this.loader.loadAsync('./assets/3d/moon_globe_height.webp')])
      .then(([moonAlb, moonH]) => {
        moonAlb.colorSpace = THREE.SRGBColorSpace; moonAlb.anisotropy = 8;
        this.moonGlobe = new THREE.Mesh(new THREE.SphereGeometry(1000, 160, 120),
          new THREE.MeshStandardMaterial({ map: moonAlb, bumpMap: moonH, bumpScale: 6, roughness: 1, metalness: 0 }));
        this.moonGlobe.visible = this.current === 'lunar_orbit';
        this.bg.add(this.moonGlobe);
      }));
  }

  rocks() {
    return this._rocks || (this._rocks = new GLTFLoader().loadAsync('./assets/3d/rocks.glb').then((rocks) => {
      this.rockGeoms = [];
      rocks.scene.traverse((o) => { if (o.isMesh) this.rockGeoms.push(o.geometry); });
    }));
  }

  // fetch what other environments need while nothing else is loading; errors surface on use
  prefetch(bodies = []) {
    const run = () => { this.moon().catch(() => {}); this.rocks().catch(() => {}); for (const b of bodies) this.terrainFor(b).catch(() => {}); };
    if ('requestIdleCallback' in window) requestIdleCallback(run, { timeout: 4000 }); else setTimeout(run, 1500);
  }

  terrainFor(body) {
    return this.terrain[body] || (this.terrain[body] = this.buildTerrain(body).catch((e) => { delete this.terrain[body]; throw e; }));
  }

  async buildTerrain(body) {
    await this.rocks();
    const meta = await (await fetch(`./assets/3d/terrain_${body}.json`)).json();
    const [img, alb] = await Promise.all([
      new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = `./assets/3d/terrain_${body}_height.png`; }),
      this.loader.loadAsync(`./assets/3d/terrain_${body}_albedo.webp`)]);
    alb.colorSpace = THREE.SRGBColorSpace; alb.anisotropy = 8;
    const n = meta.resolution, c = document.createElement('canvas'); c.width = c.height = n;
    const ctx = c.getContext('2d', { willReadFrequently: true }); ctx.drawImage(img, 0, 0);
    const px = ctx.getImageData(0, 0, n, n).data;
    const range = meta.height_max_m - meta.height_min_m;
    const H = (i, j) => { const k = (j * n + i) * 4; return meta.height_min_m + ((px[k] * 256 + px[k + 1]) / 65535) * range; };
    const seg = 220, size = meta.size_m;
    const g = new THREE.PlaneGeometry(size, size, seg, seg);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position, uv = g.attributes.uv;
    for (let k = 0; k < pos.count; k++) {
      const x = pos.getX(k), z = pos.getZ(k);
      const fi = (x / size + 0.5) * (n - 1), fj = (z / size + 0.5) * (n - 1);
      const i = Math.min(n - 2, Math.floor(fi)), j = Math.min(n - 2, Math.floor(fj)), fx = fi - i, fy = fj - j;
      const h = H(i, j) * (1 - fx) * (1 - fy) + H(i + 1, j) * fx * (1 - fy) + H(i, j + 1) * (1 - fx) * fy + H(i + 1, j + 1) * fx * fy;
      pos.setY(k, h + meta.ground_y);
      uv.setXY(k, x / size + 0.5, -z / size + 0.5);
    }
    g.computeVertexNormals();
    const detail = this.detailTexture(body);
    const mat = new THREE.MeshStandardMaterial({ map: alb, roughness: 0.97, metalness: 0, normalMap: detail, normalScale: new THREE.Vector2(0.55, 0.55) });
    const ground = new THREE.Mesh(g, mat);
    ground.receiveShadow = true;
    const group = new THREE.Group();
    group.add(ground);
    // rocks: one instanced mesh per variant
    const rockMat = new THREE.MeshStandardMaterial({ color: body === 'mars' ? 0x6b3b24 : 0x5d5b58, roughness: 0.92, flatShading: true });
    const byV = [[], [], [], []];
    for (const r of meta.rocks) byV[r.v].push(r);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    byV.forEach((list, v) => {
      const inst = new THREE.InstancedMesh(this.rockGeoms[v % this.rockGeoms.length], rockMat, list.length);
      list.forEach((r, k) => {
        q.setFromEuler(e.set(0, r.r, 0));
        m4.compose(new THREE.Vector3(r.p[0], r.p[1] + meta.ground_y, r.p[2]), q, new THREE.Vector3(...r.s));
        inst.setMatrixAt(k, m4);
      });
      inst.castShadow = inst.receiveShadow = true;
      group.add(inst);
    });
    return group;
  }

  detailTexture(body) {
    // small tileable normal map for regolith grain, generated once
    if (this._detail) return this._detail;
    const n = 256, c = document.createElement('canvas'); c.width = c.height = n;
    const x = c.getContext('2d'), img = x.createImageData(n, n);
    const h = new Float32Array(n * n);
    let s = 3; const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    for (let k = 0; k < 900; k++) {
      const cx = rnd() * n, cy = rnd() * n, r = 1 + rnd() ** 3 * 9, d = rnd() < 0.7 ? -1 : 1;
      for (let j = -r; j <= r; j++) for (let i = -r; i <= r; i++) {
        const q = 1 - (i * i + j * j) / (r * r); if (q <= 0) continue;
        const X = (Math.floor(cx + i) + n) % n, Y = (Math.floor(cy + j) + n) % n; h[Y * n + X] += d * q * q * 0.6;
      }
    }
    for (let k = 0; k < n * n; k++) h[k] += rnd() * 0.25;
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
      const dx = h[j * n + (i + 1) % n] - h[j * n + (i - 1 + n) % n], dy = h[((j + 1) % n) * n + i] - h[((j - 1 + n) % n) * n + i];
      const l = Math.hypot(dx, dy, 1), k = (j * n + i) * 4;
      img.data[k] = (-dx / l * 0.5 + 0.5) * 255; img.data[k + 1] = (-dy / l * 0.5 + 0.5) * 255; img.data[k + 2] = (1 / l * 0.5 + 0.5) * 255; img.data[k + 3] = 255;
    }
    x.putImageData(img, 0, 0);
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8;
    t.repeat.set(60, 60);                       // maps have their own UV transform: tile the grain 60x
    this._detail = t; return t;
  }

  setDetail(octaves) {
    this.earth.material.defines.OCT = octaves;
    this.earth.material.needsUpdate = true;
  }

  async set(env) {
    this.current = env;
    const v = this.v;
    const sd = SUN[env].clone().normalize();
    this.sunDir.copy(sd);
    this.sunSprite.position.copy(sd).multiplyScalar(3500);
    this.bgSun.position.copy(sd).multiplyScalar(100);
    const surface = env === 'moon' || env === 'mars';
    if (env === 'lunar_orbit') await this.moon();
    if (this.current !== env) return { surface, orbit: env === 'leo' || env === 'lunar_orbit', stale: true };
    if (surface) {
      const tg = await this.terrainFor(env);
      if (this.current !== env) return { surface, orbit: false, stale: true };
      this.terrainGroup.clear();
      this.terrainGroup.add(tg);
    } else this.terrainGroup.clear();
    // backdrop
    this.earth.visible = env === 'leo' || env === 'moon' || env === 'lunar_orbit';
    if (this.moonGlobe) this.moonGlobe.visible = env === 'lunar_orbit';
    this.marsSky.visible = env === 'mars';
    this.studio.visible = env === 'earth';
    this.stars.visible = env !== 'mars' && env !== 'earth';
    this.sunSprite.visible = env !== 'earth';
    this.stars.material.uniforms.uFade.value = env === 'moon' ? 0.55 : 1;
    this.sunSprite.material.color.set(env === 'mars' ? 0xffe9d0 : 0xfff6e8);
    this.sunSprite.scale.setScalar(env === 'mars' ? 140 : 260);
    if (env === 'leo') {
      this.earth.scale.setScalar(1); this.earth.position.set(0, -1065, -250); this.earth.rotation.set(0.35, 0.8, 0.12);
    } else if (env === 'lunar_orbit') {
      this.moonGlobe.position.set(1100, -1750, -2300); this.moonGlobe.rotation.set(0.2, 2.2, 0);
      this.earth.scale.setScalar(0.05); this.earth.position.set(2600, 900, -2800);
    } else if (env === 'moon') {
      this.earth.scale.setScalar(0.06); this.earth.position.set(1500, 900, -3000);
    }
    this.marsSky.material.uniforms.uSun.value.copy(sd);
    // lighting
    const L = {
      leo: { c: 0xfffaf2, i: 2.5, hs: 0x6a8fb8, hg: 0x1b2633, hi: 0.55, env: 0.35, exp: 1.0, fog: null },
      lunar_orbit: { c: 0xfffaf2, i: 2.6, hs: 0x3a3e44, hg: 0x2a2a2a, hi: 0.18, env: 0.25, exp: 1.0, fog: null },
      moon: { c: 0xffffff, i: 3.0, hs: 0x262a30, hg: 0x3a3936, hi: 0.18, env: 0.18, exp: 1.0, fog: null },
      mars: { c: 0xffe2c4, i: 2.6, hs: 0xd7a27a, hg: 0x5a3220, hi: 0.75, env: 0.35, exp: 1.05, fog: [0xb98a64, 0.0085] },
      earth: { c: 0xffffff, i: 1.6, hs: 0x9aa4ad, hg: 0x1c1f22, hi: 0.5, env: 0.85, exp: 1.0, fog: null },
    }[env];
    this.sun.color.set(L.c); this.sun.intensity = L.i;
    this.sun.position.copy(sd).multiplyScalar(40);
    this.sun.target.position.set(0, 0, 0);
    const sc = this.sun.shadow.camera, ext = surface ? 26 : 12;
    sc.left = -ext; sc.right = ext; sc.top = ext; sc.bottom = -ext; sc.near = 1; sc.far = 100; sc.updateProjectionMatrix();
    this.hemi.color.set(L.hs); this.hemi.groundColor.set(L.hg); this.hemi.intensity = L.hi;
    v.scene.environmentIntensity = L.env;
    v.renderer.toneMappingExposure = L.exp;
    v.scene.fog = L.fog ? new THREE.FogExp2(L.fog[0], L.fog[1]) : null;
    return { surface, orbit: env === 'leo' || env === 'lunar_orbit' };
  }

  update(camera, t) {
    this.bgCamera.quaternion.copy(camera.quaternion);
    this.bgCamera.fov = camera.fov; this.bgCamera.aspect = camera.aspect; this.bgCamera.updateProjectionMatrix();
    this.earth.material.uniforms.uTime.value = t;
    if (this.current === 'leo') this.earth.rotation.y += 0.00004;
  }
}
