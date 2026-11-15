# Blender asset pipeline

Every 3D asset of the fire lab is built from code by `build_assets.py`, so the model can be
reviewed, changed and rebuilt like the rest of the repository. Geometry follows
`blackfox/physics/habitat_layout.json`, the same file the simulator uses for fire locations,
vents and the smoke detector.

| Output (`frontend/assets/3d/`) | What |
|---|---|
| `habitat.glb` | HAB-01 module as a cutaway: aluminium pressure shell with ring frames and stringers, gold MLI, quilted beta-cloth MMOD blankets, CBM berthing rings with bolts, yellow EVA handrails, grapple fixture; inside 24 ISPR racks (stowage lockers, avionics, experiment, crew quarters, glovebox), corner standoffs with cable bundles, water lines and IMV duct, LED light strips, galley table, stowage bags, inlet diffuser, return grille and smoke detector; surface kit (saddles, legs, footpads, ladder) and orbit kit (truss, solar wings, radiator); empties `anchor_*` / `vent_*` |
| animations in the GLB | `FanSpin` (cabin fan, 2 rev/s), `HatchOpen`, `ArrayTrack` (solar wings follow the Sun) |
| `habitat_ao.webp` | ambient occlusion baked with Cycles into one atlas (UV0 of every baked object) |
| `terrain_moon_*`, `terrain_mars_*` | 240 m terrain: height map (16 bit split over R and G), albedo baked in Cycles from a procedural regolith shader x baked AO (rocks included), rock placements in JSON |
| `rocks.glb` | four faceted rock variants used as instances |
| `moon_globe.webp`, `moon_globe_height.webp` | lunar albedo (maria, craters, rays) and height for the lunar-orbit backdrop |

| `frontend/assets/img/bg-hero-mobile.webp` | phone hero still: the module over the Earth's limb, portrait framing (828x1792), Cycles (`build_cinematic.py`) |

Polygon budget and fit: `habitat.glb` is kept around 35k triangles (it was 76k) so it loads and
renders smoothly on laptops and phones. Bevels are a single chamfer and skipped on sub-3 cm sheets,
round parts use 8-16 sides with smooth shading, and revolves step 7.5 degrees. Parts never pass
through each other and nothing floats or leaves a slit: every part either rests exactly on the face
of the one under it or leaves clear space, flat parts on the round hull sit on chord planes of the
shared 7.5 degree grid, and only joints (feet, brackets, fittings) are seated a few millimetres into
their base where it cannot be seen. Keep new parts to that standard; `python blender/build_assets.py
--only habitat` prints the polygon count per object.

```bash
pip install bpy                     # or use a Blender 4.2+ install
python blender/build_assets.py      # full quality (AO 4096 px, 160 samples) - takes a while on CPU
python blender/build_assets.py --quick              # fast preview build
python blender/build_assets.py --only habitat       # habitat | terrain | globe
blender -b -P blender/build_assets.py -- --quick    # with the Blender application
```

Coordinates: the layout and the web viewer are Y-up metres (glTF); Blender is Z-up, so a layout
point `(x, y, z)` is Blender `(x, -z, y)`. If you move a rack or a fire location, edit
`habitat_layout.json`, rebuild, and the simulator, the 3D markers and the model stay in step.

## Hero film and stills (`build_cinematic.py`, `hero_cinematic.blend`)

On the site only the phone still is used (desktop shows the scroll-scrubbed video, `js/scrub.js`);
the 60 fps loop can be rendered and encoded again for other uses (pitch, social). It is rendered from the shipped `habitat.glb` (so it always shows the lab's module) in
Cycles: one hard sun (0.53 deg disc), a weak blue Earthshine fill, AgX, a procedural Earth (fBm
continents, clouds, glossy water) with a limb-glow shell, a sparse Voronoi star field. The lab's
exterior look is kept: front wall off (cutaway), orbit kit on. The camera sways 7 deg around the module
with a slight push-in; every motion is a sine of the loop phase, so frame 240 is frame 0 again and the
loop needs no cross-fade. The seed is fixed so the denoised noise does not shimmer.

```bash
python blender/build_cinematic.py --test                    # low-res framing check (desktop + phone)
python blender/build_cinematic.py --stills /tmp/hs          # posters, 128 samples (~5 min on 4 cores)
python blender/build_cinematic.py --frames /tmp/hf --res 1600x900 --samples 24 --step 3   # 80 keys, ~27 s each on 4 cores
python blender/build_cinematic.py --save hero_cinematic.blend                   # editable scene
scripts/encode_hero.sh /tmp/hf /tmp/hs /tmp/master          # 60 fps WebM + MP4 (interpolated), WebP posters, master
```

## Handrail and cable tubes

`tube()` sweeps a ring along a polyline. It used to orient each ring with `to_track_quat` on the
averaged tangent: at the 90 degree elbows of the 120+ handrails the rings rolled against each other
(twisted quads, 44 faces whose shading normals pointed into the tube) and the elbow was pinched to
cos 45 = 71 % of the tube's thickness. Rings are now carried along by parallel transport and the elbow
ring is the miter section of the incoming tube (stretched by 1/cos of half the bend angle), so the tube
keeps its thickness and every quad is planar. Triangle count is unchanged (35,572); the AO atlas was
re-baked with it.
