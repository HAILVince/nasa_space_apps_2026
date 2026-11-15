# Pitch script: Black Fox · Flame in Freefall

**Running order:** 0:00–2:00 you speak while the deck plays by itself (12 slides) → 2:00–3:00 demo video of the site.

**Pace:** about 290 words in 2 minutes (≈ 145 words per minute). That's calm, not rushed. Start the deck on your first word.

**If the deck gets ahead of you,** drop the second sentence of that slide. **If you're ahead,** pause and let the slide land. Never read the screen; the slides only carry ≤ 15 words, so you are the story.

---

## Part 1: with the deck (0:00–2:00)

| Time | Slide | Say |
|---|---|---|
| 0:00 | 1 · Title | "We're Black Fox. We built a fire-safety lab for future Moon and Mars cabins." |
| 0:07 | 2 · The stakes | "Apollo 1. Mir. This year, a smoke alarm on Artemis II. In a spacecraft, fire is the one emergency you can't walk away from." |
| 0:17 | 3 · Why the Moon is harder | "It gets harder. Moon cabins will run at lower pressure and 34 percent oxygen, and in low gravity some materials burn even more easily." |
| 0:27 | 4 · The gap | "NASA has decades of microgravity fire data. We put all 24 investigations on one map, so you can see where nobody has tested yet." |
| 0:36 | 5 · What it does | "An engineer sets the cabin and starts a fire. Pick the place and the air, choose what burns, like wire insulation next to a stuck fan, and see spread, smoke, CO and time to put it out." |
| 0:50 | 6 · NASA's brief | "That's NASA's brief, point by point: we rank the research for each mission, extract test conditions for modelling, traced to the source, and test detection and suppression. Every listed consideration is covered." |
| 1:04 | 7 · The AI | "On top sits an AI engineer. It sees your scenario, re-runs it, and cites the NASA document behind every claim." |
| 1:13 | 8 · Under the hood | "Under the hood: open models on Groq, tools over MCP, a local vector database built from 52 combustion research papers, and 3D and CFD running right in the browser." |
| 1:24 | 9 · Cost | "It's cheap to run: about 130 dollars a year today. Even with a paid AI for a hundred engineers it's around ten thousand, and the cost per engineer falls." |
| 1:35 | 10 · Market | "Our users are teams designing habitats and spacecraft, free for universities. A new environment is new data, not new code, so it scales, even to sealed spaces on Earth. Funding: ESA incubation, Horizon Europe, NASA SBIR." |
| 1:47 | 11 · What's next | "Next: Claude for deeper reasoning, one central NASA database, a desktop app for full CFD, and your own cabin models." |
| 1:55 | 12 · Handoff | "Every number traces back to NASA. Here's what it looks like." |

→ Start the video right after "Here's what it looks like."

## Part 2: during the demo video (2:00–3:00)

**If the video has its own voice-over:** stay quiet and let it play. Say only the closing line at the end.

**If the video is silent,** narrate it. Match these lines to whatever the video actually shows, and cut any line whose shot isn't in it.

| Video | Say |
|---|---|
| 0:00–0:10 · landing page → lab | "We start on the lunar surface, inside our HAB-01 module." |
| 0:10–0:30 · set up and run a fire | "Lower the pressure to 56.5 kilopascals, raise oxygen to 34 percent, pick wire insulation, place the fire by the fan, and run. The flame spreads, the smoke follows the airflow, and the alarm trips." |
| 0:30–0:45 · evidence page, gap map | "The evidence page shows which NASA experiments came close to this atmosphere, ranked for a lunar base, and where the data runs out." |
| 0:45–0:57 · AI console | "Then we ask the AI why it burned. It answers with citations you can open." |
| 0:57–1:00 · end card | "That's Black Fox. Thank you." |

**Closing line (both cases):** "That's Black Fox. Thank you, and we're happy to take questions."

---

## Remember this: one anchor word per slide

**Fox → no exit → harder → map → watch → brief → AI → hood → cheap → scales → next → see it**

## Numbers to have ready

| Number | What it means |
|---|---|
| **24** | PSI combustion investigations, all on one map |
| **34 % O₂ at 56.5 kPa** (≈ 8.2 psi) | the planned Moon–Mars exploration cabin atmosphere |
| **−4 % O₂** | materials burned at up to 4 % less oxygen in 0 g than in NASA's 1 g tests |
| **55 ppm** | NASA's 1-hour carbon monoxide limit (SMAC) |
| **18** | materials with measured NASA-STD-6001 flammability limits |
| **52** | NASA PDFs in the local vector database |
| **≈ $130 / yr** today · **≈ $10.1k / yr** at 100 engineers | infrastructure cost (VPS $120 + one .online domain $10; deck appendix A1) |

## Likely questions (one-line answers)

- **"How accurate is the simulator?"** "It's a screening model built on NASA-STD-6001 limits and drop-tower correlations. It tells you which designs to test first, and it doesn't replace NASA material testing."
- **"What about Moon and Mars gravity, when PSI has no partial-gravity data?"** "We bound it between microgravity and 1 g results, use E-FIELD as a stand-in, and the coming LUCI and FM2 lunar tests slot straight in."
- **"Why open models instead of a big paid one?"** "Free for the prototype, with key rotation and fallback. Switching to Claude is our first upgrade; the tools stay the same."
- **"Can the AI make things up?"** "Every claim must cite a NASA record, and citations we can't match are flagged as unverified."
