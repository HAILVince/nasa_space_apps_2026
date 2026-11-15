# fire_core — shared spacecraft fire engine (v5)

One engine, several geometries. `engine.js` is pure JavaScript with no DOM. It runs in a Web Worker in the pages and in Node for tests and validation. Each geometry is a layout in `layouts.js`.

| Layout | Used by |
|---|---|
| `ship` | Lab module, Node with crew quarters, Airlock, in 3D: `fire_sim_ship/spacecraft_cabin_fire.html` |
| `ship2d` | The same vehicle as a vertical section along its length, one cell deep (`dim: 2`): `fire_sim_ship/spacecraft_cabin_fire_2d.html` |
| `saffire` | A Saffire flow duct in a sealed Cygnus-sized cabin: `validate_saffire.js` |

## What it solves
- **Gas flow:** variable-density LES with a Smagorinsky turbulence model, semi-Lagrangian advection and a red-black SOR pressure projection. The divergence source includes thermal expansion and mass sources. Sealed compartments carry a background pressure.
- **Combustion:** mixing-controlled, with an FDS-style critical flame temperature. CO₂ agent raises the mixture heat capacity.
- **Radiation:** P1 approximation for incident radiation G, with soot (1862 f_v T) plus gas absorption and Marshak wall conditions.
- **Solids:**
  - Thin surfaces are lumped. Thick panels (PMMA, polycarbonate, silicone) use implicit 8-node conduction.
  - Flame existence comes from a flame-temperature model.
  - Spread: de Ris opposed spread with gas properties at the flame film temperature. Thin concurrent spread is ∝ U φⁿ, thick concurrent spread is ∝ U q″²/(kρc ΔT²).
- **Species:** O₂, fuel, soot, CO, HCN, HF, CO₂ agent and water-mist liquid. The 0 g CO and smoke yields of cotton fabrics come from Saffire. Soot scales ∝ P.
- **Ventilation:** recirculating, with a particulate filter. Return grilles carry smoke detectors.
- **Suppression:**
  - CO₂ portable extinguisher: dilution, cooling and a mass source.
  - Fine water mist: evaporation on available heat, plus surface wetting.
  - Vent-to-vacuum valves: choked outflow, compartment expansion, and a sink flow that stirs the fire.
- **Crew:** members react to the alarm (15 s awake, 60 s asleep) and move to a safe module through open hatches. They accumulate fractional effective dose (ISO 13571 / Purser): CO, HCN, hypoxia at sea-level-equivalent partial pressure, convective and radiant heat, CO₂ hyperventilation, and the HF irritant concentration (FEC).
- **Scripting:** `command({do:...})` is the single entry point for actions, and every action is logged with its time. `setScript(list)` replays a timed list.

## Calibration (and only this)
| Constant | Data |
|---|---|
| Thin concurrent coefficient | Saffire-1, 1.8 mm/s |
| Thin O₂ exponent n | Saffire VI-2, 4.05 mm/s |
| Thick concurrent coefficient | Saffire VI-3, 0.38 mm/s |
| SIBAL quench parameter | BASS-II quench speeds |
| PMMA limits | ISS PMMA (pmc-5760683) |
| Kapton, silicone, nylon 1 g upward limits | NASA-STD-6001 Test 1 MOCs (NTRS 20110008636) |
| Cotton-fabric 0 g CO and smoke yields; cargo heat sink | Saffire IV-1 CO rise, alarm time and pressure rise |

Everything else in the validation table and `validation_results.json` is a prediction.

## Commands
```
node test_ship.js 0.15 240 L1 severe iss '[{"t":30,"do":"power"},{"t":40,"do":"co2"}]'
node validate_saffire.js 0.1 1     # whole-model Saffire runs + grid convergence → validation_results.json
```
Run the 2D section with `LAYOUT=ship2d node test_ship.js 0.075 240 L1 severe iss`. Rebuild both spacecraft pages with `python ../fire_sim_ship/src/build.py`.

## 2D mode
With `dim: 2` the domain is one cell deep. Its front and back faces are symmetry planes: no flux, no wall heat loss and no radiation loss. Every item spans the slice, so heat release is per slice of depth h. Valve areas are scaled to the slice depth, so venting takes as long as in 3D.
