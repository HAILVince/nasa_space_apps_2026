# Pitch deck: Black Fox · Flame in Freefall

13 slides for a 3-minute pitch, advanced by hand with a presentation remote: the title, ten content
slides, the 51 s product walkthrough (`blackfox-walkthrough.mp4`) and the close with the team and the
QR code. Nothing moves to the next slide by itself; the text and charts on each slide animate in on
their own after you click. The words to say, and where to click, are in `SPEAKER_SCRIPT.md`.
One HTML file with local fonts, images and video; it needs no network.

| File | What it is |
|---|---|
| `deck.html` | the deck (open it in Chrome, Brave or Firefox) |
| `deck.pptx` | **the final file**: PowerPoint version of the same 13 slides, built in layers from `deck.html`, so text blocks and charts animate in by themselves as on the web (fade and rise, charts wipe in) after each click. Slides fade into each other (slides 2 and 13 wipe in from the left). Every slide change is a click; the walkthrough video on slide 12 starts on its own; the QR code and the URL on slide 13 are clickable. Speaker notes on every slide hold that slide's part of the story |
| `deck.pdf` | one page per slide, each in its final state: for the submission |
| `SPEAKER_SCRIPT.md`, `SPEAKER_SCRIPT.tech.md` | what to say (investor and technical versions; the technical one still follows the older order) |
| `deck-loop.mp4` | outdated: a recording of an earlier self-playing version |
| `FABLE_DECK_PROMPT.md` | the brief the deck was first built from |

## The slides

| # | Slide | # | Slide |
|---|---|---|---|
| 1 | Title | 8 | What it costs us (with the cost breakdown) |
| 2 | The stakes | 9 | What one cabin fire costs (the business case) |
| 3 | Why the Moon is harder | 10 | Who it's for and how it grows |
| 4 | The gap in NASA's tests | 11 | What's next and our own fire model (with the plan) |
| 5 | What it does | 12 | Walkthrough video |
| 6 | NASA's brief, answered (all eight considerations) | 13 | Close: team, QR code |
| 7 | The SI and what it runs on (with the architecture) | | |

## On the day

1. Copy the whole `pitch/` folder to the presentation laptop (the deck reads `assets/`).
2. Either open `deck.pptx` in PowerPoint and start the slide show, or serve the HTML deck locally
   (some browsers block local fonts on `file://`):

   ```bash
   python3 -m http.server 8766 --directory pitch
   ```

   then open `http://127.0.0.1:8766/deck.html` and press `F` for fullscreen.
3. Click through with the remote as the script marks. The last slide stays up for questions.

## Keys (HTML deck)

| Key | Does |
|---|---|
| `PageDown`, `→`, `↓`, `Space`, `Enter` | next slide (what a presentation remote sends) |
| `PageUp`, `←`, `↑` | previous slide |
| `P` | pause or resume the walkthrough video |
| `F` | fullscreen |
| `Home` / `End` | first / last slide |

The mouse cursor hides after 2 s. `deck.html#5` opens slide 5, and `deck.html?still` shows every slide
in its final state without motion.

## Rebuilding the PDF

Start the server as above, then from the repository root:

```bash
node pitch/tools/export.mjs pdf
```

It drives headless Brave over the DevTools protocol (`pitch/tools/cdp.mjs`; set `BROWSER=` for
another Chromium) and needs `pdfunite` (poppler). The `video` mode of the same script records the old
self-playing loop and no longer works with the hand-advanced deck.

The gap-map and chart data on slides 3, 4 and 6 come from the project's own data files; refresh them
with `.venv/bin/python pitch/tools/sync_envelopes.py`. Product screenshots: `node pitch/tools/capture_screens.mjs lab|ai`.
