// Ray-marched flame volume. Its shape follows the simulation: a round, dim, blue diffusion
// flame in microgravity, a stretched, sooty, yellow plume under gravity, skewed downstream
// by forced flow. Colour comes from the computed flame temperature (blackbody) and soot.
import * as THREE from 'three';

const VERT = /* glsl */`
  varying vec3 vLocal; varying vec3 vOrigin;
  uniform vec3 uCamLocal;
  void main(){ vLocal=position; vOrigin=uCamLocal; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`;

const FRAG = /* glsl */`
  precision highp float;
  varying vec3 vLocal; varying vec3 vOrigin;
  uniform float uTime, uStrength, uSize, uElong, uSoot, uTempK, uBlue, uFlicker, uBox, uSkew;
  float h3(vec3 p){ p=fract(p*0.3183099+.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
  float vn(vec3 x){ vec3 i=floor(x), f=fract(x); f=f*f*(3.0-2.0*f);
    return mix(mix(mix(h3(i),h3(i+vec3(1,0,0)),f.x),mix(h3(i+vec3(0,1,0)),h3(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(h3(i+vec3(0,0,1)),h3(i+vec3(1,0,1)),f.x),mix(h3(i+vec3(0,1,1)),h3(i+vec3(1,1,1)),f.x),f.y),f.z); }
  float fbm(vec3 p){ float a=.5,s=0.; for(int i=0;i<4;i++){ s+=a*vn(p); p=p*2.07+3.1; a*=.5; } return s; }
  vec3 blackbody(float T){                       // approximate Planckian locus, linear RGB
    T=clamp(T,800.,3500.)/100.;
    float r = T<=66. ? 1. : clamp(1.293*pow(T-60.,-0.1332),0.,1.);
    float g = T<=66. ? clamp(0.390*log(T)-0.632,0.,1.) : clamp(1.130*pow(T-60.,-0.0755),0.,1.);
    float b = T>=66. ? 1. : (T<=19. ? 0. : clamp(0.543*log(T-10.)-1.196,0.,1.));
    return pow(vec3(r,g,b),vec3(2.2));
  }
  // signed distance-like field of the flame in metres (axis +Y), plus inner depth
  float field(vec3 p, out float s){
    float R=uSize*0.5;
    float L=R*2.0*uElong;
    vec3 q=p;
    q.y+=L*0.5;                                    // the flame is centred in its box
    s=clamp(q.y/L,0.,1.);
    float y=p.y;
    float taper=mix(1.0, 1.0-0.62*s*s, smoothstep(1.05,1.8,uElong));
    q.x-= uSkew*R*s*s*1.5;
    float r=length(q.xz)/(max(taper,0.08));
    float d=length(vec2(r, y*(2.0*R/L)))-R;
    float t=uTime;
    float rise=mix(0.12,2.6,smoothstep(1.0,2.0,uElong));
    float n=fbm(vec3(p.x*11., p.y*6.-t*rise*3.4, p.z*11.)+t*0.2);
    d+= (n-0.5)*R*mix(0.35,0.9,s)*uFlicker;
    return d;
  }
  vec2 box(vec3 ro, vec3 rd){ vec3 inv=1./rd; vec3 t0=(-vec3(uBox)-ro)*inv, t1=(vec3(uBox)-ro)*inv;
    vec3 a=min(t0,t1), b=max(t0,t1); return vec2(max(max(a.x,a.y),a.z), min(min(b.x,b.y),b.z)); }
  void main(){
    vec3 ro=vOrigin, rd=normalize(vLocal-vOrigin);
    vec2 tb=box(ro,rd); tb.x=max(tb.x,0.);
    if(tb.x>=tb.y || uStrength<0.002) discard;
    const int N=56; float dt=(tb.y-tb.x)/float(N);
    vec3 col=vec3(0.); float trans=1.;
    float R=uSize*0.5;
    vec3 hot=blackbody(uTempK*0.95);
    vec3 sootc=blackbody(uTempK*0.78+150.);
    vec3 blue=vec3(0.06,0.20,1.0);
    float jit=h3(vec3(gl_FragCoord.xy,uTime));
    for(int i=0;i<N;i++){
      vec3 p=ro+rd*(tb.x+(float(i)+jit)*dt);
      float s; float d=field(p,s);
      if(d<R*0.25){
        float shell=exp(-pow(d/(R*0.16),2.));               // thin reaction zone
        float inner=smoothstep(0.0,-R*0.6,d);               // fuel-rich core
        float sootZone=inner*smoothstep(0.03,0.22,s)*uSoot;
        // blue CH* chemiluminescence: the whole sheet in 0 g, only the base of a buoyant flame;
        // it is hidden where soot glows, so the two never mix into pink
        float base=uElong>1.3 ? 1.0-smoothstep(0.05,0.22,s) : 1.0;
        float sootMask=smoothstep(0.0,0.25,sootZone);
        vec3 e=blue*shell*uBlue*base*(1.-sootMask)*1.6 + hot*shell*(1.-uBlue)*(1.-base*0.6)*0.5 + sootc*sootZone*2.4;
        e+= sootc*inner*(1.0-smoothstep(0.0,0.12,s))*uSoot*1.2; // bright root on the fuel surface
        e*= (1.0 - 0.6*smoothstep(0.75,1.0,s));             // tip fades
        float k=(shell*0.7+sootZone*1.3)*dt/R*0.55;
        col+=e*k*trans;
        trans*=exp(-sootZone*dt/R*0.5);
      }
    }
    col*=uStrength*1.6;
    gl_FragColor=vec4(col, 1.);
  }`;

function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d'), g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, 'rgba(255,255,255,.9)'); g.addColorStop(0.25, 'rgba(255,255,255,.25)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

export class Fire {
  constructor(scene) {
    this.group = new THREE.Group();
    this.uniforms = {
      uTime: { value: 0 }, uStrength: { value: 0 }, uSize: { value: 0.2 }, uElong: { value: 1 }, uSoot: { value: 0.3 },
      uTempK: { value: 1800 }, uBlue: { value: 0.5 }, uFlicker: { value: 0.5 }, uBox: { value: 0.5 }, uSkew: { value: 0 },
      uCamLocal: { value: new THREE.Vector3() },
    };
    this.mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.ShaderMaterial({
      uniforms: this.uniforms, vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending, side: THREE.BackSide,
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
    this.light.castShadow = false;
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
          float xs=(vObj.x+0.5)*uLen; float front=uFront;
          float burnt=smoothstep(front+0.006,front-0.004,xs);
          diffuseColor.rgb=mix(diffuseColor.rgb, vec3(0.03,0.025,0.02), burnt*0.95);`)
        .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
          totalEmissiveRadiance += vec3(1.0,0.35,0.06)*exp(-pow((xs-front)/0.01,2.))*uGlow*1.2;`);
    };
    this.group.add(this.sample);
    this.sample.castShadow = true;
    scene.add(this.group);
    this.params = null;
    this.state = { strength: 0, hrr: 0, front: 0 };
  }

  configure(anchor, result, gravityDir) {
    const f = result.flame, inp = result.inputs;
    this.group.position.set(...anchor);
    const elong = Math.max(1, Math.min(f.elongation, 4.2));
    const buoy = f.buoyancy;
    const soot = Math.min(1.4, f.soot_index);
    // flame axis: buoyant "up" blended with the cabin flow (+X); in orbit only flow
    const flowDir = new THREE.Vector3(1, 0, 0);
    const up = gravityDir.clone().multiplyScalar(-1);
    const flowShare = Math.min(1, result.flammability.forced_flow_cm_s / 30);
    const axis = up.clone().multiplyScalar(buoy).add(flowDir.clone().multiplyScalar(buoy > 0.05 ? flowShare * 0.35 : 1));
    if (axis.lengthSq() < 1e-4) axis.set(0, 1, 0);
    axis.normalize();
    this.pivot.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis);
    const u = this.uniforms;
    u.uElong.value = buoy < 0.05 ? 1 + 0.6 * flowShare : Math.min(elong, 3.0);
    u.uSoot.value = soot * (buoy < 0.05 ? 0.55 : 1.0);
    u.uTempK.value = f.temperature_k;
    // blue chemiluminescence dominates dim, low-soot and microgravity flames
    u.uBlue.value = Math.max(0.15, Math.min(0.95, 0.85 - soot * 0.55 + (buoy < 0.05 ? 0.25 : 0) - (f.temperature_k - 1700) / 2500));
    u.uFlicker.value = buoy < 0.05 ? 0.25 : 0.55 + 0.45 * buoy;
    u.uSkew.value = buoy > 0.05 ? flowShare * 0.6 : 0;
    this.params = { buoy, elong, maxHrr: Math.max(result.peaks.hrr_kw, 0.02), soot };
    // sample strip along the fuel (+X), sized from the location's fuel bed
    const loc = result.inputs.location;
    const len = { avionics_rack: 0.9, cable_standoff: 1.4, crew_quarters: 0.9, galley: 0.36, stowage: 0.5, glovebox: 0.15 }[loc] || 0.5;
    const wid = { avionics_rack: 0.03, cable_standoff: 0.04, crew_quarters: 0.5, galley: 0.26, stowage: 0.4, glovebox: 0.04 }[loc] || 0.1;
    const thick = { ptfe_wire: 0.02, nomex: 0.01, polyethylene: 0.006, pet_film: 0.004 }[inp.material] || 0.025;
    this.sample.scale.set(len, thick, wid);
    this.sample.position.set(len / 2 - 0.03, -0.035, 0);
    this.sampleU.uLen.value = len;
    this.sampleU.uColor.value.set(result.catalogColor || '#cccccc');
    this.len = len;
    this.axis = axis.clone();
  }

  setState(row, timeSec, camera) {
    // row: one interpolated sample of the server time series
    const p = this.params; if (!p) return;
    const hrr = row ? row.hrr_kw : 0, strength = row ? row.flame : 0;
    // flame width; buoyant flame length follows Heskestad (L = 0.235 Q^0.4 m, Q in kW)
    const size = 0.04 + 0.08 * Math.pow(Math.max(hrr, 0.001), 0.4);
    const s = Math.min(1, strength) * Math.min(1, 0.25 + Math.pow(hrr / p.maxHrr, 0.35));
    const u = this.uniforms;
    u.uTime.value = timeSec;
    u.uStrength.value = s;
    u.uSize.value = size;
    const box = size * Math.max(1.25, u.uElong.value * 1.1 + 0.3);
    u.uBox.value = 0.5;
    this.mesh.scale.setScalar(box * 1.15);
    const flameLen = size * u.uElong.value;
    this.mesh.position.set(0, flameLen * 0.5 - size * 0.12, 0);
    this.mesh.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(this.mesh.matrixWorld).invert();
    u.uCamLocal.value.copy(camera.position).applyMatrix4(inv);
    // outside the box draw its front faces (so walls behind the flame cannot hide it), inside the back faces
    const inside = Math.max(Math.abs(u.uCamLocal.value.x), Math.abs(u.uCamLocal.value.y), Math.abs(u.uCamLocal.value.z)) < 0.5;
    const side = inside ? THREE.BackSide : THREE.FrontSide;
    if (this.mesh.material.side !== side) { this.mesh.material.side = side; this.mesh.material.needsUpdate = true; }
    // the box is unit-sized in object space; field() works in metres, so rescale inside
    u.uSize.value = size / (box * 1.15);
    const flick = 1 + 0.12 * Math.sin(timeSec * 23.0) * Math.sin(timeSec * 7.3) * (p.buoy > 0.05 ? 1 : 0.3);
    const col = new THREE.Color().setRGB(1.0, 0.55 + 0.25 * u.uBlue.value, 0.25 + 0.6 * u.uBlue.value);
    this.light.color.copy(col);
    this.light.intensity = s * (0.08 + 0.55 * Math.pow(hrr, 0.5)) * flick;
    this.light.position.copy(new THREE.Vector3(0, size * 0.8, 0).applyQuaternion(this.pivot.quaternion));
    this.glow.material.color.copy(col);
    this.glow.material.opacity = Math.min(0.35, s * 0.3);
    this.glow.scale.setScalar(size * 2.4);
    this.glow.position.copy(this.light.position);
    this.sampleU.uFront.value = row ? Math.min(this.len, row.front_m) : 0;
    this.sampleU.uGlow.value = s;
    this.group.visible = true;
  }
}
