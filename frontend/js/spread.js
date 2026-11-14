// The room-to-room fire spread simulator page: language switch for the shared top bar and a
// Hungarian rendering of the simulator's fixed labels. Text nodes are matched exactly, so the
// simulator's own code stays untouched; live values and the event log stay in English.
import { getLang } from './i18n.js';
import { bindChrome } from './common.js';

const HU = {
  'Black Fox knowledge base · 0 g / Moon / Mars': 'Black Fox tudásbázis · 0 g / Hold / Mars',
  'Habitat Fire Spread': 'Tűzterjedés a habitatban',
  'A side view of a 6 m × 3 m, two-deck habitat with six rooms. The model solves the ventilation flow, then moves heat, smoke and oxygen through the rooms. Flames spread over the furnishings using flammability limits fitted to NASA BASS, BASS-II, Saffire and partial-gravity tests in your knowledge folder. Open or close doors and hatches to see how the fire moves from room to room.':
    'Egy 6 m × 3 m-es, kétszintes, hathelyiséges habitat oldalnézete. A modell kiszámolja a szellőzés áramlását, majd a hőt, a füstöt és az oxigént mozgatja a helyiségek között. A láng a berendezésen terjed, a NASA BASS, BASS-II, Saffire és részleges gravitációs kísérleteire illesztett éghetőségi határokkal. Nyiss vagy zárj ajtókat és zsilipeket, és nézd, hogyan jut át a tűz egyik helyiségből a másikba.',
  Pause: 'Szünet', Reset: 'Újra', 'Ventilation off': 'Szellőzés ki',
  'Click a furnishing to start a fire. Click a door or hatch to close it (shown blue) or open it again. Air enters the Crew quarters on the upper left and leaves through the Lab grille on the lower right.':
    'Kattints egy berendezésre a tűz indításához. Ajtóra vagy zsilipre kattintva bezárod (kék) vagy újra kinyitod. A levegő bal fent a hálófülkénél lép be, és jobb lent a labor rácsán távozik.',
  'hot gas': 'forró gáz', smoke: 'füst', airflow: 'légáram', 'front rings': 'lángfront', 'O₂ depletion': 'O₂-fogyás',
  'Scenario presets': 'Előre beállított szcenáriók', 'Wall lining material': 'Falburkolat anyaga', Gravity: 'Gravitáció',
  'Moon 0.165': 'Hold 0,165', 'Mars 0.378': 'Mars 0,378', 'Earth 1': 'Föld 1', Oxygen: 'Oxigén', 'Cabin pressure': 'Kabinnyomás',
  'Supply air speed': 'Befújt levegő sebessége', 'Room tracker': 'Helyiségek állapota', 'laid out as in the habitat': 'a habitat elrendezésében',
  'Fire area by room': 'Égő felület helyiségenként', 'cm² burning': 'cm² ég', 'Event log': 'Eseménynapló', 'Flammability map': 'Éghetőségi térkép',
  'The wall lining burns above its limit line. Very slow flow starves the flame of oxygen (quenching, left). Fast flow blows it off (right). The dot is the first ignition point, using its local effective flow (ventilation plus buoyancy).':
    'A falburkolat a határvonal fölött ég. Nagyon lassú áramlásnál a láng oxigénhiánytól kialszik (kioltás, balra), gyors áramlás lefújja (jobbra). A pont az első gyújtás helye a helyi effektív áramlással (szellőzés + felhajtóerő).',
  'concurrent limit (downstream spread)': 'egyenáramú határ (terjedés a légárammal)', 'opposed limit (upstream / downward)': 'ellenáramú határ (szembe / lefelé)',
  '0 g flight-data envelope at ~1 atm': '0 g repülési adatok tartománya ~1 atm-en', Evidence: 'Bizonyítékok',
  'Outside the measured envelope': 'A mért tartományon kívül', 'Nearest records in the knowledge base': 'Legközelebbi rekordok a tudásbázisban',
  'Scenario and result as schema.json objects': 'Szcenárió és eredmény schema.json objektumként', 'Copy JSON': 'JSON másolása',
  'The mathematical model': 'A matematikai modell', 'Ventilation flow (potential flow).': 'Szellőzési áramlás (potenciálos áramlás).',
  'Buoyant rise of hot gas.': 'A forró gáz felhajtóerős emelkedése.', 'Heat, smoke and oxygen transport.': 'Hő-, füst- és oxigéntranszport.',
  'Flammability limit (fitted to knowledge-base data).': 'Éghetőségi határ (a tudásbázis adataira illesztve).', 'Flame spread over a surface.': 'Lángterjedés felületen.',
  'Ignition by hot gas.': 'Gyulladás forró gáztól.', 'This is how fire jumps a doorway.': 'Így ugrik át a tűz egy ajtón.', 'Extinction and burnout.': 'Kialvás és kiégés.',
  'This is a teaching and design-exploration model, not a validated fire code like FDS. The flow is potential flow, not Navier–Stokes. The limit lines are hand-fitted to published trends, and spread rates are order-of-magnitude. Before using a number, open the cited NTRS record and check it against the PSI experiment tables.':
    'Ez oktatási és tervezési felfedező modell, nem validált tűzkód (mint az FDS). Az áramlás potenciálos, nem Navier–Stokes. A határvonalak publikált trendekre kézzel illesztettek, a terjedési sebességek nagyságrendiek. Mielőtt egy számot felhasználsz, nyisd meg a hivatkozott NTRS-rekordot, és vesd össze a PSI kísérleti táblázatokkal.',
};
const original = new Map();

function translate() {
  const hu = getLang() === 'hu';
  const walker = document.createTreeWalker(document.querySelector('.wrap') || document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!original.has(n)) {
      const key = n.nodeValue.trim();
      if (!HU[key]) continue;
      original.set(n, key);
    }
    const key = original.get(n);
    n.nodeValue = n.nodeValue.replace(hu ? key : HU[key], hu ? HU[key] : key);
  }
  document.documentElement.lang = getLang();
}

bindChrome(translate);
translate();
