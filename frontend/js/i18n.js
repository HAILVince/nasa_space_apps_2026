// UI strings. The language follows the domain (.hu -> Hungarian), the browser, or the user's choice.
const T = {
  hu: {
    tab_dashboard: 'Kísérletek', dash_title: 'Kísérlet-dashboardok',
    dash_intro: 'Mikrogravitációs égési kísérletcsaládok küldetés és tűzbiztonsági fókusz szerint (NASA Flame in Freefall kihívás). A rangsor kutatási relevanciát mutat, nem tűzkockázatot.',
    dash_mission: 'Küldetés', dash_focus: 'Fókusz', dash_search: 'Keresés', dash_update: 'Frissítés', focus_all: 'Áttekintés',
    focus_prevention: 'Megelőzés', focus_detection: 'Érzékelés', focus_suppression: 'Oltás', dash_limits: 'Bizonyítékok és adatkorlátok',
    dash_compare: 'Kijelöltek összehasonlítása (2–4)', dash_loading: 'Betöltés…', dash_error: 'A kérés sikertelen',
    dash_retry: 'Próbáld újra a Frissítés gombbal.', dash_counts: '{n} kísérletcsalád · megelőzés: {p} · érzékelés: {d} · oltás: {s}',
    dash_none: 'Nincs találat. Próbálj másik fókuszt vagy keresést.', dash_pick: 'Összehasonlításba', dash_source: 'Forrás: NASA kihívásleírás',
    dash_relevance: 'Relevancia', dash_fuel: 'Üzemanyag', dash_hw: 'Eszköz', dash_pick_2_4: 'Jelölj ki 2–4 kísérletet.',
    dash_caption: 'Kísérletek összehasonlítása — az ismeretlen körülményekhez az eredeti adatsorok kellenek',
    dash_cols: ['Kísérlet', 'Fókusz', 'Üzemanyag', 'Eszköz', 'Gravitáció', 'Oxigén (%)', 'Nyomás (kPa)', 'Légáram (m/s)'], unknown: 'ismeretlen',
    scn_spacecraft: 'Űrhajó', scn_station: 'Űrállomás', scn_lunar_base: 'Holdbázis', scn_mars_habitat: 'Mars-habitat', scn_rover: 'Túlnyomásos rover',
    reply_lang: 'Válasz nyelve', chat_label: 'Kérdés az AI mérnöknek',
    skip: 'Ugrás a 3D modellhez', product: 'Tűzbiztonsági labor', tab_sim: 'Szimuláció', tab_research: 'Kutatási bizonyítékok',
    tab_console: 'AI mérnök', data_source: 'NASA NTRS adatok', tour: 'Bemutató', env: 'Környezet', atmosphere: 'Kabinlégkör',
    reset_defaults: 'alapérték', pressure: 'Össznyomás', o2: 'Oxigén', temp: 'Hőmérséklet', ppo2: 'O₂ parciális nyomás',
    source: 'Tűzforrás', location: 'Hely a modulban', material: 'Anyag', response: 'Szellőzés és beavatkozás',
    vent: 'Légáramlás a forrásnál', vent_hint: 'Névleges űrhajó-szellőzés: 5–20 cm/s (sávozva). Zárt rack, fülke és kesztyűsdoboz saját ventilátorral.',
    auto_vent: 'Szellőzés leállítása riasztáskor', suppression: 'Oltás', sup_none: 'Nincs', sup_co2: 'CO₂ PFE', sup_mist: 'Vízköd',
    resp_time: 'Legénység reakcióideje', hud_title: 'Kabintűz-szimuláció', cam_ext: 'Külső', cam_cut: 'Metszet', cam_int: 'Belső',
    cam_fire: 'Tűz', mode_normal: 'Valós', mode_xray: 'Röntgen', mode_thermal: 'Hőkép', mode_air: 'Áramlás', loading: 'Modell betöltése…',
    map_title: 'Éghetőségi térkép', map_sub: 'O₂ – össznyomás', ts_title: 'Lefolyás', log_title: 'Eseménynapló',
    evidence_title: 'Forrásaink', see_all: 'összes', research_intro: 'A szimulátor minden kulcsszáma a Blackfox tudásbázis ellenőrzött rekordjaiból jön (NASA Technical Reports Server). Alább a jelenlegi környezethez és anyaghoz illő rekordok — a biológiai, egészségügyi és más, nem tűzbiztonsági témák kiszűrve.',
    console_intro: 'Kérdezd a Blackfox ügynököt az aktuális szcenárióról. Látja a beállításaidat és újra tudja futtatni a szimulációt.',
    send: 'Küldés', chat_ph: 'Pl.: Miért ég a polietilén a Holdon 34% oxigénnél?',
    lv_low: 'Nem terjed', lv_elevated: 'Mérsékelt', lv_high: 'Magas', lv_critical: 'Kritikus',
    v_low: 'Az oxigénszint {margin} százalékponttal a korrigált éghetőségi határ (MOC) alatt van: a gyújtás után a láng magától kialszik.',
    v_burn: 'Az anyag ég: {margin} százalékpont az oxigén-tartalék a határ felett. Terjedés {spread}, csúcs hőteljesítmény {hrr}. {det}',
    v_det: 'Riasztás {t} után, {how}.', v_nodet: 'Az érzékelők nem jeleznek a szimuláció ideje alatt.',
    how_detector: 'füstérzékelő', how_crew: 'a legénység észleli',
    m_moc1g: 'MOC 1 g-n (NASA-STD-6001)', m_moceff: 'Korrigált határ itt', m_margin: 'O₂-tartalék', m_spread: 'Lángterjedés',
    m_tflame: 'Lánghőmérséklet', m_hrr: 'Csúcs hőteljesítmény', m_alarm: 'Riasztásig', m_co: 'CO csúcs (SMAC 1 h: {smac})',
    m_dp: 'Nyomásnövekedés', m_flow: 'Effektív áramlás', m_burned: 'Elégett anyag', m_out: 'Kialvásig',
    none: 'nincs', burnout: 'kiégés',
    ev_ignition: 'Gyújtás', ev_alarm: 'Riasztás', ev_vent_off: 'Szellőzés leállítva', ev_co2: 'CO₂ oltó (PFE) bevetve',
    ev_water_mist: 'Vízköd-oltó bevetve', ev_crew_on_scene: 'Legénység a helyszínen (nincs oltó)', ev_extinguished: 'A láng kialudt',
    ev_self_extinguished: 'A láng magától kialudt', ev_co_smac: 'CO eléri az 1 órás SMAC értéket',
    map_eff: 'határ itt (g, áramlás)', map_1g: 'NASA-STD-6001 (1 g)', map_norm: 'normoxikus görbe', map_meas: 'mért pont', map_now: 'jelenlegi',
    map_flam: 'ÉG', map_nonflam: 'NEM TERJED', ts_hrr: 'hőteljesítmény kW', ts_co: 'CO ppm', ts_smoke: 'füst a detektornál mg/m³',
    hud_hrr: 'Hőteljesítmény', hud_o2: 'O₂ kabin', hud_co: 'CO', hud_flow: 'Áramlás',
    legend_thermal: 'Felületi hőmérséklet-emelkedés', legend_air: 'Befúvás → elszívás · ciánkék: légáram, szürke: füst',
    gravity: 'gravitáció', form_thin: 'vékony (szövet/fólia)', form_wire: 'kábelszigetelés', form_thick: 'tömör alkatrész',
    material_hint: '{form} · MOC 1 g: {moc} @ {p} · égéshő ≈ {dhc} MJ/kg · bomlástermék: {tox}',
    vent_off: 'ki', vent_on: 'be', research_loading: 'Rekordok betöltése…', research_none: 'Nincs találat.',
    facts: 'Tények', sources: 'Források', open_ntrs: 'Megnyitás az NTRS-en', back: '← vissza',
    chat_error: 'Az AI most nem elérhető. Próbáld újra később.', thinking: 'Gondolkodom…',
    tour_steps: [
      ['HAB–01 kutatómodul', 'Blenderben modellezett, Cycles-ben sütött árnyékolású nyomásálló modul metszete: rackek, kábelcsatornák, ventilátor, zsilip.'],
      ['ISS-légkör, mikrogravitáció', '101,4 kPa és 21% O₂. Felhajtóerő nincs, ezért a láng gömbszerű és kék; a füst nem száll fel, csak a szellőzés viszi.'],
      ['Gateway, Hold körüli pálya', '70,3 kPa és 26,5% O₂: a kisebb nyomás alig segít, a több oxigén viszont csökkenti a tartalékot.'],
      ['Holdfelszín, 34% O₂', 'A NASA Moon-to-Mars kutatási légköre (56,5 kPa / 34%): a 0,165 g "aranyközép" — elég felhajtóerő, kevés hőveszteség.'],
      ['Mars, 0,378 g', 'Ugyanaz a légkör, nagyobb gravitáció: hosszabb, sárgább láng. A tűzforrást a 3D modellben a jelölőkre kattintva is áthelyezheted.'],
    ],
  },
  en: {
    tab_dashboard: 'Investigations', dash_title: 'Research dashboards',
    dash_intro: 'Microgravity combustion experiment families by mission and fire-safety focus (NASA Flame in Freefall challenge). Rankings describe research relevance; they are not predictions of fire risk.',
    dash_mission: 'Mission', dash_focus: 'Dashboard', dash_search: 'Search', dash_update: 'Update dashboard', focus_all: 'Research overview',
    focus_prevention: 'Prevention', focus_detection: 'Detection', focus_suppression: 'Suppression', dash_limits: 'About the evidence & data limitations',
    dash_compare: 'Compare selected investigations (2–4)', dash_loading: 'Loading…', dash_error: 'Research request failed',
    dash_retry: 'Use Update dashboard to retry.', dash_counts: '{n} investigations · prevention: {p} · detection: {d} · suppression: {s}',
    dash_none: 'No investigations match. Try another focus or search.', dash_pick: 'Compare', dash_source: 'Source: NASA challenge brief',
    dash_relevance: 'Relevance', dash_fuel: 'Fuel', dash_hw: 'Hardware', dash_pick_2_4: 'Select two to four investigations.',
    dash_caption: 'Investigation comparison — unknown conditions require original datasets',
    dash_cols: ['Investigation', 'Focus', 'Fuel', 'Hardware', 'Gravity', 'Oxygen (%)', 'Pressure (kPa)', 'Airflow (m/s)'], unknown: 'Unknown',
    scn_spacecraft: 'Spacecraft', scn_station: 'Station', scn_lunar_base: 'Lunar base', scn_mars_habitat: 'Mars habitat', scn_rover: 'Pressurized rover',
    reply_lang: 'Agent reply language', chat_label: 'Ask the AI engineer',
    skip: 'Skip to the 3D model', product: 'Fire Safety Lab', tab_sim: 'Simulation', tab_research: 'Research evidence',
    tab_console: 'AI engineer', data_source: 'NASA NTRS data', tour: 'Guided tour', env: 'Environment', atmosphere: 'Cabin atmosphere',
    reset_defaults: 'defaults', pressure: 'Total pressure', o2: 'Oxygen', temp: 'Temperature', ppo2: 'O₂ partial pressure',
    source: 'Fire source', location: 'Location in the module', material: 'Material', response: 'Ventilation & response',
    vent: 'Air flow at the source', vent_hint: 'Nominal spacecraft ventilation: 5–20 cm/s (hatched). Enclosed rack, crew quarters and glovebox have their own fans.',
    auto_vent: 'Shut ventilation down on alarm', suppression: 'Suppression', sup_none: 'None', sup_co2: 'CO₂ PFE', sup_mist: 'Water mist',
    resp_time: 'Crew response time', hud_title: 'Cabin fire simulation', cam_ext: 'Exterior', cam_cut: 'Cutaway', cam_int: 'Interior',
    cam_fire: 'Fire', mode_normal: 'Real', mode_xray: 'X-ray', mode_thermal: 'Thermal', mode_air: 'Airflow', loading: 'Loading model…',
    map_title: 'Flammability map', map_sub: 'O₂ vs total pressure', ts_title: 'Fire history', log_title: 'Event log',
    evidence_title: 'Our sources', see_all: 'all', research_intro: 'Every key number of the simulator comes from checked records of the Blackfox knowledge base (NASA Technical Reports Server). Below are the records that match the current environment and material — biology, health and other non-fire topics are filtered out.',
    console_intro: 'Ask the Blackfox agent about the current scenario. It sees your settings and can re-run the simulation.',
    send: 'Send', chat_ph: 'e.g. Why does polyethylene burn on the Moon at 34% oxygen?',
    lv_low: 'No spread', lv_elevated: 'Elevated', lv_high: 'High', lv_critical: 'Critical',
    v_low: 'Oxygen is {margin} points below the corrected flammability limit (MOC): after ignition the flame goes out by itself.',
    v_burn: 'The material burns: {margin} points of oxygen above the limit. Spread {spread}, peak heat release {hrr}. {det}',
    v_det: 'Alarm after {t}, {how}.', v_nodet: 'No detector alarms during the simulated time.',
    how_detector: 'smoke detector', how_crew: 'seen by the crew',
    m_moc1g: 'MOC at 1 g (NASA-STD-6001)', m_moceff: 'Corrected limit here', m_margin: 'O₂ margin', m_spread: 'Flame spread',
    m_tflame: 'Flame temperature', m_hrr: 'Peak heat release', m_alarm: 'Time to alarm', m_co: 'Peak CO (1 h SMAC: {smac})',
    m_dp: 'Pressure rise', m_flow: 'Effective flow', m_burned: 'Material burned', m_out: 'Time to extinction',
    none: 'none', burnout: 'burnout',
    ev_ignition: 'Ignition', ev_alarm: 'Alarm', ev_vent_off: 'Ventilation shut down', ev_co2: 'CO₂ extinguisher (PFE) discharged',
    ev_water_mist: 'Water-mist extinguisher discharged', ev_crew_on_scene: 'Crew on scene (no extinguisher)', ev_extinguished: 'Flame extinguished',
    ev_self_extinguished: 'Flame self-extinguished', ev_co_smac: 'CO reaches the 1-hour SMAC',
    map_eff: 'limit here (g, flow)', map_1g: 'NASA-STD-6001 (1 g)', map_norm: 'normoxic curve', map_meas: 'measured', map_now: 'current',
    map_flam: 'BURNS', map_nonflam: 'NO SPREAD', ts_hrr: 'heat release kW', ts_co: 'CO ppm', ts_smoke: 'smoke at detector mg/m³',
    hud_hrr: 'Heat release', hud_o2: 'Cabin O₂', hud_co: 'CO', hud_flow: 'Flow',
    legend_thermal: 'Surface temperature rise', legend_air: 'Inlet → return · cyan: air flow, grey: smoke',
    gravity: 'gravity', form_thin: 'thin (fabric/film)', form_wire: 'wire insulation', form_thick: 'solid part',
    material_hint: '{form} · MOC 1 g: {moc} @ {p} · heat of combustion ≈ {dhc} MJ/kg · products: {tox}',
    vent_off: 'off', vent_on: 'on', research_loading: 'Loading records…', research_none: 'No matching records.',
    facts: 'Facts', sources: 'Sources', open_ntrs: 'Open on NTRS', back: '← back',
    chat_error: 'The AI is not available right now. Try again later.', thinking: 'Thinking…',
    tour_steps: [
      ['HAB-01 research module', 'A cutaway of the pressurized module, modelled in Blender with Cycles-baked shading: racks, cable runs, cabin fan, hatch.'],
      ['ISS atmosphere, microgravity', '101.4 kPa and 21 % O₂. No buoyancy, so the flame is round and blue; smoke does not rise, only ventilation moves it.'],
      ['Gateway, lunar orbit', '70.3 kPa and 26.5 % O₂: the lower pressure hardly helps, while the extra oxygen eats into the safety margin.'],
      ['Lunar surface, 34 % O₂', 'NASA\'s Moon-to-Mars exploration atmosphere (56.5 kPa / 34 %): 0.165 g is a "goldilocks zone" — enough buoyancy, little heat loss.'],
      ['Mars, 0.378 g', 'Same atmosphere, more gravity: a taller, yellower flame. Click the markers in the 3D model to move the fire source.'],
    ],
  },
};

let lang = 'en';
try { lang = localStorage.getItem('bfx-lang') || ''; } catch { lang = ''; }
if (!lang) lang = location.hostname.endsWith('.hu') || (navigator.language || '').startsWith('hu') ? 'hu' : 'en';

export const getLang = () => lang;
export function setLang(l) {
  lang = l in T ? l : 'en';
  try { localStorage.setItem('bfx-lang', lang); } catch { /* private mode */ }
  document.documentElement.lang = lang;
  for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
}
export function t(key, vars) {
  let s = T[lang][key] ?? T.en[key] ?? key;
  if (vars && typeof s === 'string') for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}
export const label = (obj) => (obj && (obj[lang] || obj.en)) || '';
