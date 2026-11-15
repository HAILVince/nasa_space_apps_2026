# Business case data

Two data files feed the business case. Every number has its source, page or table, date and an exact quote.

| File | What it holds | Read it with |
|---|---|---|
| `flame/data/finance.json` | 54 figures: NASA's ISS price list (crew time, cargo, stowage, private astronaut missions), NASA's own cargo cost per kg, ISS cost per year/day, CLPS lander task orders, Artemis HLS and spacesuit contracts, commercial space station awards, the space insurance market (premiums, claims, capacity, rates) and market size (OECD) | `flame.data.get_finance()`, `GET /api/flame/finance`, agent tool `fire_finance` |
| `flame/data/fire_events.json` | Real in-flight fire and smoke events with how long the crew response took (Mir 1997, ISS 2006) | `flame.data.get_fire_events()` |

## Read the figures correctly

- `kind: price` is what NASA **charges commercial users** (Table A / Table B of the NASA Commercial and Marketing
  Pricing Policy). It is not NASA's own cost.
- `kind: cost_estimate` is an audit's estimate of **NASA's own** unit cost. Example: NASA OIG puts its own cost of
  ISS cargo at about $63,200/kg (CRS-1) and $71,800/kg (CRS-2), roughly three times the $20,000/kg commercial price.
- `kind: derived` is computed here; `formula` says how (e.g. ISS cost per day = $3 billion / 365).
- `sourceLevel: secondary` means a news report of the document. Two ISS budget-split figures still are.

## Anchors for the cost-of-a-fire calculator

| Event | Crew | Response | Recovery |
|---|---|---|---|
| Mir oxygen-candle fire, 1997 | 6 | masks for 2.5 h, fire up to 14 min (sources differ) | hardware and cable insulation destroyed |
| ISS Elektron overheat, 2006 | 3 | emergency about 2 h | atmosphere scrub about 36 h; unit back online after 6 weeks |

How often: NASA counts 13 on-orbit fire or near-ignition overheat events since the 1960s, two of them grave
([ICES-2020-173, NTRS 20205000063](https://ntrs.nasa.gov/api/citations/20205000063/downloads/ICES-2020_173%20Fire%20Safety%20revised%20final%20manuscript%20-%202020%2007%2020.pdf)).

The calculator multiplies a simulated event (crew hours, days a module is closed, kg of hardware to replace) by these
prices. The crew-hours, closure-days and replaced-mass values are **our assumptions**, set from the two events above,
and must be shown as such.

## Client 2: commercial stations and their insurers

| Figure | Value | Source |
|---|---|---|
| Space insurance gross premiums | about $557M (2023), $580M (2024) | Seradata |
| Claims | net loss $1.3B in 2023; $210.8M claims in 2024 | Seradata |
| Working capacity of the whole market | $502M (2025) | Gallagher |
| Loss ratio 2025, after the SpainSat NG-2 loss | about 75% | Gallagher |
| Launch insurance | about 10% of insured value | van Oijhuizen Galhego Rosa 2013 (Acta Astronautica) |
| Third-party liability | about 1% rate on line at launch, 0.1% in orbit | Luinaud & Salmon 2023 (J. Space Safety Eng.) |
| NASA awards for commercial stations | $415.6M (three Space Act Agreements) + $140M (Axiom) | Paravano et al. 2025 (Acta Astronautica) |

Pitch point to check before using: the whole market covers only about half a billion dollars per risk. We have no
sourced insured value for a commercial station module yet, so do not state that a module exceeds it.

## Market size (OECD, The Space Economy in Figures, 2023)

| Figure | Value | Page |
|---|---|---|
| OECD government space budgets, 2022 | USD 75 billion (0.1% of OECD GDP) | 15 |
| Global space economy, excluding government procurement | USD 200-350 billion | 22 |
| NASA budget FY2023 | USD 25.4 billion | 30 |
| NASA share for space operations (ISS, transport), 2022 | 16.5% | 145 |
| US total space budget, 2022 | USD 60 billion | 146 |
| Private investment in space companies, 2021 (record) | USD 15.4 billion | 31 |
