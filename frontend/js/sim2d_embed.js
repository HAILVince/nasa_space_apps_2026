// Loaded only into the simulator's "2D" tab (/fire-sim?embed=1), after the teammate's Spacecraft Cabin
// Fire 2D page. That page keeps its code private (one closure), so this works through its own controls;
// the teammate's file is not changed.
// In the tab the fire always starts by itself at one spot; clicking the map no longer lights fires.
// The default run is the sleeping bag in the port crew quarters, in the exploration atmosphere: there the
// flame lives long enough for the fans to carry its smoke through the Node and into the Lab. (In ISS air the
// small items go out within seconds, and the avionics rack bay is closed off, so little smoke reaches the cabin.)
(function () {
  'use strict';
  const ORIGIN = 'Sleeping bag';                 // Nomex, port crew quarters in the Node
  const PRESET = 'Exploration atmosphere';       // 34 % O2 at 56.5 kPa, in orbit (the planned cabin air)
  const IDLE = 'Choose a fire origin';           // the page's status while nothing burns yet
  const $ = (id) => document.getElementById(id);

  // 1. no manual ignition: map clicks stop here, before the page's own handlers (window capture runs first)
  const onMap = (e) => e.target && (e.target.id === 'slice' || (e.target.closest && e.target.closest('#three')));
  for (const type of ['click', 'pointerup']) {
    window.addEventListener(type, (e) => { if (onMap(e)) { e.stopPropagation(); e.preventDefault(); } }, true);
  }
  const style = document.createElement('style');
  style.textContent = '#igFlame,#igHot,#igSevere,#igStop,.btns:has(#igFlame)+.sub{display:none!important}'
    + '#origin{pointer-events:none;opacity:.75}';
  document.head.append(style);
  const hint = () => {
    const s = $('barSlice') && $('barSlice').querySelector('span:last-child');
    if (s) s.textContent = 'The fire starts by itself in a sleeping bag in the crew quarters. Circles are the crew.';
  };

  // 2. one fixed origin, lit with the page's own "Open flame" after every start or reset
  let lastTry = 0, presetDone = false;
  function tick() {
    const o = $('origin'), status = $('status'), flame = $('igFlame');
    if (!o || !status || !flame || !o.options.length) return;
    hint();
    if (!presetDone) {                                                   // once, at the start; the user may change it
      presetDone = true;
      const f = $('sfield');                                             // show the smoke field first
      if (f && f.value !== 'S') { f.value = 'S'; f.dispatchEvent(new Event('change')); }
      const b = [...document.querySelectorAll('#presets button')].find((x) => x.textContent.includes(PRESET));
      if (b) { b.click(); return; }
    }
    const opt = [...o.options].find((x) => x.text.startsWith(ORIGIN)) || o.options[0];
    if (o.value !== opt.value) { o.value = opt.value; o.dispatchEvent(new Event('change')); }
    if ($('rpOn') && $('rpOn').checked) return;                          // replaying a recorded run
    if (!status.textContent.startsWith(IDLE) || performance.now() - lastTry < 3000) return;
    lastTry = performance.now();
    setTimeout(() => flame.click(), 1200);                               // a moment of airflow first
  }
  setInterval(tick, 400);
})();
