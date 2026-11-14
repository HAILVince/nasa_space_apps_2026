// Procedural 3D Mars (visual only). No external textures: the surface is generated
// from 3D noise sampled on the sphere (seamless), plus craters, dark albedo regions
// and polar caps. Usage: <div data-mars data-res="1024" data-controls="1"></div>
import * as THREE from "three";

// ---------- noise -------------------------------------------------------------
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(1977);
const perm = new Uint8Array(512);
{
  const p = [...Array(256).keys()];
  for (let i = 255; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [p[i], p[j]] = [p[j], p[i]]; }
  for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
}
const fade = (t) => t * t * t * (t * (t * 6 - 15) + 10);
const lerp = (a, b, t) => a + (b - a) * t;
function grad(h, x, y, z) {
  const u = h < 8 ? x : y, v = h < 4 ? y : h === 12 || h === 14 ? x : z;
  return ((h & 1) ? -u : u) + ((h & 2) ? -v : v);
}
function perlin(x, y, z) {
  const X = Math.floor(x) & 255, Y = Math.floor(y) & 255, Z = Math.floor(z) & 255;
  x -= Math.floor(x); y -= Math.floor(y); z -= Math.floor(z);
  const u = fade(x), v = fade(y), w = fade(z);
  const A = perm[X] + Y, AA = perm[A] + Z, AB = perm[A + 1] + Z, B = perm[X + 1] + Y, BA = perm[B] + Z, BB = perm[B + 1] + Z;
  return lerp(
    lerp(lerp(grad(perm[AA] & 15, x, y, z), grad(perm[BA] & 15, x - 1, y, z), u),
         lerp(grad(perm[AB] & 15, x, y - 1, z), grad(perm[BB] & 15, x - 1, y - 1, z), u), v),
    lerp(lerp(grad(perm[AA + 1] & 15, x, y, z - 1), grad(perm[BA + 1] & 15, x - 1, y, z - 1), u),
         lerp(grad(perm[AB + 1] & 15, x, y - 1, z - 1), grad(perm[BB + 1] & 15, x - 1, y - 1, z - 1), u), v), w);
}
function fbm(x, y, z, oct) {
  let s = 0, a = 0.5, f = 1;
  for (let i = 0; i < oct; i++) { s += a * perlin(x * f, y * f, z * f); f *= 2.03; a *= 0.5; }
  return s;
}

// ---------- surface -----------------------------------------------------------
const PALETTE = [
  [0.00, [62, 30, 22]],    // dark basalt
  [0.35, [128, 58, 32]],   // rust
  [0.60, [176, 92, 52]],   // ochre
  [0.82, [206, 136, 92]],  // bright dust
  [1.00, [226, 176, 132]],
];
function palette(t) {
  t = Math.min(1, Math.max(0, t));
  for (let i = 1; i < PALETTE.length; i++) {
    if (t <= PALETTE[i][0]) {
      const [t0, c0] = PALETTE[i - 1], [t1, c1] = PALETTE[i], k = (t - t0) / (t1 - t0);
      return [lerp(c0[0], c1[0], k), lerp(c0[1], c1[1], k), lerp(c0[2], c1[2], k)];
    }
  }
  return PALETTE[PALETTE.length - 1][1];
}

function makeCraters(n) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const u = rand() * 2 - 1, th = rand() * Math.PI * 2, r = Math.sqrt(1 - u * u);
    const size = 0.012 + Math.pow(rand(), 3) * 0.11;
    out.push({ x: r * Math.cos(th), y: u, z: r * Math.sin(th), size });
  }
  return out;
}

function buildMaps(W) {
  const H = W / 2;
  const color = document.createElement("canvas"); color.width = W; color.height = H;
  const bump = document.createElement("canvas"); bump.width = W; bump.height = H;
  const cctx = color.getContext("2d"), bctx = bump.getContext("2d");
  const cimg = cctx.createImageData(W, H), bimg = bctx.createImageData(W, H);
  const craters = makeCraters(260);
  // crater lookup by latitude band to keep it fast
  for (let j = 0; j < H; j++) {
    const lat = Math.PI / 2 - (j + 0.5) / H * Math.PI;
    const cy = Math.sin(lat), cr = Math.cos(lat);
    const near = craters.filter((c) => Math.abs(Math.asin(Math.max(-1, Math.min(1, c.y))) - lat) < c.size * 1.6);
    for (let i = 0; i < W; i++) {
      const lon = (i + 0.5) / W * Math.PI * 2;
      const x = cr * Math.cos(lon), z = cr * Math.sin(lon), y = cy;
      const albedo = fbm(x * 1.3 + 7, y * 1.3, z * 1.3, 4);             // big dark regions
      const detail = fbm(x * 6, y * 6, z * 6, 5);
      const fine = perlin(x * 40, y * 40, z * 40) * 0.5;
      let h = 0.5 + detail * 0.55 + fine * 0.15;
      for (const c of near) {
        const d = Math.hypot(x - c.x, y - c.y, z - c.z) / c.size;
        if (d < 1.35) {
          if (d < 1) h -= (1 - d * d) * 0.35;                           // bowl
          else h += Math.max(0, 1 - Math.abs(d - 1.12) / 0.2) * 0.18;   // rim
        }
      }
      let t = 0.58 + detail * 0.45 + fine * 0.12 + (h - 0.5) * 0.35;
      t -= Math.max(0, -albedo - 0.04) * 1.6;                           // dark plains (Syrtis-like)
      let [r, g, b] = palette(t);
      const capEdge = 0.86 + fbm(x * 4, y * 4, z * 4, 3) * 0.08;      // polar caps
      const capK = Math.min(1, Math.max(0, (Math.abs(y) - capEdge) / 0.04));
      r = lerp(r, 240, capK); g = lerp(g, 236, capK); b = lerp(b, 232, capK);
      const k = (j * W + i) * 4;
      cimg.data[k] = r; cimg.data[k + 1] = g; cimg.data[k + 2] = b; cimg.data[k + 3] = 255;
      const hv = Math.min(255, Math.max(0, h * 255));
      bimg.data[k] = bimg.data[k + 1] = bimg.data[k + 2] = hv; bimg.data[k + 3] = 255;
    }
  }
  cctx.putImageData(cimg, 0, 0); bctx.putImageData(bimg, 0, 0);
  return { color, bump };
}

// ---------- scene -------------------------------------------------------------
async function mount(el) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const res = parseInt(el.dataset.res || "1024", 10);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  el.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 200);
  camera.position.set(0, 0.35, 4.2);

  const maps = buildMaps(res);
  const tex = new THREE.CanvasTexture(maps.color); tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  const bump = new THREE.CanvasTexture(maps.bump);
  const mars = new THREE.Mesh(
    new THREE.SphereGeometry(1, 128, 96),
    new THREE.MeshStandardMaterial({ map: tex, bumpMap: bump, bumpScale: 2.2, roughness: 1, metalness: 0 }));
  const tilt = new THREE.Group(); tilt.rotation.z = THREE.MathUtils.degToRad(25.2); // Mars' axial tilt
  tilt.add(mars); scene.add(tilt);

  const atmo = new THREE.Mesh(new THREE.SphereGeometry(1.045, 64, 48), new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, side: THREE.BackSide, blending: THREE.AdditiveBlending,
    uniforms: { glow: { value: new THREE.Color(0xff9466) } },
    vertexShader: "varying vec3 vN; varying vec3 vP; void main(){ vN = normalize(normalMatrix*normal); vec4 p = modelViewMatrix*vec4(position,1.0); vP = p.xyz; gl_Position = projectionMatrix*p; }",
    fragmentShader: "uniform vec3 glow; varying vec3 vN; varying vec3 vP; void main(){ float f = pow(1.0 - abs(dot(normalize(-vP), vN)), 3.0); gl_FragColor = vec4(glow, f*0.55); }",
  }));
  scene.add(atmo);

  const starGeo = new THREE.BufferGeometry(), pts = [];
  for (let i = 0; i < 1500; i++) {
    const u = rand() * 2 - 1, th = rand() * Math.PI * 2, r = Math.sqrt(1 - u * u), R = 60 + rand() * 30;
    pts.push(R * r * Math.cos(th), R * u, R * r * Math.sin(th));
  }
  starGeo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.18, sizeAttenuation: true, transparent: true, opacity: 0.8 })));

  const sun = new THREE.DirectionalLight(0xfff1e0, 2.6); sun.position.set(-5, 2.5, 4); scene.add(sun);
  scene.add(new THREE.AmbientLight(0x6a4a5a, 0.35));

  let controls = null;
  if (el.dataset.controls) {
    const { OrbitControls } = await import("three/addons/OrbitControls.js");
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.enablePan = false; controls.minDistance = 1.6; controls.maxDistance = 9;
  }

  function resize() {
    const w = el.clientWidth || 300, h = el.clientHeight || w;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(el); resize();

  let visible = true;
  new IntersectionObserver((e) => { visible = e[0].isIntersecting; }).observe(el);
  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    const dt = clock.getDelta();
    if (!visible) return;
    if (!reduced) mars.rotation.y += dt * 0.06;
    controls && controls.update();
    renderer.render(scene, camera);
  });
  el.classList.add("mars-ready");
}

for (const el of document.querySelectorAll("[data-mars]")) {
  mount(el).catch((e) => console.warn("Mars render failed", e));
}
