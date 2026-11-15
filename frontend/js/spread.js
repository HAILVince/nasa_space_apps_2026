// The room-to-room fire spread simulator page: shared top bar. The simulator's own code is in spread.html.
import { t } from './i18n.js';
import { bindChrome } from './common.js';

window.bfT = t;      // the page's own script (spread.html) uses the shared strings for the calculator block
bindChrome();
