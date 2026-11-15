# Pitch deck: Black Fox · Flame in Freefall

A deck that plays by itself while we talk: 20 slides in a 3:00 run, timed to the story in `SPEAKER_SCRIPT.md` (2:00 of slides, then 1:00 of video and close). Slides 14–18 are the
detail slides (costs, NASA's brief, architecture, business case, our own model), slide 19 plays the
55 s product walkthrough slide (the 51 s video, then its last frame) (`blackfox-walkthrough.mp4`), slide 20 closes with the team and the QR code.
One HTML file with local fonts, images and video; it needs no network.

| File | What it is |
|---|---|
| `deck.html` | the deck (open it in Chrome, Brave or Firefox) |
| `deck-loop.mp4` | (old order, not yet updated) the loop recorded once, 1920 × 1080 |
| `deck.pptx` | **the final file**: PowerPoint version of the same 20 slides, built in layers from `deck.html`, so text blocks and charts animate in as on the web (fade and rise, charts wipe in) with the same delays, slides fade (slides 2 and 20 wipe in from the left), it advances by itself on the story's timings (3:00), the walkthrough video on slide 19 starts on its own, and it stops on slide 20, where the QR code and the URL are clickable. Speaker notes on every slide hold that slide's part of the story |
| `deck.pdf` | one page per slide, each in its final state: for the submission |
| `SPEAKER_SCRIPT.md`, `SPEAKER_SCRIPT.tech.md` | what to say on each slide (investor and technical versions) |
| `FABLE_DECK_PROMPT.md` | the brief the deck was built from |

## On the day

1. Copy the whole `pitch/` folder to the presentation laptop (the deck reads `assets/`).
2. Serve it locally, because some browsers block local fonts on `file://`:

   ```bash
   python3 -m http.server 8766 --directory pitch
   ```

3. Open `http://127.0.0.1:8766/deck.html?auto` and press `F` for fullscreen. The loop starts on its
   own; the walkthrough video starts by itself on slide 19. After slide 20 it returns to slide 1, so
   press `P` on slide 20 to hold it for questions. Start talking on the first slide.

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
| `G` | jump to the detail slides (slide 14) |

The mouse cursor hides after 2 s. `deck.html#5` opens slide 5 (old links like `#a2` still open the same slide), and
`deck.html?still` shows every slide in its final state without motion.

## Timing

| Slide | Seconds | Slide | Seconds |
|---|---|---|---|
| 1 · Title | 5 | 11 · Who it's for | 9 |
| 2 · The stakes | 13 | 12 · What's next | 4 |
| 3 · Why the Moon is harder | 11 | 13 · Our own model | 4 |
| 4 · The gap | 10 | 14 · Cost model | 4 |
| 5 · What it does | 16 | 15 · NASA considerations | 3 |
| 6 · NASA's brief, answered | 7 | 16 · Architecture | 3 |
| 7 · The Super Intelligence | 6 | 17 · Business case | 3 |
| 8 · Under the hood | 8 | 18 · Our own model, the plan | 3 |
| 9 · What it costs | 5 | 19 · Walkthrough video | 55 |
| 10 · What one fire costs | 6 | 20 · Close, team, QR | 5 |

Total: 180 s (3:00); slides 1–18 add up to 120 s. Change a slide's time with its `data-dur` attribute in `deck.html`.

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
