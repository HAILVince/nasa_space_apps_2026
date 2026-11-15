// Loaded only into the simulator's "2D" tab (/fire-sim?embed=1), after the teammate's Spacecraft Cabin
// Fire 2D page. That page keeps its code private (one closure), so this works through its own controls;
// the teammate's file is not changed.
// In the tab the fire always starts by itself at one spot; clicking the map no longer lights fires.
(function () {
  'use strict';
  const ORIGIN = 'Avionics rack wire harness';   // item L1, in the rack bay under the Lab deck
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
    if (s) s.textContent = 'The fire starts by itself in the avionics rack wiring. Circles are the crew.';
  };

  // 2. one fixed origin, lit with the page's own "Open flame" after every start or reset
  let lastTry = 0;
  function tick() {
    const o = $('origin'), status = $('status'), flame = $('igFlame');
    if (!o || !status || !flame || !o.options.length) return;
    hint();
    const opt = [...o.options].find((x) => x.text.startsWith(ORIGIN)) || o.options[0];
    if (o.value !== opt.value) { o.value = opt.value; o.dispatchEvent(new Event('change')); }
    if ($('rpOn') && $('rpOn').checked) return;                          // replaying a recorded run
    if (!status.textContent.startsWith(IDLE) || performance.now() - lastTry < 3000) return;
    lastTry = performance.now();
    setTimeout(() => flame.click(), 1200);                               // a moment of airflow first
  }
  setInterval(tick, 400);
})();
