# How the Black Fox fire simulation works / Как работает симуляция пожара Black Fox

- [English](#english)
- [Русский](#русский)

---

<a id="english"></a>

# English

## 1. What you see on the website

The **Simulator** page has three tabs. They show two different fire models:

| Tab | What it runs | What it is for |
|---|---|---|
| **3D cabin** | The site's own fast model: a flammability and spread calculation on the server (`blackfox/physics/fire.py`) plus a browser-side 2D spread model. It is shown on a 3D habitat. | A quick "will it burn, how fast, when does the alarm go off" answer for any scenario. The scenario panel on the left and the Start button drive it, and the right column shows its result. |
| **Spacecraft 2D** | The teammate's full **Spacecraft Cabin Fire** simulator, as one vertical slice along the vehicle (7.5 cm cells). | Seeing exactly how flame, smoke and crew move. |
| **Spacecraft 3D** | The same simulator for the whole vehicle in 3D (15 cm cells). | The realistic picture: smoke and airflow in every direction, the vehicle in orbit or on a surface. |

In the **Spacecraft 2D** and **Spacecraft 3D** tabs the lab's scenario panel is hidden. Its place is taken by the simulator's own controls: fire origin, crew response, emergency depressurisation and cabin atmosphere.

Most of this document explains the Spacecraft simulator (the 2D and 3D tabs), because that is the detailed physics model. Section 11 explains the 3D cabin tab.

## 2. The spacecraft

The vehicle is representative of a crewed station segment. It is not a copy of one real spacecraft.

| Compartment | Description |
|---|---|
| **Lab module** | A US-Lab-style module: a ring of equipment racks around a central aisle. |
| **Avionics rack bay** | A closed space inside a rack, with its own cooling fan and grilles to the aisle. |
| **Node and galley** | A connecting module with a galley table. |
| **Crew quarters, port and starboard** | Two small sleeping cabins in the Node, each with a door and a fan. |
| **Airlock** | At the far end, with its own hatch. |

The model also includes:
- **Hatches and doors:** Lab–Node, Node–Airlock and both crew-quarters doors. Each can be open or closed.
- **Ventilation:** supply diffusers that blow air in, return grilles that take it back, and smoke detectors at the returns, as on the ISS.
- **Vent valves:** one per module, for emergency depressurisation.
- **Four astronauts:** the commander in the Lab, one flight engineer in the Node, and two asleep in the crew quarters.

**Fire origins:** 14 real kinds of items, for example rack wire harness, cable tray, experiment panel, stowage bags, laptop foam, wipes and checklists, glovebox window, sleeping bag, clothing, Velcro, galley food packaging, closeout curtain, EVA suit and hatch seal. Each item can be made of one of several of the 12 spacecraft materials: polyethylene, PTFE (Teflon), Kapton, silicone, polycarbonate, PMMA (acrylic), polyurethane foam, nylon, Nomex, cotton, paper and SIBAL fabric.

**Ways to start a fire:**
- **Open flame:** lights the item directly.
- **Electrical overheat:** 15 kW/m² from inside. Usually smoulders and smokes.
- **Severe overheat:** 40 kW/m². Can ignite, like an overloaded wire.

**Atmospheres:**

| Preset | Oxygen | Pressure | Gravity |
|---|---|---|---|
| ISS cabin | 21 % | 101 kPa | 0 g |
| Exploration atmosphere (planned for future vehicles) | 34 % | 56.5 kPa | 0 g |
| Mars transit | 26.5 % | 70.3 kPa | 0 g |
| Lunar lander | 34 % | 56.5 kPa | 0.165 g |
| Mars surface | 26.5 % | 70.3 kPa | 0.378 g |
| ISS, fans off | 21 % | 101 kPa | 0 g |

You can also set any custom combination of gravity, oxygen and pressure.

## 3. The basic idea: a grid of cells and small time steps

The cabin is cut into small cubes ("cells"): 15 cm in 3D (about 71,000 cells) or 7.5 cm in the 2D slice. Each cell stores:
- gas temperature and velocity;
- the amount of oxygen, fuel vapour, soot (smoke), CO, HCN, HF, CO₂ agent and water mist;
- for solid cells: the material, its surface temperature, how much of it has burnt, and its flame state (none, heating, burning, out or burnt).

Every time step (up to 0.25 simulated seconds; shorter when the air moves fast), the engine updates every cell in this order:

1. **Airflow:** the fans push air, hot gas expands and rises if there is gravity, and the flow is made consistent with the walls and hatches.
2. **Transport:** heat, oxygen, fuel vapour, smoke and toxic gases are carried by the flow and mixed. The ventilation returns air through its filter.
3. **Solids:** each surface heats up. The engine checks whether a flame can exist there, how fast it spreads to neighbouring cells, and how fast the material burns and releases vapour, smoke, CO, HCN and HF.
4. **Extinguishers and venting:** CO₂, water mist and vent valves act.
5. **Combustion:** where fuel vapour meets oxygen and the mixture is hot enough, it burns and releases heat. The pressure of each sealed compartment follows the heat released.
6. **Radiation:** flames and hot smoke radiate heat to walls and to other items, preheating them.
7. **Crew:** each astronaut checks the alarm, moves, and breathes in a dose.

The engine is plain JavaScript and runs in a background thread (Web Worker) in the browser. On an ordinary laptop CPU it runs at about 8× real time; no GPU is needed.

## 4. The physics, step by step

### 4.1 Airflow (gas flow)
- The air obeys the **Navier–Stokes equations** for a gas whose density changes with temperature: hot gas is light, and in gravity it rises.
- Small-scale turbulence is represented by the **Smagorinsky model**, a standard method in fire simulation.
- Hot gas expands. A **pressure projection** step makes the flow obey mass conservation, including this expansion and the gas added by extinguishers or removed by venting.
- **Ventilation recirculates**, as on the ISS: air passes a particle filter and is blown back in. Smoke particles are removed, but CO, HCN and the oxygen deficit stay in the cabin.
- When a hatch is closed, that compartment becomes **sealed** and has its own pressure. A fire inside raises it, so smoke and pressure are trapped.

### 4.2 Combustion
- Burning is **mixing-controlled**: the rate depends on how fast fuel vapour and oxygen mix, and every kilogram of oxygen used releases 13.1 MJ.
- An **extinction check** (the same approach as NASA/NIST's FDS code) lets a mixture burn only if it can reach the critical flame temperature of 1600 K. This is why fires go out when oxygen drops or the agent cools the gas.
- **CO₂ agent** makes the gas harder to heat, so it acts like a lower oxygen level.

### 4.3 Radiation
- Heat radiation is solved with the **P1 approximation**.
- Soot and combustion gases absorb and emit radiation. Smokier gas radiates more.
- About 30 % of a flame's heat leaves as radiation. It can preheat items far away, and walls absorb it.

### 4.4 Solid materials and flame spread
This is the heart of the model.

**Thin vs thick items.** Thin items (fabric, paper, wire insulation) heat up as a whole. Thick panels (PMMA, polycarbonate, silicone) conduct heat inward, which is computed through the thickness at 8 points.

**Can a flame exist here?** The model computes a flame temperature from three things: oxygen, the local air speed, and pressure. A flame exists only if:
- it is hot enough, so it is not quenched. In still or very slow air, a flame loses too much heat by radiation and goes out;
- the air is not too fast, so it is not blown off.

This single rule reproduces the effects of oxygen, airflow and pressure seen in NASA tests.

**How fast does it spread?** There are two directions:
- **Against the airflow (opposed spread):** slow. It is computed from de Ris's classic theory for thin fuels.
- **With the airflow (concurrent spread):** faster. It grows with air speed and flame temperature. Its constants are fitted to flight data.

**How fast does it burn?** The heat reaching the surface (from its own flame, radiation and electrical overheat), minus the heat removed (by water mist and by conduction), divided by the energy needed to turn the solid into vapour.

### 4.5 Smoke and toxic gases
- Each material releases soot (smoke), CO, HCN and HF in fixed proportions (yields).
- In 0 g, flames are weak and near their limits, so they make **much more CO**. Saffire found about 0.034 kg of CO per kg of cotton in 0 g, against about 0.004 on Earth. The model blends between the 0 g and 1 g values as gravity changes.
- CO rises further when a compartment runs short of oxygen.
- **Visibility** is calculated from the smoke density.
- **Smoke alarms** trigger at an extinction of 0.1 per metre.

## 5. Why fire in microgravity is different

- **No buoyancy.** Hot gas does not rise, so there is no natural "chimney" pulling fresh air into the flame. A flame lives or dies on the **fan airflow**.
- **Fans off.** In still air many flames go out by themselves, which is why the crew turns the fans off. Some materials keep smouldering, though.
- **Smoke goes where the fans carry it.** It does not rise to a ceiling. That is why the ISS has detectors in the ventilation returns.
- **More CO.** Weak flames produce more carbon monoxide.
- **Oxygen-enriched, low-pressure cabins** (34 % O₂ at 56.5 kPa) let many more materials burn.

The simulator shows all of this directly: the same material can burn or go out depending on the airflow, oxygen and pressure.

## 6. Crew and survival

- The four astronauts react to the smoke alarm: after 15 s if awake, 60 s if asleep. On the website's 2D tab, whoever is in the burning compartment reacts at once.
- They move through open hatches to a safe module, spread out there, and the last one closes the hatch toward the fire.
- Each astronaut accumulates a **fractional effective dose (FED)**, the ISO 13571 / Purser method, from four sources: CO and HCN, low oxygen, heat, and the extra breathing caused by CO₂. Low oxygen is measured as sea-level-equivalent partial pressure, so a vented module is deadly.
- **FED 0.3 means impairment and FED 1 means incapacitation.** A separate irritant measure covers HF.
- A hatch closed too early can **trap someone** with the fire.

## 7. What the crew can do

| Action | What happens in the model |
|---|---|
| **Cut power** | Stops an electrical overheat. |
| **Fans off** | Removes the airflow that feeds the flame, but smoke stops being filtered. |
| **Close hatches or doors** | Seals a compartment: it traps smoke and pressure, and can trap crew. |
| **Alert crew** | Everyone starts moving sooner. |
| **Masks on** | The crew breathe from oxygen-supplied sets for 15 minutes. |
| **CO₂ extinguisher** | About 2.7 kg over 45 s. It dilutes oxygen and cools the gas; the air is not breathable without masks. |
| **Water-mist extinguisher** | About 2 kg over 50 s. It evaporates on the heat and wets surfaces; the air stays breathable. |
| **Vent to vacuum** | The last resort. Air flows out through a valve and the flame dies from low pressure. Venting is slow, can fan the fire at first, and kills anyone left inside. |

A **guidance panel** under the view changes with the situation (prevention, act now, evacuate and isolate, all clear). Its "Do it" buttons perform the action. There are also **fast-forward** buttons (to ignition, to alarm, +1 min, +5 min), **replay**, run comparison, CSV export and a training quiz.

## 8. Where the numbers come from: calibration

All constants come from the project's knowledge base of NASA records (NTRS, Europe PMC, TechPort). Only a few constants were **fitted** to measurements; everything else is a **prediction**.

| Fitted constant | Measurement it was fitted to |
|---|---|
| Spread speed with the airflow, thin fabric | Saffire-1: SIBAL fabric, 0 g, 21.7 % O₂, 20 cm/s air → 1.8 mm/s |
| How spread speed grows with oxygen | Saffire VI-2: 31 % O₂, 54 kPa → 4.05 mm/s |
| Spread speed with the airflow, thick PMMA | Saffire VI-3: 10 mm PMMA → 0.38 mm/s |
| SIBAL flame limits | BASS-II quench speeds (1 cm/s at 21 % O₂, 5 cm/s at 16 %) |
| PMMA limits | ISS PMMA tests |
| Kapton, silicone and nylon limits | NASA-STD-6001 Test 1 |
| CO and smoke yields of cotton fabrics in 0 g | Saffire IV-1 (CO rise, alarm time, pressure rise) |

**Saffire** was NASA's series of large fire experiments flown inside empty Cygnus cargo vehicles after they left the ISS. It is the only data on large fires in real spacecraft.

## 9. How good is it: validation

The model was tested against measurements it was **not** fitted to:
- **Of 22 independent checks, 18 are within a factor of 2 of the measurement, and 8 are within 30 %.**
- Examples: Saffire-2 spread of 2.1 and 2.6 mm/s measured against 1.91 and 2.34 mm/s in the model; lunar-gravity spread (LUCI) of 0.92–1.1 mm/s against 1.10 mm/s.
- The whole 3D model re-creates each Saffire flight fire in a sealed cabin of the measured size, and compares spread, heat, CO, pressure rise and alarm time.
- **Grid study:** heat release is close to converged. The spread speed still falls as cells get smaller, so the live 15 cm grid probably overstates spread by about 25 %.

The full validation table, a predicted-vs-measured chart and the grid study are shown at the bottom of the 3D page.

## 10. Honest limitations

- 15 cm cells are larger than a real flame, so flames are modelled below the grid scale.
- Toxic gases come from fixed yields, not detailed chemistry. Only cotton fabrics have measured 0 g yields.
- Most material limits come from handbook values (LOI). Only SIBAL, PMMA, Kapton, silicone and nylon have measured ones.
- Extinguisher amounts and valve sizes are representative, not real hardware specifications.
- At low pressure the smoke alarm comes 2–4× too early compared with Saffire.
- Crew behaviour is a simple rule (react, then move away). Real crews follow procedures and fight the fire.
- **This is a teaching and research tool, not an operational procedure.**

## 11. The 3D cabin tab (the site's own quick model)

The 3D cabin tab answers "how dangerous is this fire" in a second rather than simulating every cell:

1. **Can it burn?** The material's NASA-STD-6001 maximum oxygen concentration is interpolated at the cabin pressure. It is lowered by up to 3 % O₂ as gravity goes to zero, and raised steeply in nearly still air, where radiation quenches the flame.
2. **How fast?** Spread correlations from NASA drop-tower tests give the spread rate, a burning-rate model gives the heat release, and Thornton's rule gives the oxygen use.
3. **What happens to the air?** Product yields give the CO and smoke, and a two-zone cabin model gives the time for smoke to reach the detector.
4. **Response:** turning off the ventilation slows the flame but does not put it out at once, as seen in Saffire V.
5. In the browser, a separate **2D spread model** (taken unchanged from a teammate's habitat simulator) runs alongside it. Its numbers are saved with each run.
6. The result appears in the right-hand column: verdict, spread, alarm time, and the Before/After comparison. The **SI assistant** can read the scenario and the result.

## 12. How the spacecraft tabs are put on the website

- The teammate's pages are files in `blackfox/db/knowledge/spacecraft_fire/fire_sim_ship/`:
  - `spacecraft_cabin_fire_2d.html` is served at `/fire-sim`;
  - `spacecraft_cabin_fire.html` is served at `/fire-sim-3d`.
- The server sends them **unchanged** from that folder, so a new upload of either file is live after the next deploy (about a minute after it reaches `main`).
- Inside the tabs (`?embed=1`):
  - the page's title header is hidden;
  - its controls column is moved to the left, in place of the lab's scenario panel.
- The **2D tab** adds a few things on top of the teammate's page:
  - **Automatic start:** the fire starts by itself in a sleeping bag in the port crew quarters, in the exploration atmosphere. There it burns long enough for the fans to carry the smoke through the Node into the Lab. Clicking the map does not start fires.
  - **Crew rules:** the crew react to the alarm (or to Alert crew), not to the first flame anywhere. Whoever is in the burning compartment reacts at once. They spread out in the safe module, and the hatch toward the fire is closed once everyone is safe.
  - **Smoke shading:** smoke is drawn on a log scale, so thin smoke at alarm level is visible. Only the picture changes, not the physics.
- The **3D tab** shows the full page with all its own controls.

## 13. How the simulation is built

### 13.1 Technology
- **Language:** plain JavaScript. There are no frameworks and no build tools beyond one small Python script, and nothing needs installing.
- **Engine** (`fire_core/engine.js`, about 740 lines): pure calculation with no screen code. The same file runs in the browser and in Node.js, so tests and validation use exactly the code the page uses.
- **Geometry** (`fire_core/layouts.js`): the vehicle is described as data, not drawn by hand:
  - compartments, hatches, vents, valves, items and crew positions are given as boxes and simple shape tests in metres;
  - the engine turns them into cells at whatever cell size is chosen. This is how one engine serves the 3D ship, the 2D section and the Saffire validation cabin.
- **3D picture:** three.js (WebGL):
  - the hull is drawn as see-through cylinders;
  - racks, items, vents and hatches are drawn as many small boxes in one batch (instanced meshes);
  - hot gas and smoke are point clouds with a custom shader;
  - the astronauts are simple figures, and Earth, Moon or Mars is drawn in the background.
- **2D picture:** the slice is painted pixel by pixel on an HTML canvas. You choose the field to show (temperature, smoke, oxygen, CO and others), and arrows show the airflow.

### 13.2 How the engine is organised
- **Cells:** the domain is a 3D array with one extra layer of "ghost" cells around it for the walls. Each cell is gas, wall or fuel. Each quantity (temperature, velocity, oxygen and so on) is one flat number array (`Float64Array`) for speed.
- **Building the grid:** at start the engine:
  - marks every cell from the layout;
  - finds which cells belong to which compartment, and which gas regions are sealed off from each other;
  - computes the fan airflow once;
  - runs 30 "warm-up" steps so the air is already moving at time zero.
- **Time step:** the step length adapts to the fastest air, so that air never crosses more than two cells in one step (between 0.03 and 0.25 s). This keeps the calculation stable.
- **Numerical methods:**
  - **semi-Lagrangian advection:** each cell looks back along the flow to see where its air came from. It is stable even with large steps;
  - **implicit diffusion;**
  - **red-black SOR:** an iterative solver for the pressure, which makes the flow conserve mass;
  - **P1 radiation:** solved with the same kind of iterative solver.
- **Commands:** every action (ignite, extinguisher, close hatch, vent, and so on) goes through one `command()` function, which logs it with its time. This is what makes replay, scripted scenarios and the "Do it" buttons possible.

### 13.3 How the page runs it
- The engine runs in a **Web Worker** (a background thread), so the page never freezes. The worker:
  - steps the engine toward a target time: wall-clock time multiplied by the chosen speed (×2, ×8, ×32);
  - works in slices of about 45 ms;
  - about 7 times a second, sends the page a frame with all fields as compact arrays.
- If the computer cannot keep up, the simulation **runs slower instead of skipping physics**.
- **Fast-forward** (to ignition, to alarm, +1 or +5 min) runs the engine as fast as possible and checks the stop condition after every step.
- **Recording:** one row of numbers per simulated second (for charts, comparison and CSV), and a compressed 3D snapshot every 5 s (for replay).
- **One file:** `src/build.py` glues the page sources, the engine, the worker code and the validation results into a single HTML file. The engine and worker are embedded as text and started from it. That is why the page opens by double-click with no server.
- **Self-test:** opening the page with `#autotest` ignites, extinguishes and reports PASS or FAIL in the page title.

### 13.4 How the physics was put together and checked
1. **Data first.** The project's knowledge base holds NASA records (NTRS reports, Europe PMC papers, TechPort): Saffire, BASS, LUCI, NASA-STD-6001 material limits, extinguisher and depressurisation studies. Each material in the engine lists its sources.
2. **Sub-models from published theory:** de Ris flame spread, FDS-style combustion and extinction, P1 radiation, ISO 13571 / Purser toxic dose.
3. **Calibration on a small, declared set** of measurements (section 8). Everything else stays a prediction.
4. **Validation offline:** `validate_saffire.js` runs in Node. It re-creates each Saffire flight fire in a sealed cabin with the measured volume, compares the results with the measurements at several cell sizes, and writes `validation_results.json`. `build.py` embeds that file in the page, where the validation table and charts read it.
5. **Fixing what validation found.** Six real model defects were found this way and fixed, for example double-counted fuel mass, fires that could not spread in 0 g, and detectors that missed smoke in 0 g.

### 13.5 How the website adds it (Black Fox side)
- The backend is **FastAPI** (Python). The `/fire-sim` and `/fire-sim-3d` routes read the teammate's HTML file and add only:
  - a small "back to the simulator" bar, or, inside the tab, CSS that hides the page header and moves its controls to the left;
  - for the 2D tab, a few exact text replacements (crew rules and smoke shading) and the automatic-ignition script.
- **Safety net for the replacements:** each one must match the teammate's file exactly once. If his file changes and a match is lost, none of them are applied and the page runs as he wrote it. A test reports the mismatch.
- The pages are shown in an **iframe**. The server allows that only on the site's own pages (`Content-Security-Policy: frame-ancestors 'self'`).
- **Tests** (pytest and Node) check that the routes serve the files unchanged apart from these additions, and that the tabs exist. Every push to `main` deploys to the live site within about a minute.

## 14. Where the code is

```
blackfox/db/knowledge/spacecraft_fire/
  README.md                     full technical report (equations, validation, sources)
  fire_core/engine.js           the physics engine
  fire_core/layouts.js          geometries: 3D ship, 2D section, Saffire validation cabin
  fire_core/validate_saffire.js validation against Saffire → validation_results.json
  fire_sim_ship/spacecraft_cabin_fire.html      3D simulator page
  fire_sim_ship/spacecraft_cabin_fire_2d.html   2D simulator page
  fire_sim_ship/src/build.py    rebuilds both pages from the engine and page sources
app/main.py                     serves /fire-sim and /fire-sim-3d (and the 2D tab's crew and smoke changes)
frontend/js/sim2d_embed.js      the 2D tab's automatic ignition
blackfox/physics/fire.py        the 3D cabin tab's quick model
```

**Main sources:** NASA NTRS 20170008805 (Saffire-1 and Saffire-2), 20260001992 (Saffire IV–VI heat and smoke), 20150008962 (BASS-II), 20110008636 (NASA-STD-6001 limits), 20260003546 (risks of depressurisation), 20130011664 and 20110012896 (ISS water-mist extinguisher), 20250010653 (LUCI), ISO 13571 / Purser (toxic dose), and McGrattan et al. (FDS).

---

<a id="русский"></a>

# Русский

## 1. Что вы видите на сайте

На странице **Simulator** три вкладки. Они показывают две разные модели пожара:

| Вкладка | Что работает | Для чего |
|---|---|---|
| **3D cabin** (3D кабина) | Собственная быстрая модель сайта: расчёт горючести и распространения на сервере (`blackfox/physics/fire.py`) плюс 2D-модель распространения в браузере. Показывается на 3D-модели жилого модуля. | Быстрый ответ: «загорится ли, как быстро, когда сработает сигнализация». Ею управляют панель сценария слева и кнопка Start, а результат показан в правой колонке. |
| **Spacecraft 2D** (Корабль 2D) | Полный симулятор **Spacecraft Cabin Fire** нашего товарища по команде: один вертикальный срез вдоль корабля (ячейки 7,5 см). | Видно, как именно движутся пламя, дым и экипаж. |
| **Spacecraft 3D** (Корабль 3D) | Тот же симулятор для всего корабля в 3D (ячейки 15 см). | Реалистичная картина: дым и воздушные потоки во всех направлениях, корабль на орбите или на поверхности. |

Во вкладках **Spacecraft 2D** и **Spacecraft 3D** панель сценария лаборатории скрыта. На её месте стоят собственные элементы управления симулятора: источник пожара, действия экипажа, аварийная разгерметизация и атмосфера кабины.

Большая часть этого документа объясняет симулятор корабля (вкладки 2D и 3D), потому что это подробная физическая модель. Вкладка 3D cabin описана в разделе 11.

## 2. Корабль

Корабль типовой, похожий на сегмент пилотируемой станции. Это не копия какого-то реального корабля.

| Отсек | Описание |
|---|---|
| **Лабораторный модуль** | Модуль вроде американского «Лаба»: кольцо приборных стоек вокруг центрального прохода. |
| **Отсек авионики** | Закрытое пространство внутри стойки, со своим вентилятором охлаждения и решётками в проход. |
| **Узловой модуль (Node) с камбузом** | Соединительный модуль со столом для еды. |
| **Каюты экипажа, левая и правая** | Две маленькие спальные каюты в узловом модуле, у каждой дверь и вентилятор. |
| **Шлюз** | В дальнем конце, со своим люком. |

В модели также есть:
- **Люки и двери:** Лаб–Узел, Узел–Шлюз и двери обеих кают. Каждый можно открыть или закрыть.
- **Вентиляция:** приточные диффузоры, которые подают воздух, вытяжные решётки, которые его забирают, и датчики дыма на вытяжке, как на МКС.
- **Сбросные клапаны:** по одному на модуль, для аварийной разгерметизации.
- **Четыре астронавта:** командир в Лабе, один бортинженер в Узле и двое спят в каютах.

**Источники пожара:** 14 реальных типов предметов, например жгут проводов в стойке, кабельный лоток, панель эксперимента, сумки хранения, поролон упаковки ноутбука, салфетки и чек-листы, окно перчаточного бокса, спальный мешок, одежда, липучка, упаковка еды на камбузе, занавеска, скафандр и уплотнитель люка. Для каждого предмета можно выбрать один из нескольких материалов из 12 космических: полиэтилен, PTFE (тефлон), каптон, силикон, поликарбонат, PMMA (оргстекло), пенополиуретан, нейлон, номекс, хлопок, бумага и ткань SIBAL.

**Способы поджога:**
- **Открытое пламя:** поджигает предмет напрямую.
- **Электрический перегрев:** 15 кВт/м² изнутри. Обычно тлеет и дымит.
- **Сильный перегрев:** 40 кВт/м². Может воспламенить, как перегруженный провод.

**Атмосферы:**

| Вариант | Кислород | Давление | Гравитация |
|---|---|---|---|
| Кабина МКС | 21 % | 101 кПа | 0 g |
| Атмосфера для дальних полётов (планируется для будущих кораблей) | 34 % | 56,5 кПа | 0 g |
| Перелёт к Марсу | 26,5 % | 70,3 кПа | 0 g |
| Лунный посадочный модуль | 34 % | 56,5 кПа | 0,165 g |
| Поверхность Марса | 26,5 % | 70,3 кПа | 0,378 g |
| МКС с выключенными вентиляторами | 21 % | 101 кПа | 0 g |

Можно задать и любое своё сочетание гравитации, кислорода и давления.

## 3. Основная идея: сетка ячеек и маленькие шаги по времени

Кабина разрезана на маленькие кубики («ячейки»): 15 см в 3D (около 71 000 ячеек) или 7,5 см в 2D-срезе. В каждой ячейке хранятся:
- температура и скорость газа;
- количество кислорода, паров горючего, сажи (дыма), CO, HCN, HF, огнегасящего CO₂ и водяного тумана;
- для твёрдых ячеек: материал, температура его поверхности, сколько уже сгорело и состояние пламени (нет, нагрев, горит, погасло или выгорело).

На каждом шаге (до 0,25 секунды модельного времени; короче, когда воздух движется быстро) движок обновляет каждую ячейку в таком порядке:

1. **Воздушный поток:** вентиляторы толкают воздух, горячий газ расширяется и при гравитации поднимается, поток согласуется со стенами и люками.
2. **Перенос:** поток переносит и перемешивает тепло, кислород, пары горючего, дым и токсичные газы. Вентиляция возвращает воздух через фильтр.
3. **Твёрдые материалы:** каждая поверхность нагревается. Движок проверяет, может ли там существовать пламя, как быстро оно переходит на соседние ячейки и как быстро сгорает материал, выделяя пары, дым, CO, HCN и HF.
4. **Огнетушители и сброс давления:** действуют CO₂, водяной туман и сбросные клапаны.
5. **Горение:** где пары горючего встречаются с кислородом и смесь достаточно горячая, она горит и выделяет тепло. Давление каждого изолированного отсека меняется вслед за выделенным теплом.
6. **Излучение:** пламя и горячий дым излучают тепло на стены и другие предметы и прогревают их.
7. **Экипаж:** каждый астронавт проверяет сигнализацию, перемещается и получает дозу.

Движок написан на обычном JavaScript и работает в фоновом потоке браузера (Web Worker). На обычном процессоре ноутбука он идёт примерно в 8 раз быстрее реального времени; видеокарта не нужна.

## 4. Физика по шагам

### 4.1 Воздушный поток
- Воздух подчиняется **уравнениям Навье–Стокса** для газа, плотность которого меняется с температурой: горячий газ лёгкий и при гравитации поднимается.
- Мелкая турбулентность описывается **моделью Смагоринского**, стандартным методом в моделировании пожаров.
- Горячий газ расширяется. Шаг **проекции давления** заставляет поток сохранять массу с учётом этого расширения, а также газа, который добавляют огнетушители или убирает разгерметизация.
- **Вентиляция рециркуляционная**, как на МКС: воздух проходит через фильтр частиц и подаётся обратно. Частицы дыма удаляются, но CO, HCN и недостаток кислорода остаются в кабине.
- Когда люк закрыт, отсек становится **изолированным** и получает своё давление. Пожар внутри его повышает, поэтому дым и давление запираются.

### 4.2 Горение
- Горение **контролируется смешением**: скорость зависит от того, как быстро смешиваются пары горючего и кислород, и каждый израсходованный килограмм кислорода даёт 13,1 МДж.
- **Проверка затухания** (тот же подход, что в коде FDS от NASA/NIST) позволяет смеси гореть, только если она может достичь критической температуры пламени 1600 К. Поэтому пламя гаснет, когда падает кислород или огнегасящее вещество охлаждает газ.
- **CO₂ из огнетушителя** делает газ труднее нагреваемым, поэтому действует как пониженный уровень кислорода.

### 4.3 Излучение
- Тепловое излучение рассчитывается в **P1-приближении**.
- Сажа и газы горения поглощают и излучают тепло. Чем дымнее газ, тем сильнее он излучает.
- Около 30 % тепла пламени уходит излучением. Оно может прогреть далёкие предметы, и стены его поглощают.

### 4.4 Твёрдые материалы и распространение пламени
Это сердце модели.

**Тонкие и толстые предметы.** Тонкие предметы (ткань, бумага, изоляция проводов) прогреваются целиком. Толстые панели (PMMA, поликарбонат, силикон) проводят тепло вглубь, и это рассчитывается по толщине в 8 точках.

**Может ли здесь существовать пламя?** Модель вычисляет температуру пламени из трёх величин: кислорода, местной скорости воздуха и давления. Пламя существует, только если:
- оно достаточно горячее, то есть не гаснет. В неподвижном или очень медленном воздухе пламя теряет слишком много тепла излучением и гаснет;
- воздух не слишком быстрый, то есть пламя не сдувается.

Это одно правило воспроизводит влияние кислорода, потока и давления, которое видно в испытаниях NASA.

**Как быстро распространяется?** Есть два направления:
- **Навстречу потоку:** медленно. Рассчитывается по классической теории де Риса для тонкого горючего.
- **По потоку:** быстрее. Растёт со скоростью воздуха и температурой пламени. Константы подобраны по данным полётов.

**Как быстро сгорает?** Тепло, приходящее на поверхность (от своего пламени, излучения и электрического перегрева), минус уходящее тепло (на водяной туман и теплопроводность), делённое на энергию, нужную, чтобы превратить твёрдый материал в пар.

### 4.5 Дым и токсичные газы
- Каждый материал выделяет сажу (дым), CO, HCN и HF в постоянных пропорциях (выходах).
- В невесомости пламя слабое и близко к пределу, поэтому даёт **гораздо больше CO**. В Saffire для хлопка в 0 g получилось около 0,034 кг CO на кг, а на Земле около 0,004. Модель плавно переходит между значениями для 0 g и 1 g при изменении гравитации.
- CO растёт ещё больше, когда в отсеке кончается кислород.
- **Видимость** рассчитывается по плотности дыма.
- **Датчики дыма** срабатывают при ослаблении света 0,1 на метр.

## 5. Почему пожар в невесомости другой

- **Нет конвекции.** Горячий газ не поднимается, поэтому нет естественной «тяги», которая подаёт свежий воздух в пламя. Пламя живёт или умирает за счёт **потока от вентиляторов**.
- **Вентиляторы выключены.** В неподвижном воздухе многие пламена гаснут сами, поэтому экипаж выключает вентиляцию. Но некоторые материалы продолжают тлеть.
- **Дым идёт туда, куда несут вентиляторы.** Он не поднимается к потолку. Поэтому на МКС датчики стоят на вытяжке вентиляции.
- **Больше CO.** Слабое пламя даёт больше угарного газа.
- **Кабины с повышенным кислородом и пониженным давлением** (34 % O₂ при 56,5 кПа) позволяют гореть гораздо большему числу материалов.

Симулятор показывает всё это напрямую: один и тот же материал может гореть или погаснуть в зависимости от потока, кислорода и давления.

## 6. Экипаж и выживание

- Четыре астронавта реагируют на датчик дыма: через 15 с, если не спят, и через 60 с, если спят. Во вкладке 2D на сайте тот, кто находится в горящем отсеке, реагирует сразу.
- Они идут через открытые люки в безопасный модуль, распределяются там, и последний закрывает люк в сторону пожара.
- Каждый астронавт набирает **долю эффективной дозы (FED)** по методу ISO 13571 / Пёрсера из четырёх источников: CO и HCN, недостаток кислорода, жара и учащённое дыхание из-за CO₂. Недостаток кислорода считается по парциальному давлению, приведённому к уровню моря, поэтому разгерметизированный модуль смертелен.
- **FED 0,3 означает потерю работоспособности, а FED 1 означает потерю сознания.** Отдельная мера раздражения учитывает HF.
- Люк, закрытый слишком рано, может **запереть человека** вместе с пожаром.

## 7. Что может сделать экипаж

| Действие | Что происходит в модели |
|---|---|
| **Отключить питание** | Прекращает электрический перегрев. |
| **Выключить вентиляторы** | Убирает поток, питающий пламя, но дым перестаёт фильтроваться. |
| **Закрыть люки или двери** | Изолирует отсек: запирает дым и давление и может запереть экипаж. |
| **Оповестить экипаж** | Все начинают двигаться раньше. |
| **Надеть маски** | Экипаж 15 минут дышит из кислородных аппаратов. |
| **Углекислотный огнетушитель (CO₂)** | Около 2,7 кг за 45 с. Разбавляет кислород и охлаждает газ; без масок воздух непригоден для дыхания. |
| **Огнетушитель с водяным туманом** | Около 2 кг за 50 с. Испаряется на тепле и смачивает поверхности; воздух остаётся пригодным для дыхания. |
| **Сброс в вакуум** | Крайняя мера. Воздух уходит через клапан, и пламя гаснет от низкого давления. Сброс медленный, сначала может раздуть пожар, и убивает тех, кто остался внутри. |

**Панель подсказок** под изображением меняется с ситуацией (профилактика, действовать сейчас, эвакуироваться и изолировать, всё чисто). Её кнопки «Do it» выполняют действие. Есть также кнопки **ускорения** (до воспламенения, до тревоги, +1 мин, +5 мин), **повтор**, сравнение двух запусков, экспорт в CSV и учебный тест.

## 8. Откуда берутся числа: калибровка

Все константы взяты из базы знаний проекта с записями NASA (NTRS, Europe PMC, TechPort). Лишь несколько констант **подобраны** по измерениям; всё остальное является **предсказанием**.

| Подобранная константа | По какому измерению |
|---|---|
| Скорость распространения по потоку, тонкая ткань | Saffire-1: ткань SIBAL, 0 g, 21,7 % O₂, поток 20 см/с → 1,8 мм/с |
| Как скорость растёт с кислородом | Saffire VI-2: 31 % O₂, 54 кПа → 4,05 мм/с |
| Скорость распространения по потоку, толстый PMMA | Saffire VI-3: PMMA 10 мм → 0,38 мм/с |
| Пределы пламени для SIBAL | Скорости погасания в BASS-II (1 см/с при 21 % O₂, 5 см/с при 16 %) |
| Пределы для PMMA | Испытания PMMA на МКС |
| Пределы для каптона, силикона и нейлона | NASA-STD-6001, тест 1 |
| Выходы CO и дыма для хлопковых тканей в 0 g | Saffire IV-1 (рост CO, время тревоги, рост давления) |

**Saffire** — серия больших экспериментов NASA с огнём внутри пустых грузовых кораблей Cygnus после их отстыковки от МКС. Это единственные данные о больших пожарах в настоящих космических кораблях.

## 9. Насколько точно: валидация

Модель проверили по измерениям, по которым её **не** подбирали:
- **Из 22 независимых проверок 18 совпадают с измерением с точностью до двух раз, а 8 — в пределах 30 %.**
- Примеры: распространение в Saffire-2 измерено 2,1 и 2,6 мм/с, а в модели 1,91 и 2,34 мм/с; распространение при лунной гравитации (LUCI) измерено 0,92–1,1 мм/с, а в модели 1,10 мм/с.
- Вся 3D-модель воспроизводит каждый пожар Saffire в изолированной кабине измеренного объёма и сравнивает скорость распространения, тепло, CO, рост давления и время тревоги.
- **Исследование сетки:** тепловыделение почти сошлось. Скорость распространения ещё падает при уменьшении ячеек, поэтому рабочая сетка 15 см, вероятно, завышает скорость примерно на 25 %.

Полная таблица валидации, график «предсказано против измерено» и исследование сетки показаны внизу 3D-страницы.

## 10. Честные ограничения

- Ячейки 15 см больше реального пламени, поэтому пламя моделируется ниже масштаба сетки.
- Токсичные газы берутся из постоянных выходов, а не из подробной химии. Измеренные выходы в 0 g есть только для хлопковых тканей.
- Большинство пределов материалов взято из справочных значений (LOI). Измеренные пределы есть только для SIBAL, PMMA, каптона, силикона и нейлона.
- Количества огнегасящих веществ и размеры клапанов типовые, а не характеристики реального оборудования.
- При низком давлении датчик дыма срабатывает в 2–4 раза раньше, чем в Saffire.
- Поведение экипажа — простое правило (отреагировать и уйти). Реальный экипаж действует по процедурам и тушит пожар.
- **Это инструмент для обучения и исследований, а не рабочая процедура.**

## 11. Вкладка 3D cabin (собственная быстрая модель сайта)

Вкладка 3D cabin отвечает на вопрос «насколько опасен этот пожар» за секунду, без расчёта каждой ячейки:

1. **Может ли гореть?** Максимальная концентрация кислорода для материала по NASA-STD-6001 интерполируется на давление кабины. Она снижается до 3 % O₂ по мере приближения гравитации к нулю и резко растёт в почти неподвижном воздухе, где излучение гасит пламя.
2. **Как быстро?** Корреляции распространения из испытаний NASA в башнях сброса дают скорость распространения, модель скорости горения даёт тепловыделение, а правило Торнтона — расход кислорода.
3. **Что происходит с воздухом?** Выходы продуктов горения дают CO и дым, а двухзонная модель кабины — время, за которое дым дойдёт до датчика.
4. **Реагирование:** выключение вентиляции замедляет пламя, но не гасит его сразу, как было видно в Saffire V.
5. В браузере параллельно работает отдельная **2D-модель распространения** (взята без изменений из симулятора жилого модуля товарища по команде). Её результаты сохраняются с каждым запуском.
6. Результат появляется в правой колонке: вывод, распространение, время тревоги и сравнение «до и после». **ИИ-ассистент** может прочитать сценарий и результат.

## 12. Как вкладки корабля встроены в сайт

- Страницы товарища по команде — это файлы в `blackfox/db/knowledge/spacecraft_fire/fire_sim_ship/`:
  - `spacecraft_cabin_fire_2d.html` открывается по адресу `/fire-sim`;
  - `spacecraft_cabin_fire.html` открывается по адресу `/fire-sim-3d`.
- Сервер отдаёт их из этой папки **без изменений**, поэтому новая загрузка любого из файлов появляется на сайте после следующего развёртывания (примерно через минуту после попадания в `main`).
- Внутри вкладок (`?embed=1`):
  - заголовок страницы скрыт;
  - колонка с элементами управления перенесена влево, на место панели сценария лаборатории.
- **Вкладка 2D** добавляет кое-что поверх страницы товарища:
  - **Автоматический старт:** пожар начинается сам в спальном мешке в левой каюте, в атмосфере для дальних полётов. Там он горит достаточно долго, чтобы вентиляторы пронесли дым через Узел в Лаб. Щелчок по карте пожар не начинает.
  - **Правила экипажа:** экипаж реагирует на тревогу (или на кнопку Alert crew), а не на первое пламя где угодно. Тот, кто находится в горящем отсеке, реагирует сразу. Экипаж распределяется в безопасном модуле, и люк в сторону пожара закрывается, когда все в безопасности.
  - **Отображение дыма:** дым рисуется в логарифмической шкале, поэтому видно даже тонкий дым на уровне тревоги. Меняется только картинка, не физика.
- **Вкладка 3D** показывает полную страницу со всеми её элементами управления.

## 13. Как сделана симуляция

### 13.1 Технологии
- **Язык:** обычный JavaScript. Без фреймворков и без инструментов сборки, кроме одного небольшого скрипта на Python, и ничего не нужно устанавливать.
- **Движок** (`fire_core/engine.js`, около 740 строк): чистые вычисления, без кода экрана. Один и тот же файл работает в браузере и в Node.js, поэтому тесты и валидация используют ровно тот же код, что и страница.
- **Геометрия** (`fire_core/layouts.js`): корабль описан как данные, а не нарисован вручную:
  - отсеки, люки, вентиляция, клапаны, предметы и места экипажа заданы как прямоугольные области и простые проверки формы в метрах;
  - движок сам превращает их в ячейки при любом выбранном размере ячейки. Поэтому один движок обслуживает 3D-корабль, 2D-срез и кабину для валидации Saffire.
- **3D-изображение:** three.js (WebGL):
  - корпус рисуется полупрозрачными цилиндрами;
  - стойки, предметы, вентиляция и люки рисуются множеством маленьких кубиков одним пакетом (instanced meshes);
  - горячий газ и дым — облака точек со своим шейдером;
  - астронавты — простые фигурки, а на фоне Земля, Луна или Марс.
- **2D-изображение:** срез рисуется попиксельно на HTML canvas. Можно выбрать, какое поле показывать (температура, дым, кислород, CO и другие), а стрелки показывают поток воздуха.

### 13.2 Как устроен движок
- **Ячейки:** область — это трёхмерный массив с одним дополнительным слоем «фантомных» ячеек по краям для стен. Каждая ячейка — газ, стена или горючее. Каждая величина (температура, скорость, кислород и т. д.) хранится в одном плоском массиве чисел (`Float64Array`) ради скорости.
- **Построение сетки:** при запуске движок:
  - размечает каждую ячейку по описанию геометрии;
  - находит, какие ячейки к какому отсеку относятся и какие области газа изолированы друг от друга;
  - один раз рассчитывает поток от вентиляторов;
  - делает 30 шагов «разогрева», чтобы в момент ноль воздух уже двигался.
- **Шаг по времени:** длина шага подстраивается под самый быстрый воздух, чтобы воздух никогда не проходил больше двух ячеек за шаг (от 0,03 до 0,25 с). Это сохраняет расчёт устойчивым.
- **Численные методы:**
  - **полулагранжев перенос:** каждая ячейка смотрит назад по потоку, откуда пришёл её воздух. Метод устойчив даже при больших шагах;
  - **неявная диффузия;**
  - **метод red-black SOR:** итерационный решатель для давления, который заставляет поток сохранять массу;
  - **P1-излучение:** решается таким же итерационным решателем.
- **Команды:** каждое действие (поджог, огнетушитель, закрыть люк, сброс давления и т. д.) проходит через одну функцию `command()`, которая записывает его со временем. Благодаря этому работают повтор, сценарии по сценарию-скрипту и кнопки «Do it».

### 13.3 Как страница его запускает
- Движок работает в **Web Worker** (фоновом потоке), поэтому страница никогда не зависает. Воркер:
  - продвигает движок к целевому времени: реальное время, умноженное на выбранную скорость (×2, ×8, ×32);
  - работает порциями примерно по 45 мс;
  - примерно 7 раз в секунду отправляет странице кадр со всеми полями в виде компактных массивов.
- Если компьютер не успевает, симуляция **идёт медленнее, но не пропускает физику**.
- **Ускорение** (до воспламенения, до тревоги, +1 или +5 мин) гонит движок максимально быстро и проверяет условие остановки после каждого шага.
- **Запись:** одна строка чисел на каждую секунду модельного времени (для графиков, сравнения и CSV) и сжатый 3D-снимок каждые 5 с (для повтора).
- **Один файл:** `src/build.py` склеивает исходники страницы, движок, код воркера и результаты валидации в один HTML-файл. Движок и воркер встроены как текст и запускаются из него. Поэтому страница открывается двойным щелчком без сервера.
- **Самопроверка:** если открыть страницу с `#autotest` в конце адреса, она поджигает, тушит и пишет PASS или FAIL в заголовке.

### 13.4 Как собиралась и проверялась физика
1. **Сначала данные.** В базе знаний проекта лежат записи NASA (отчёты NTRS, статьи Europe PMC, TechPort): Saffire, BASS, LUCI, пределы материалов NASA-STD-6001, исследования огнетушителей и разгерметизации. У каждого материала в движке указаны источники.
2. **Подмодели из опубликованной теории:** распространение пламени по де Рису, горение и затухание в стиле FDS, P1-излучение, токсичная доза по ISO 13571 / Пёрсеру.
3. **Калибровка на небольшом заявленном наборе** измерений (раздел 8). Всё остальное остаётся предсказанием.
4. **Валидация отдельно от страницы:** `validate_saffire.js` запускается в Node. Он воспроизводит каждый пожар Saffire в изолированной кабине измеренного объёма, сравнивает результаты с измерениями при нескольких размерах ячеек и записывает `validation_results.json`. `build.py` встраивает этот файл в страницу, где из него строятся таблица и графики валидации.
5. **Исправление найденного.** Так нашли и исправили шесть настоящих ошибок модели, например двойной учёт массы горючего, пожар, который не мог распространяться в 0 g, и датчики, которые не видели дым в 0 g.

### 13.5 Как сайт его встраивает (сторона Black Fox)
- Бэкенд — **FastAPI** (Python). Маршруты `/fire-sim` и `/fire-sim-3d` читают HTML-файл товарища и добавляют только:
  - маленькую полосу «назад к симулятору», а внутри вкладки — CSS, который прячет заголовок страницы и переносит её элементы управления влево;
  - для вкладки 2D — несколько точных текстовых замен (правила экипажа и отображение дыма) и скрипт автоматического поджога.
- **Защита для замен:** каждая из них должна совпасть с файлом товарища ровно один раз. Если его файл изменится и совпадение пропадёт, ни одна замена не применяется, и страница работает так, как он её написал. Тест сообщает о несовпадении.
- Страницы показываются в **iframe**. Сервер разрешает это только на страницах самого сайта (`Content-Security-Policy: frame-ancestors 'self'`).
- **Тесты** (pytest и Node) проверяют, что маршруты отдают файлы без изменений, кроме этих добавок, и что вкладки на месте. Каждый push в `main` выкладывается на сайт примерно за минуту.

## 14. Где находится код

```
blackfox/db/knowledge/spacecraft_fire/
  README.md                     полный технический отчёт (уравнения, валидация, источники)
  fire_core/engine.js           физический движок
  fire_core/layouts.js          геометрии: 3D-корабль, 2D-срез, кабина для валидации Saffire
  fire_core/validate_saffire.js валидация по Saffire → validation_results.json
  fire_sim_ship/spacecraft_cabin_fire.html      страница 3D-симулятора
  fire_sim_ship/spacecraft_cabin_fire_2d.html   страница 2D-симулятора
  fire_sim_ship/src/build.py    пересобирает обе страницы из движка и исходников страницы
app/main.py                     отдаёт /fire-sim и /fire-sim-3d (и изменения экипажа и дыма во вкладке 2D)
frontend/js/sim2d_embed.js      автоматический поджог во вкладке 2D
blackfox/physics/fire.py        быстрая модель вкладки 3D cabin
```

**Основные источники:** NASA NTRS 20170008805 (Saffire-1 и Saffire-2), 20260001992 (тепло и дым в Saffire IV–VI), 20150008962 (BASS-II), 20110008636 (пределы по NASA-STD-6001), 20260003546 (риски разгерметизации), 20130011664 и 20110012896 (огнетушитель с водяным туманом на МКС), 20250010653 (LUCI), ISO 13571 / Пёрсер (токсичная доза) и McGrattan и др. (FDS).
