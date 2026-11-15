# Pitch deck: Black Fox · Flame in Freefall

A 2-minute deck that plays by itself while we talk: 14 slides in a 120 s loop, plus five
appendix slides (A1–A5) for questions. One HTML file with local fonts and images; it needs no
network.

| File | What it is |
|---|---|
| `deck.html` | the deck (open it in Chrome, Brave or Firefox) |
| `deck-loop.mp4` | the loop recorded once, 1920 × 1080, 120 s: the safest file to play in the background |
| `deck.pdf` | one page per slide (1–14, then A1–A5), each in its final state: for the submission |
| `SPEAKER_SCRIPT.md`, `SPEAKER_SCRIPT.tech.md` | what to say on each slide (investor and technical versions) |
| `FABLE_DECK_PROMPT.md` | the brief the deck was built from |

## On the day

1. Copy the whole `pitch/` folder to the presentation laptop (the deck reads `assets/`).
2. Serve it locally, because some browsers block local fonts on `file://`:

   ```bash
   python3 -m http.server 8766 --directory pitch
   ```

3. Open `http://127.0.0.1:8766/deck.html?auto` and press `F` for fullscreen. The loop starts on its
   own and returns to slide 1 after slide 14. Start talking on the first slide.

If anything goes wrong with the browser, play `deck-loop.mp4` full screen instead: it is the same loop.

## Keys

| Key | Does |
|---|---|
| `→` or `Space` | next slide |
| `←` | previous slide |
| `A` | start or stop the loop |
| `P` | pause or resume the loop |
| `F` | fullscreen |
| `Home` | back to slide 1 |
| `G` | jump to the appendix (A1 cost model, A2 NASA considerations, A3 architecture, A4 business model, A5 our own model) |

The mouse cursor hides after 2 s. `deck.html#5` opens slide 5, `deck.html#a2` opens appendix A2, and
`deck.html?still` shows every slide in its final state without motion.

## Timing

| Slide | Seconds | Slide | Seconds |
|---|---|---|---|
| 1 · Title | 6 | 8 · Under the hood | 9 |
| 2 · The stakes | 9 | 9 · What it costs | 9 |
| 3 · Why the Moon is harder | 9 | 10 · How it makes money | 10 |
| 4 · The gap | 8 | 11 · Who it's for | 10 |
| 5 · What it does | 12 | 12 · What's next | 7 |
| 6 · NASA's brief, answered | 11 | 13 · Our own model | 8 |
| 7 · The Super Intelligence | 8 | 14 · Close | 4 |

Total: 120 s. Change a slide's time with its `data-dur` attribute in `deck.html`.

## Rebuilding the exports

Start the server as above, then from the repository root:

```bash
node pitch/tools/export.mjs pdf
```

```bash
node pitch/tools/export.mjs video
```

Both drive headless Brave over the DevTools protocol (`pitch/tools/cdp.mjs`; set `BROWSER=` for
another Chromium). The PDF needs `pdfunite` (poppler), the video `ffmpeg`. The video is rendered
frame by frame on a manual clock, so it takes a few minutes but the motion is even.

The gap-map and chart data on slides 3, 4 and 6 come from the project's own data files; refresh them
with `.venv/bin/python pitch/tools/sync_envelopes.py`. Product screenshots: `node pitch/tools/capture_screens.mjs lab|ai`.
