// Ray-marched flame volume. Its shape follows the simulation: a round, dim, blue diffusion
// flame in microgravity, a stretched, sooty, yellow plume under gravity, skewed downstream
// by forced flow. Colour comes from the computed flame temperature (blackbody) and soot.
//
// Stability rules (the earlier version "swam" and sparkled):
//  - the ray-march box is sized once per scenario from the peak heat release, never per frame;
//  - every field and noise coordinate is in metres, so the pattern does not rescale as the
//    flame grows or shrinks;
//  - the dither is fixed per pixel (no per-frame random), and strength is smoothed in time;
//  - soot absorbs: the volume outputs premultiplied colour + coverage, so sooty tips darken
//    what is behind them instead of washing it out.
import * as THREE from 'three';

const VERT = /* glsl */`
  varying vec3 vLocal;
  void main(){ vLocal=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`;

const FRAG = /* glsl */`
  precision highp float;
  varying vec3 vLocal;
  uniform vec3 uCamLocal;
  uniform float uTime, uStrength, uSize, uElong, uSoot, uTempK, uBlue, uFlicker, uSkew, uBoxM, uBaseY, uRise, uScale, uGain;
  float h3(vec3 p){ p=fract(p*0.3183099+.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
  float vn(vec3 x){ vec3 i=floor(x), f=fract(x); f=f*f*(3.0-2.0*f);
    return mix(mix(mix(h3(i),h3(i+vec3(1,0,0)),f.x),mix(h3(i+vec3(0,1,0)),h3(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(h3(i+vec3(0,0,1)),h3(i+vec3(1,0,1)),f.x),mix(h3(i+vec3(0,1,1)),h3(i+vec3(1,1,1)),f.x),f.y),f.z); }
  float fbm(vec3 p){ float a=.5,s=0.; for(int i=0;i<4;i++){ s+=a*vn(p); p=p*2.03+vec3(3.1,1.7,5.3); a*=.5; } return s; }
  vec3 blackbody(float T){                        // approximate Planckian locus, linear RGB
    T=clamp(T,800.,3500.)/100.;
    float r = T<=66. ? 1. : clamp(1.293*pow(T-60.,-0.1332),0.,1.);
    float g = T<=66. ? clamp(0.390*log(T)-0.632,0.,1.) : clamp(1.130*pow(T-60.,-0.0755),0.,1.);
    float b = T>=66. ? 1. : (T<=19. ? 0. : clamp(0.543*log(T-10.)-1.196,0.,1.));
    return pow(vec3(r,g,b),vec3(2.2));
  }
  // distance-like field in metres; axis +Y, base at uBaseY (metres from the box centre)
  float field(vec3 p, out float s){
    float R=uSize*0.5;
    float L=max(uSize*uElong, 1e-3);
    float y=p.y-uBaseY;                            // 0 at the fuel surface
    s=clamp(y/L,0.,1.);
    float taper=mix(1.0, 1.0-0.62*s*s, smoothstep(1.05,1.8,uElong));
    vec3 q=p; q.x-=uSkew*R*s*s*1.5;
    float r=length(q.xz)/max(taper,0.08);
    float d=length(vec2(r, (y-L*0.5)*(2.0*R/L)))-R;
    // turbulence in metres; advected along the axis faster when buoyancy is strong
    vec3 np=vec3(p.x, p.y-uTime*uRise, p.z)*uScale;
    float n=fbm(np+vec3(0.,0.,uTime*0.15));
    d+=(n-0.5)*R*mix(0.35,0.95,s)*uFlicker;
    return d;
  }
  vec2 hitBox(vec3 ro, vec3 rd){ vec3 inv=1./rd; vec3 t0=(-0.5-ro)*inv, t1=(0.5-ro)*inv;
    vec3 a=min(t0,t1), b=max(t0,t1); return vec2(max(max(a.x,a.y),a.z), min(min(b.x,b.y),b.z)); }
  void main(){
    if(uStrength<0.002) discard;
    vec3 ro=uCamLocal, rd=normalize(vLocal-uCamLocal);
    vec2 tb=hitBox(ro,rd); tb.x=max(tb.x,0.);
    if(tb.x>=tb.y) discard;
    const int N=64; float dt=(tb.y-tb.x)/float(N);
    float dtm=dt*uBoxM;                             // step length in metres
    vec3 cBlue=vec3(0.), cHot=vec3(0.); float trans=1.;
    float R=max(uSize*0.5,1e-3);
    vec3 hot=blackbody(uTempK*0.95);
    vec3 sootc=blackbody(uTempK*0.8+120.);
    vec3 blue=vec3(0.05,0.18,1.0);
    float jit=h3(vec3(floor(gl_FragCoord.xy),7.0));  // fixed per pixel: no sparkle
    for(int i=0;i<N;i++){
      vec3 p=(ro+rd*(tb.x+(float(i)+jit)*dt))*uBoxM;   // metres from the box centre
      float s; float d=field(p,s);
      if(d<R*0.3){
        // heat: 0 at the edge, 1 deep in the flame; the upper part breaks into tongues
        float h=smoothstep(R*0.1,-R*0.55,d);
        float brk=fbm(vec3(p.x,p.y-uTime*uRise*1.6,p.z)*uScale*1.7+vec3(5.2,1.3,7.7));
        h*=1.0-smoothstep(0.42,1.0,s)*smoothstep(0.3,0.72,brk+0.25*s);
        float shell=exp(-pow(d/(R*0.15),2.));          // thin reaction zone
        float base=uElong>1.3 ? 1.0-smoothstep(0.04,0.22,s) : 1.0;   // CH*: base only, or the whole sheet in 0 g
        float sootOn=uSoot*smoothstep(0.02,0.16,s);
        float Tl=mix(1050.,uTempK,pow(h,0.65));          // local temperature: red rim, white-yellow core
        vec3 eh=blackbody(Tl)*h*sootOn*2.4 + hot*shell*(1.-uBlue)*0.25;
        vec3 eb=blue*shell*uBlue*base*1.4*(1.0-0.6*smoothstep(0.75,1.0,s));
        float k=dtm/R*1.1;
        cBlue+=eb*k*trans; cHot+=eh*k*trans;
        // cooled soot above the luminous zone absorbs (dark tips of sooty flames)
        trans*=exp(-sootOn*smoothstep(0.6,1.0,s)*(1.0-h)*smoothstep(0.0,-R*0.2,d)*dtm/R*1.2);
        if(trans<0.02) break;
      }
    }
    // luminous soot outshines CH*: where it glows the blue sheet is not seen (no pink mixing)
    float lh=dot(cHot,vec3(0.3,0.59,0.11));
    vec3 col=(cHot+cBlue*(1.0-smoothstep(0.0,0.35,lh)))*uStrength*uGain;
    float cover=(1.-trans)*uStrength;
    gl_FragColor=vec4(col, cover);                   // premultiplied: ONE, ONE_MINUS_SRC_ALPHA
  }`;

function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d'), g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, 'rgba(255,255,255,.85)'); g.addColorStop(0.3, 'rgba(255,255,255,.18)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

const SAMPLE = {
  len: { avionics_rack: 0.9, cable_standoff: 1.4, crew_quarters: 0.9, galley: 0.36, stowage: 0.5, glovebox: 0.15 },
  wid: { avionics_rack: 0.03, cable_standoff: 0.04, crew_quarters: 0.5, galley: 0.26, stowage: 0.4, glovebox: 0.04 },
  thick: { ptfe_wire: 0.02, nomex: 0.01, polyethylene: 0.006, pet_film: 0.004 },
};
const flameWidth = (hrr) => 0.04 + 0.08 * Math.pow(Math.max(hrr, 0.001), 0.4);   // m; length via elongation (Heskestad-like)

export class Fire {
  constructor(scene) {
    this.group = new THREE.Group();
    this.group.visible = false;
    this.uniforms = {
      uTime: { value: 0 }, uStrength: { value: 0 }, uSize: { value: 0.2 }, uElong: { value: 1 }, uSoot: { value: 0.3 },
      uTempK: { value: 1800 }, uBlue: { value: 0.5 }, uFlicker: { value: 0.5 }, uSkew: { value: 0 },
      uBoxM: { value: 1 }, uBaseY: { value: -0.3 }, uRise: { value: 0.2 }, uScale: { value: 10 }, uGain: { value: 3 },
      uCamLocal: { value: new THREE.Vector3() },
    };
    this.mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.ShaderMaterial({
      uniforms: this.uniforms, vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false,
      blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
      blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneMinusSrcAlphaFactor, side: THREE.FrontSide,
    }));
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 10;
    this.pivot = new THREE.Group();
    this.pivot.add(this.mesh);
    this.group.add(this.pivot);
    this.glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: 0xff8a3a, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
    this.glow.renderOrder = 11;
    this.group.add(this.glow);
    this.light = new THREE.PointLight(0xff9a50, 0, 6, 2);
    this.group.add(this.light);
    // the burning sample: a strip of the material with a char front
    this.sampleU = { uFront: { value: 0 }, uColor: { value: new THREE.Color(0xdddddd) }, uLen: { value: 1 }, uGlow: { value: 0 } };
    this.sample = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ roughness: 0.8 }));
    this.sample.material.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, this.sampleU);
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vObj;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nvObj=position;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vObj; uniform float uFront,uLen,uGlow; uniform vec3 uColor;')
        .replace('vec4 diffuseColor = vec4( diffuse, opacity );', `vec4 diffuseColor = vec4( uColor, opacity );
          float xs=(vObj.x+0.5)*uLen;
          float burnt=smoothstep(uFront+0.006,uFront-0.004,xs);
          diffuseColor.rgb=mix(diffuseColor.rgb, vec3(0.03,0.025,0.02), burnt*0.95);`)
        .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
          totalEmissiveRadiance += vec3(1.0,0.35,0.06)*exp(-pow((xs-uFront)/0.01,2.))*uGlow*1.2;`);
    };
    this.sample.castShadow = true;
    this.group.add(this.sample);
    scene.add(this.group);
    this.params = null;
    this.smooth = { s: 0, hrr: 0 };
    this._inv = new THREE.Matrix4();
    this._v = new THREE.Vector3();
    this.axis = new THREE.Vector3(0, 1, 0);
  }

  configure(anchor, result, gravityDir) {
    const f = result.flame, inp = result.inputs;
    this.group.position.set(...anchor);
    const buoy = f.buoyancy;
    const soot = Math.min(1.4, f.soot_index);
    // flame axis: buoyant "up" blended with the cabin flow (+X); in orbit the flow alone
    const flowShare = Math.min(1, result.flammability.forced_flow_cm_s / 30);
    const up = gravityDir.clone().multiplyScalar(-1);
    const axis = up.multiplyScalar(buoy).add(new THREE.Vector3(1, 0, 0).multiplyScalar(buoy > 0.05 ? flowShare * 0.35 : flowShare));
    if (axis.lengthSq() < 1e-4) axis.set(0, 1, 0);
    axis.normalize();
    this.axis.copy(axis);
    this.pivot.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis);
    const u = this.uniforms;
    const elong = buoy < 0.05 ? 1 + 0.6 * flowShare : Math.min(Math.max(1, f.elongation), 3.0);
    u.uElong.value = elong;
    u.uSoot.value = soot * (buoy < 0.05 ? 0.35 : 1.0);
    u.uTempK.value = f.temperature_k;
    // 0 g: the reaction sheet is blue (CH*), soot glows only inside; 1 g: blue only at the base
    u.uBlue.value = buoy < 0.05 ? 0.9 : THREE.MathUtils.clamp(0.85 - soot * 0.55 - (f.temperature_k - 1700) / 2500, 0.15, 0.9);
    u.uFlicker.value = buoy < 0.05 ? 0.25 : 0.55 + 0.45 * buoy;
    // HDR gain: buoyant sooty flames are far brighter than a lit cabin; 0 g flames are dim and blue
    u.uGain.value = buoy < 0.05 ? 1.6 : 1.5 + 0.9 * Math.min(1, soot);
    u.uSkew.value = buoy > 0.05 ? flowShare * 0.6 : 0;
    // one fixed box per scenario, big enough for the peak flame
    const sizeMax = flameWidth(Math.max(result.peaks.hrr_kw, 0.02));
    const lenMax = sizeMax * elong;
    const half = Math.max(lenMax * 0.5 + sizeMax * 0.35, sizeMax * 0.85);
    const boxM = half * 2.0;
    const centreY = lenMax * 0.5 - sizeMax * 0.15;
    this.mesh.scale.setScalar(boxM);
    this.mesh.position.set(0, centreY, 0);
    u.uBoxM.value = boxM;
    u.uBaseY.value = -centreY - sizeMax * 0.15;     // fuel surface, metres from the box centre
    u.uScale.value = 6.0 / sizeMax;                  // a few turbulent cells across the flame
    u.uRise.value = buoy < 0.05 ? 0.012 + 0.05 * flowShare : 0.22 + 0.45 * buoy;   // m/s, visual
    this.params = { buoy, maxHrr: Math.max(result.peaks.hrr_kw, 0.02), sizeMax };
    // sample strip along the fuel (+X)
    const loc = inp.location;
    const len = SAMPLE.len[loc] || 0.5, wid = SAMPLE.wid[loc] || 0.1, thick = SAMPLE.thick[inp.material] || 0.025;
    this.sample.scale.set(len, thick, wid);
    this.sample.position.set(len / 2 - 0.03, -0.035, 0);
    this.sampleU.uLen.value = len;
    this.sampleU.uColor.value.set(result.catalogColor || '#cccccc');
    this.len = len;
    this.smooth.s = 0;
    this.smooth.hrr = 0;
    this.group.visible = true;
  }

  setState(row, timeSec, camera, dt = 1 / 60) {
    const p = this.params; if (!p) return;
    const targetHrr = row ? row.hrr_kw : 0;
    const targetS = row ? Math.min(1, row.flame) * Math.min(1, 0.3 + Math.pow(targetHrr / p.maxHrr, 0.35)) : 0;
    // smooth the steps of the 2-s simulation series
    const k = 1 - Math.exp(-dt * 6);
    this.smooth.s += (targetS - this.smooth.s) * k;
    this.smooth.hrr += (targetHrr - this.smooth.hrr) * k;
    const s = this.smooth.s, hrr = this.smooth.hrr;
    const u = this.uniforms;
    u.uTime.value = timeSec;
    u.uStrength.value = s;
    u.uSize.value = Math.min(flameWidth(hrr), p.sizeMax);
    // camera in box space, and which faces to draw: outside -> front faces (walls behind the
    // flame cannot hide it), inside -> back faces. Changing the side needs no recompile.
    this.mesh.updateMatrixWorld();
    this._inv.copy(this.mesh.matrixWorld).invert();
    const c = u.uCamLocal.value.copy(camera.position).applyMatrix4(this._inv);
    this.mesh.material.side = Math.max(Math.abs(c.x), Math.abs(c.y), Math.abs(c.z)) < 0.5 ? THREE.BackSide : THREE.FrontSide;
    const flick = 1 + 0.1 * Math.sin(timeSec * 23.0) * Math.sin(timeSec * 7.3) * (p.buoy > 0.05 ? 1 : 0.3);
    const col = this._col || (this._col = new THREE.Color());
    if (p.buoy < 0.05) col.setRGB(0.35, 0.55, 1.0); else col.setRGB(1.0, 0.5 + 0.2 * u.uBlue.value, 0.2 + 0.3 * u.uBlue.value);
    this.light.color.copy(col);
    this.light.intensity = s * (0.06 + 0.24 * Math.sqrt(Math.max(hrr, 0))) * flick;
    this.light.position.copy(this._v.set(0, u.uSize.value * 0.8, 0).applyQuaternion(this.pivot.quaternion));
    this.glow.material.color.copy(col);
    this.glow.material.opacity = Math.min(0.14, s * (p.buoy < 0.05 ? 0.1 : 0.14));
    this.glow.scale.setScalar(u.uSize.value * 2.4);
    this.glow.position.copy(this.light.position);
    this.sampleU.uFront.value = row ? Math.min(this.len, row.front_m) : 0;
    this.sampleU.uGlow.value = s;
  }
}
