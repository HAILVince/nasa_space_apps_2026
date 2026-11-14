import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Environments } from './environments.js';
import { Fire } from './fire.js';
import { Smoke, Airflow } from './smoke.js';

const BAKED = new Set(['Shell', 'Interior', 'FrontWall', 'SurfaceKit', 'Hatch', 'FanHousing', 'OrbitKit_Radiator', 'OrbitKit']);
const THERMAL = { uThermal: { value: 0 }, uFirePos: { value: new THREE.Vector3() }, uHeat: { value: 0 } };

function patchThermal(material) {
  material.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, THERMAL);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWPos;')
      .replace('#include <project_vertex>', '#include <project_vertex>\nvWPos=(modelMatrix*vec4(transformed,1.0)).xyz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
      varying vec3 vWPos; uniform float uThermal, uHeat; uniform vec3 uFirePos;
      vec3 inferno(float x){ x=clamp(x,0.,1.);
        vec3 a=vec3(0.0015,0.0005,0.014), b=vec3(0.258,0.039,0.406), c=vec3(0.865,0.317,0.226), d=vec3(0.988,0.998,0.645);
        return x<0.33? mix(a,b,x/0.33) : x<0.7 ? mix(b,c,(x-0.33)/0.37) : mix(c,d,(x-0.7)/0.3); }`)
      .replace('#include <tonemapping_fragment>', `if(uThermal>0.5){
          float dd=distance(vWPos,uFirePos);
          // hot plume near the source; the mixed cabin air warms only a few kelvin
          float dT=uHeat*(exp(-dd/0.45)+0.03*exp(-dd/1.6));
          float lum=clamp(dot(gl_FragColor.rgb,vec3(.3,.59,.11))*2.5,0.,1.);
          gl_FragColor.rgb=inferno(0.05+dT/320.)*(0.35+0.65*lum)*1.25;
        }
        #include <tonemapping_fragment>`);
  };
  material.customProgramCacheKey = () => 'thermal2';
}

// Quality tiers. The start tier comes from the GPU and the device; the frame time then
// steps it down (or once up) while the page runs, so every machine stays smooth.
const TIERS = {
  low: { dpr: 1.0, samples: 2, bloom: false, shadow: 0, steps: 28, smoke: 1000, earthOct: 3 },
  medium: { dpr: 1.5, samples: 4, bloom: true, shadow: 1024, steps: 44, smoke: 2000, earthOct: 4 },
  high: { dpr: 1.5, samples: 4, bloom: true, shadow: 2048, steps: 64, smoke: 3000, earthOct: 4 },
};
const ORDER = ['low', 'medium', 'high'];

function startTier(renderer) {
  const q = new URLSearchParams(location.search).get('q');
  if (TIERS[q]) return q;
  let gpu = '';
  try {
    const gl = renderer.getContext(), ext = gl.getExtension('WEBGL_debug_renderer_info');
    gpu = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)).toLowerCase();
  } catch { /* unknown GPU */ }
  const mobile = matchMedia('(pointer: coarse)').matches;
  const cores = navigator.hardwareConcurrency || 4, mem = navigator.deviceMemory || 4;
  if (/swiftshader|llvmpipe|software|basic render/.test(gpu)) return 'low';
  if (mobile || cores <= 4 || mem <= 4 || /intel|mali|adreno|powervr|apple gpu/.test(gpu)) return 'medium';
  return 'high';
}

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

export class Viewer {
  constructor(canvas, viewport, labels, opts = {}) {
    this.canvas = canvas; this.viewport = viewport; this.labels = labels;
    const r = this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.shadowMap.autoUpdate = false;           // the scene is static: redraw shadows only when it changes
    this.scene = new THREE.Scene();
    const pm = new THREE.PMREMGenerator(r);
    this.scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.03, 800);
    this.camera.position.set(9, 4.5, 12);
    // the canvas sits behind a scrolling page: the wheel scrolls the page, Ctrl/Cmd + wheel zooms
    if (!opts.wheelZoom) canvas.addEventListener('wheel', (e) => { if (!e.ctrlKey && !e.metaKey) e.stopImmediatePropagation(); }, { capture: true });
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.autoRotateSpeed = 0.35;
    this.lastInteract = performance.now();
    this.controls.addEventListener('change', () => { if (!this.controls.autoRotate) this.lastInteract = performance.now(); });
    this.calm = false;                        // set by the page while playback is paused
    this.active = true;
    this.shift = 0; this.shiftTarget = 0; this.shiftY = 0; this.shiftYTarget = 0;
    this.vw = 0; this.vh = 0;                 // viewport size, kept by resize()
    this.ptr = { x: 0, y: 0, tx: 0, ty: 0 };   // pointer parallax (px)
    this.dolly = 0; this.baseDist = null;     // scroll-linked push-in
    this.tweenMs = 2200;
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.07;
    this.controls.minDistance = 0.25;
    this.controls.maxDistance = 38;
    this.envs = new Environments(this);
    this.fire = new Fire(this.scene);
    this.smoke = new Smoke(this.scene);
    this.airflow = new Airflow(this.scene);
    this.clock = new THREE.Clock();
    this.mode = 'normal';
    this.view = 'exterior';
    this.tween = null;
    this.gravityDir = new THREE.Vector3(0, -1, 0);
    this.ventOn = true;
    this.markers = [];
    // interior lighting: LED panels along the overhead corners
    for (const x of [-2.2, 0, 2.2]) {
      const l = new THREE.PointLight(0xe9f2ff, 0.9, 5.5, 2);
      l.position.set(x, 0.78, -0.1);
      this.scene.add(l);
    }
    // HDR targets need a float-renderable format; older GPUs without it get 8-bit targets
    // instead of a black screen. MSAA is clamped to what the GPU offers.
    const ext = r.extensions;
    this.hdr = ext.has('EXT_color_buffer_half_float') || ext.has('EXT_color_buffer_float');
    this.maxSamples = r.getContext().getParameter(r.getContext().MAX_SAMPLES) || 0;
    const rt = new THREE.WebGLRenderTarget(1, 1, { type: this.hdr ? THREE.HalfFloatType : THREE.UnsignedByteType, samples: 0 });
    // a lost GPU context (driver reset, sleep) pauses the scene and rebuilds it when restored
    canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); this.lost = true; opts.onLost?.(); });
    canvas.addEventListener('webglcontextrestored', () => { this.lost = false; opts.onRestored ? opts.onRestored() : location.reload(); });
    this.composer = new EffectComposer(r, rt);
    this.bgPass = new RenderPass(this.envs.bg, this.envs.bgCamera);
    this.mainPass = new RenderPass(this.scene, this.camera);
    this.mainPass.clear = false;
    this.mainPass.clearDepth = true;
    this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.32, 0.38, 1.1);
    this.composer.addPass(this.bgPass);
    this.composer.addPass(this.mainPass);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());
    this.perf = { acc: 0, n: 0, upTried: false, since: performance.now() };
    this.scale = 1;                            // dynamic resolution, 0.55..1 of the tier's pixel ratio
    this.setTier(startTier(r));
    new ResizeObserver(() => this.resize()).observe(viewport);
    this.resize();
  }

  setTier(name) {
    const q = this.q = TIERS[name]; this.tier = name;
    const r = this.renderer;
    this.applyScale();
    const samples = Math.min(q.samples, this.maxSamples || 0);
    for (const rt of [this.composer.renderTarget1, this.composer.renderTarget2]) { rt.samples = samples; rt.dispose(); }
    this.bloom.enabled = q.bloom;
    r.shadowMap.enabled = q.shadow > 0;
    if (this.envs?.sun) {
      this.envs.sun.castShadow = q.shadow > 0;
      if (q.shadow) { this.envs.sun.shadow.mapSize.set(q.shadow, q.shadow); this.envs.sun.shadow.map?.dispose(); this.envs.sun.shadow.map = null; }
    }
    this.fire.setSteps(q.steps);
    this.smoke.setBudget(q.smoke);
    this.envs?.setDetail?.(q.earthOct);
    this.scene.traverse((o) => { if (o.material) o.material.needsUpdate = true; });
    this.shadowsDirty();
    this.resize();
  }

  applyScale() {
    const pr = Math.max(0.5, Math.min(devicePixelRatio, this.q.dpr) * this.scale);
    this.renderer.setPixelRatio(pr);
    this.composer.setPixelRatio(pr);
  }

  shadowsDirty() { this.renderer.shadowMap.needsUpdate = true; }

  // dynamic resolution: every second the render scale follows the frame time (target ~60 fps);
  // only when the smallest scale is still too slow does the quality tier step down
  // Frame-time watchdog. Resolution is never lowered (sharpness first); a machine that stays
  // slow for 3 s only loses effects (bloom, shadows, flame steps, smoke). It only ever steps
  // down, and ignores the second after a scene change, so it cannot oscillate.
  watchPerf(ms) {
    const p = this.perf, now = performance.now();
    if (ms > 250 || now < (this.quietUntil || 0)) { p.acc = 0; p.n = 0; p.since = now; return; }
    p.acc += ms; p.n += 1;
    if (now - p.since < 3000) return;
    const avg = p.acc / p.n; p.acc = 0; p.n = 0; p.since = now;
    const i = ORDER.indexOf(this.tier);
    if (avg > 24 && i > 0) { this.setTier(ORDER[i - 1]); this.quietUntil = now + 1500; }
  }
  settle(ms = 1500) { this.quietUntil = performance.now() + ms; }

  async init(progress) {
    const texLoader = new THREE.TextureLoader();
    const [gltf, ao, weave] = await Promise.all([
      new GLTFLoader().loadAsync('./assets/3d/habitat.glb', (e) => e.total && progress?.(0.2 + 0.6 * e.loaded / e.total)),
      texLoader.loadAsync('./assets/3d/habitat_ao.webp'),
      texLoader.loadAsync('./assets/img/thermal-weave.webp'),
      this.envs.preload(progress),
    ]);
    ao.flipY = false; ao.colorSpace = THREE.NoColorSpace; ao.anisotropy = 4;
    weave.wrapS = weave.wrapT = THREE.RepeatWrapping; weave.repeat.set(70, 70);
    this.habitat = gltf.scene;
    this.parts = {};
    this.habitat.traverse((o) => {
      if (!o.isMesh) return;
      let top = o; while (top.parent && top.parent !== this.habitat) top = top.parent;
      const name = top.name;
      (this.parts[name] ||= []).push(o);
      o.castShadow = true; o.receiveShadow = true;
      const m = o.material.clone();
      if (BAKED.has(name) && o.geometry.attributes.uv) { m.aoMap = ao; m.aoMapIntensity = 1.0; }
      if (m.name === 'MMOD_BetaCloth') { m.bumpMap = weave; m.bumpScale = 0.6; m.roughness = 0.82; }
      if (m.name === 'Solar_Cell') { m.map = this.solarTexture(); m.metalness = 0.55; m.roughness = 0.28; m.color.set(0xffffff); }
      if (m.name === 'Viewport_Glass') { m.transparent = true; m.opacity = 0.28; m.depthWrite = false; }
      if (m.name === 'LED_Panel') m.emissiveIntensity = 2.4;
      if (m.name === 'Display_Screen') { m.emissiveMap = this.screenTexture(); m.emissive.set(0xffffff); m.emissiveIntensity = 1.6; }
      if (/Aluminium|Steel|Kapton|Footpad/.test(m.name)) m.envMapIntensity = 1.4;
      m.userData.base = { transparent: m.transparent, opacity: m.opacity, depthWrite: m.depthWrite };
      patchThermal(m);
      o.material = m;
    });
    this.scene.add(this.habitat);
    this.shadowsDirty();
    this.mixer = new THREE.AnimationMixer(this.habitat);
    this.actions = {};
    for (const clip of gltf.animations) {
      const a = this.mixer.clipAction(clip);
      if (clip.name.startsWith('ArrayTrack')) { a.setLoop(THREE.LoopPingPong); a.timeScale = 0.4; }
      if (clip.name.startsWith('Hatch')) { a.setLoop(THREE.LoopOnce); a.clampWhenFinished = true; }
      else a.play();
      this.actions[clip.name] = a;
    }
    this.fanAction = Object.entries(this.actions).find(([k]) => k.startsWith('FanSpin'))?.[1];
    progress?.(0.95);
    this.loop();
  }

  solarTexture() {
    const c = document.createElement('canvas'); c.width = 512; c.height = 512;
    const x = c.getContext('2d');
    x.fillStyle = '#0b1a33'; x.fillRect(0, 0, 512, 512);
    for (let j = 0; j < 16; j++) for (let i = 0; i < 16; i++) {
      const g = x.createLinearGradient(i * 32, j * 32, i * 32 + 32, j * 32 + 32);
      g.addColorStop(0, '#1d3766'); g.addColorStop(1, '#0d1d3d');
      x.fillStyle = g; x.fillRect(i * 32 + 1.5, j * 32 + 1.5, 29, 29);
      x.fillStyle = 'rgba(200,210,230,.25)'; x.fillRect(i * 32 + 1.5, j * 32 + 15, 29, 0.8);
    }
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
  }

  screenTexture() {
    const c = document.createElement('canvas'); c.width = 256; c.height = 256;
    const x = c.getContext('2d');
    x.fillStyle = '#04121a'; x.fillRect(0, 0, 256, 256);
    x.strokeStyle = '#2bb3d6'; x.lineWidth = 2; x.beginPath();
    for (let i = 0; i < 256; i += 4) x.lineTo(i, 160 + 30 * Math.sin(i / 17) * Math.cos(i / 41));
    x.stroke();
    x.fillStyle = '#7fe08a'; for (let i = 0; i < 6; i++) x.fillRect(16, 20 + i * 18, 60 + 25 * ((i * 37) % 5), 8);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  }

  resize() {
    const w = this.viewport.clientWidth, h = this.viewport.clientHeight;
    if (!w || !h) return;
    this.vw = w; this.vh = h;                  // read by the frame loop: no layout reads per frame
    this.applyScale();
    this.renderer.setSize(w, h, false);
    this.composer.setSize(w, h);
    this.bloom.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.smoke.resize(h * this.renderer.getPixelRatio());
  }

  async setEnvironment(env, gFrac) {
    const info = await this.envs.set(env);
    if (info.stale) return;                    // another environment was chosen while this one loaded
    this.shadowsDirty();
    this.surface = info.surface;
    const show = (name, on) => (this.parts[name] || []).forEach((m) => { m.visible = on; });
    show('SurfaceKit', env !== 'leo' && env !== 'lunar_orbit');
    for (const k of Object.keys(this.parts)) if (k.startsWith('OrbitKit')) show(k, info.orbit);
    this.gravityFrac = gFrac;
    this.envName = env;
  }

  setMode(mode) {
    this.mode = mode;
    THERMAL.uThermal.value = mode === 'thermal' ? 1 : 0;
    this.airflow.group.visible = mode === 'airflow';
    const xr = mode === 'xray';
    for (const [name, list] of Object.entries(this.parts)) {
      const op = name === 'Shell' ? 0.07 : name.startsWith('OrbitKit') || name === 'SurfaceKit' ? 0.12 : 0.22;
      for (const m of list) {
        const mat = m.material, b = mat.userData.base;
        mat.transparent = xr ? true : b.transparent;
        mat.opacity = xr ? Math.min(op, b.opacity) : b.opacity;
        mat.depthWrite = xr ? false : b.depthWrite;
        mat.needsUpdate = true;
      }
    }
  }

  presets() {
    const a = this.anchor || new THREE.Vector3(1.5, 0, -0.9);
    const dz = this.surface ? 0.6 : 0;
    const far = THREE.MathUtils.clamp(1.3 / this.camera.aspect, 1, 2.1);   // portrait screens: step back
    const fireDir = new THREE.Vector3(0.55, 0.22, 1).normalize();
    // frame the whole flame: look at its middle from a distance that grows with its length
    const hrr = this.result ? this.result.peaks.hrr_kw : 1;
    const len = (0.04 + 0.08 * Math.pow(hrr, 0.4)) * Math.min(3, this.result?.flame.elongation || 1);
    const mid = a.clone().addScaledVector(this.fire.axis || new THREE.Vector3(0, 1, 0), len * 0.45);
    const fp = mid.clone().addScaledVector(fireDir, 1.3 + len * 1.6);
    fp.y = THREE.MathUtils.clamp(fp.y, -0.8, 0.8); fp.z = THREE.MathUtils.clamp(fp.z, -0.8, 0.85);
    return {
      exterior: { p: new THREE.Vector3(-9.8, 3.6 + dz, 13.2).multiplyScalar(far), t: new THREE.Vector3(-0.2, -0.45 - dz * 0.5, 0) },
      cutaway: { p: new THREE.Vector3(0.6, 2.4, 6.4), t: new THREE.Vector3(0.2, -0.1, -0.5) },
      interior: { p: new THREE.Vector3(-3.25, 0.12, 0.35), t: new THREE.Vector3(1.0, -0.12, -0.35) },
      fire: { p: fp, t: mid },
    };
  }

  // page integration: whether the scene renders, takes pointer input, rotates by itself and
  // where its subject sits horizontally (pixels, + = right)
  setActive(on) { this.active = on; }
  setInteractive(on) { this.controls.enabled = on; }
  // landing page: drag to turn the module, no zoom or pan; turning stops the auto-rotation for a while
  setDragOnly(on) {
    this.controls.enableZoom = !on; this.controls.enablePan = !on;
    this.dragOnly = on;
    if (!this._dragHook) {
      this._dragHook = true;
      this.controls.addEventListener('start', () => { this.userTurning = true; this.baseDist = null; this.tween = null; });
      this.controls.addEventListener('end', () => { this.userTurning = false; this.lastTurn = performance.now(); });
    }
  }
  setAutoRotate(on) { this.controls.autoRotate = on; }
  setShift(px, py = 0) { this.shiftTarget = px; this.shiftYTarget = py; }
  setPointer(nx, ny) { this.ptr.tx = nx * 26; this.ptr.ty = ny * 16; }
  setDolly(f) { this.dolly = Math.max(0, Math.min(1, f)); }
  // cinematic entry: start far out on a wide arc and fly to the view
  flyIn(name = 'exterior') {
    const pr = this.presets()[name];
    const from = pr.p.clone().sub(pr.t).applyAxisAngle(new THREE.Vector3(0, 1, 0), 0.9).multiplyScalar(3.4).add(pr.t);
    from.y += 6;
    this.camera.position.copy(from); this.controls.target.copy(pr.t); this.controls.update();
    this.view = name;
    this.tween = { p0: from, t0: pr.t.clone(), p1: pr.p, t1: pr.t, s: performance.now(), d: 4200 };
  }

  setView(name, instant = false, retarget = false) {
    if (!instant && !retarget && name === this.view && this.tween) return;     // already flying there
    this.view = name;
    const pr = this.presets()[name];
    if (!pr) return;
    const inside = name === 'interior' || name === 'fire';
    this.controls.minDistance = inside ? 0.05 : 1.5;
    this.controls.maxDistance = inside ? 3.5 : 60;
    if (instant) { this.camera.position.copy(pr.p); this.controls.target.copy(pr.t); this.controls.update(); return; }
    this.baseDist = null;
    this.tween = { p0: this.camera.position.clone(), t0: this.controls.target.clone(), p1: pr.p, t1: pr.t, s: performance.now(), d: this.tweenMs };
  }

  setScenario(result, catalog) {
    const loc = catalog.locations[result.inputs.location];
    this.anchor = new THREE.Vector3(...loc.anchor);
    this.gravityDir.set(0, -1, 0);
    result.catalogColor = catalog.materials[result.inputs.material]?.color;
    this.fire.configure(loc.anchor, result, this.gravityDir);
    this.smoke.configure(loc.anchor, result, result.atmosphere.gravity_fraction, loc.enclosure);
    THERMAL.uFirePos.value.copy(this.anchor);
    this.result = result;
    this.markers.forEach((m) => m.el.classList.toggle('is-active', m.key === result.inputs.location));
    if (this.view === 'fire') this.setView('fire', false, true);   // new source: fly there even mid-flight
  }

  setTime(t, row, dtSim) {
    this.simT = t; this.row = row;
    this.ventOn = row ? row.vent : true;
    if (dtSim < 0) this.smoke.reset();
    else this.smoke.step(Math.min(dtSim, 8), row);
    THERMAL.uHeat.value = row && row.flame > 0 ? 60 + 260 * Math.min(1, Math.sqrt(row.hrr_kw)) * row.flame : 0;
  }

  setMarkers(locations, labelFn, onPick) {
    this.labels.innerHTML = '';
    this.markers = Object.entries(locations).map(([key, loc]) => {
      const el = document.createElement('button');
      el.className = 'marker';
      el.innerHTML = '<span class="dot"></span><span class="txt"></span>';
      el.querySelector('.txt').textContent = labelFn(key);
      el.setAttribute('aria-label', labelFn(key));
      el.onclick = () => onPick(key);
      this.labels.appendChild(el);
      return { key, el, p: new THREE.Vector3(...loc.anchor) };
    });
  }

  relabel(labelFn) { this.markers.forEach((m) => { m.el.querySelector('.txt').textContent = labelFn(m.key); }); }

  updateMarkers() {
    // project with this frame's camera (its matrices are otherwise refreshed only while rendering,
    // which left the markers one frame behind and made them slide while zooming or orbiting)
    this.camera.updateMatrixWorld();
    const w = this.vw, h = this.vh;
    const v = this._mv || (this._mv = new THREE.Vector3());
    for (const m of this.markers) {
      v.copy(m.p).project(this.camera);
      const vis = v.z < 1 && Math.abs(v.x) < 1.05 && Math.abs(v.y) < 1.05;
      if (vis !== m.vis) { m.el.style.display = vis ? '' : 'none'; m.vis = vis; }
      if (!vis) continue;
      // the dot's centre sits exactly on the anchor, whatever the label width
      const x = Math.round((v.x * 0.5 + 0.5) * w * 2) / 2, y = Math.round((-v.y * 0.5 + 0.5) * h * 2) / 2;
      if (x !== m.x || y !== m.y) { m.x = x; m.y = y; m.el.style.transform = `translate3d(${x}px,${y}px,0) translate(-50%,-50%)`; }
    }
  }

  loop() {
    // ?fps=N caps the frame rate (software-rendered previews and screenshots)
    const cap = Number(new URLSearchParams(location.search).get('fps')) || 0;
    let last = 0;
    const tick = () => {
      requestAnimationFrame(tick);
      if (document.hidden || !this.active || this.lost) { this.clock.getDelta(); return; }
      const nowMs = performance.now();
      // idle (paused, nothing moving, no input for 3 s): 24 fps is plenty for the flicker
      const idle = this.calm && !this.tween && nowMs - this.lastInteract > 3000;
      const minGap = cap ? 1000 / cap : idle ? 1000 / 24 : 0;
      if (minGap && nowMs - last < minGap) return;
      if (last && !cap && !idle) this.watchPerf(nowMs - last);
      last = nowMs;
      const dt = Math.min(this.clock.getDelta(), 0.1), now = performance.now(), t = now / 1000;
      if (this.tween) {
        const k = Math.min(1, (now - this.tween.s) / this.tween.d), e = ease(k);
        this.camera.position.lerpVectors(this.tween.p0, this.tween.p1, e);
        this.controls.target.lerpVectors(this.tween.t0, this.tween.t1, e);
        if (k >= 1) { this.tween = null; this.baseDist = this.camera.position.distanceTo(this.controls.target); }
      } else if ((this.dragOnly || !this.controls.enabled) && this.baseDist && !this.userTurning) {
        // scroll-linked push-in while the page drives the camera
        const want = this.baseDist * (1 - 0.3 * this.dolly);
        const off = (this._off || (this._off = new THREE.Vector3())).copy(this.camera.position).sub(this.controls.target);
        off.setLength(off.length() + (want - off.length()) * Math.min(1, dt * 3));
        this.camera.position.copy(this.controls.target).add(off);
      }
      // horizontal frame shift: keeps the subject clear of text columns and side panels
      this.shift += (this.shiftTarget - this.shift) * Math.min(1, dt * 4);
      this.shiftY += (this.shiftYTarget - this.shiftY) * Math.min(1, dt * 4);
      const w = this.vw, h = this.vh;
      const pr = this.ptr, pk = Math.min(1, dt * 2.5);
      pr.x += (pr.tx - pr.x) * pk; pr.y += (pr.ty - pr.y) * pk;
      const ox = this.shift + pr.x, oy = this.shiftY + pr.y;
      if (Math.abs(ox) > 0.5 || Math.abs(oy) > 0.5) this.camera.setViewOffset(w, h, -ox, -oy, w, h);
      else if (this.camera.view) this.camera.clearViewOffset();
      this.controls.update();
      const c = this.camera.position;
      const inside = Math.abs(c.y) < 1.0 && Math.abs(c.z) < 1.0 && Math.abs(c.x) < 3.9;
      (this.parts.FrontWall || []).forEach((m) => { m.visible = inside || this.mode === 'xray'; });
      // the cabin fan runs only while ventilation is on
      if (this.fanAction) this.fanAction.timeScale = this.ventOn ? 1 : 0;
      this.mixer?.update(dt);
      // moving solar arrays cast moving shadows: refresh the shadow map a few times a second
      if (this.envs.sun.castShadow && (this._shadowT = (this._shadowT || 0) + dt) > 0.4) { this._shadowT = 0; this.shadowsDirty(); }
      this.fire.setState(this.row, t, this.camera, dt);
      this.airflow.update(t, this.ventOn);
      this.envs.update(this.camera, t);
      this.updateMarkers();
      this.composer.render();
    };
    tick();
  }
}
