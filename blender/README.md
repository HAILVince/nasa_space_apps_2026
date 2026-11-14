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
