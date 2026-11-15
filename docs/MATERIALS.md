# Spacecraft materials in the CFD fire models: review

Scope: the 12 materials of the teammate's spacecraft solver
(`blackfox/db/knowledge/Spacecraft_Cabin_Fire/src/solver.js`, also used by the living-quarters habitat)
and which material each furnishing uses. Reviewed 14 Nov 2026. Nothing in the teammate's data has been
changed; the proposed changes below wait for the team's decision.

Since 15 Nov 2026 the CFD tab's spacecraft model runs the teammate's newer v5 engine
(`blackfox/db/knowledge/spacecraft_fire/fire_core/`, the engine of `spacecraft_cabin_fire.html`), which has
its own material table; this review still describes the v4 table that the living-quarters habitat uses.

## 1. Material properties: consistent with typical published values

The solver's own notes say most limits are typical handbook values (ASTM D2863 limiting oxygen index,
LOI) rather than knowledge-base measurements, with the 0 g limit set 1.5-3 points lower
(NTRS 20080034883). Checked against typical published ranges; heat of combustion is `s x 13.1 MJ/kg`.

| Material | LOI (1 g) | 0 g limit | Heat of combustion | Typical published | Verdict |
|---|---|---|---|---|---|
| Polyethylene (wire insulation) | 17.4 % | 16 % | 43 MJ/kg | LOI ~17.4, 43-46 MJ/kg | consistent |
| PTFE (Teflon) | 95 % | 92 % | 5.0 MJ/kg | LOI >95, ~4-6 MJ/kg | consistent |
| Kapton (polyimide) | 37 % | 34 % | 25 MJ/kg | LOI ~37 | consistent |
| Silicone rubber | 29 % | 26.5 % | 15 MJ/kg | LOI 26-30+ (depends on filler) | consistent |
| Polycarbonate | 26.5 % | 24 % | 31 MJ/kg | LOI 25-27, ~31 MJ/kg | consistent |
| Pyrell PU foam (flame-retarded) | 22 % | 20 % | 26 MJ/kg | FR PU foams ~22-26 | plausible, assumed |
| Nylon (Velcro, webbing) | 24 % | 22 % | 30 MJ/kg | LOI 21-28, ~30 MJ/kg | consistent |
| Cotton | 18.5 % | 16.5 % | 16 MJ/kg | LOI ~18-18.5, ~16 MJ/kg | consistent |
| Nomex | 28.5 % | 24 % | 27.5 MJ/kg | LOI 28-30 | consistent (marked ASSUMED in the solver) |
| PMMA | 17.3 % | 16.6 % | 25 MJ/kg | LOI ~17.3, ~25 MJ/kg | consistent, fitted to ISS data |
| Paper / cellulose | 18.5 % | 14.5 % | 16 MJ/kg | LOI ~18-19 | consistent |
| SIBAL (cotton-fiberglass) | 19 % | — | 16 MJ/kg | NASA test fabric | fitted to BASS-II |

The SIBAL, PMMA and Nomex flame-spread and limit fits come from NASA BASS, BASS-II, Saffire and the
Olson & Ferkul 2012 tables; the others are handbook-based and the solver says so in each `src` note.

## 2. Which material each furnishing uses: four to discuss

| Item | Uses | Assessment | Proposal |
|---|---|---|---|
| L1 avionics rack wire harness | polyethylene | Crewed US spacecraft wiring is mostly cross-linked ETFE (Tefzel) or PTFE / polyimide insulation, chosen to pass NASA-STD-6001; polyethylene is not typical. As a worst case it is defensible, but it should be labelled so. | Add ETFE (LOI about 30-32, about 14 MJ/kg) and make it the default, or default to PTFE and keep PE as the worst-case option |
| N4 galley food packaging | paper | ISS food packaging is mostly multilayer plastic pouches (polyester / foil / polyethylene laminate); paper is a stand-in. | Default to the existing `pe` option, or label "paper-like packaging" |
| N5 node closeout curtain | SIBAL | SIBAL is a NASA flammability test fabric, not a cabin furnishing; curtains and closeouts are usually Nomex. | Default to Nomex |
| L6 glovebox window | PMMA | Not verified here: glovebox and port windows may be polycarbonate instead. | Check the hardware source; the `pc` option already exists |

Consistent with typical practice: CTB stowage bags (Nomex), sleeping bag (Nomex), crew clothing (cotton),
Velcro (nylon), laptop packing (Pyrell foam), wipes and checklists (paper), cable tray (PTFE), EVA suit
outer layer (Nomex as a stand-in for the Ortho-fabric blend), hatch seal (silicone), experiment rack
panel (polycarbonate, a plausible worst case).

## 3. The living-quarters habitat

`frontend/js/cfd/solver_living.js` uses the same 12 materials. Its wire harness is polyethylene for the
same reason as L1 (worst case); it changes together with L1 once the team decides.
