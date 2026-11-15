# Non-NASA sources and resources used by Black Fox

Everything the project uses that does not come from NASA: peer-reviewed papers, accounts of past
cabin fires, the market and insurance figures behind the business case, and the software and
services the project is built with. The NASA sources are listed separately in
[NASA_SOURCES.md](NASA_SOURCES.md).

Live project: https://blackfoxhackathon.hu

## Peer-reviewed combustion papers

| Paper | Link |
|---|---|
| Thomsen, Fernandez-Pello, Urban, Ruff, Olson (2018). On Simulating Concurrent Flame Spread in Reduced Gravity by Reducing Ambient Pressure. Proceedings of the Combustion Institute | https://europepmc.org/article/MED/31832025 |
| Link, Huang, Fernandez-Pello, Olson, Ferkul (2018). The Effect of Gravity on Flame Spread over PMMA Cylinders. Scientific Reports | https://europepmc.org/article/MED/29317681 |
| Smooke, Long et al. (2004). Investigation of the transition from lightly sooting towards heavily sooting co-flow ethylene diffusion flames. Combustion Theory and Modelling 8(3) | https://doi.org/10.1088/1364-7830/8/3/009 |
| Luque, Jeffries, Smith, Crosley, Walsh, Long, Smooke (2000). CH(A-X) and OH(A-X) optical emission in an axisymmetric laminar diffusion flame. Combustion and Flame 122 | https://doi.org/10.1016/S0010-2180(00)00112-7 |
| Smooke, Long et al. (2000). Experimental and computational study of temperature, species, and soot in buoyant and non-buoyant coflow laminar diffusion flames. Proceedings of the Combustion Institute 28 | https://doi.org/10.1016/S0082-0784(00)80603-7 |
| Walsh, Long, Tanoff, Smooke (1998). Experimental and computational study of CH, CH*, and OH* in an axisymmetric laminar diffusion flame. Proceedings of the Combustion Institute 27 | https://doi.org/10.1016/S0082-0784(98)80453-0 |
| Ju et al. (2019). Dynamics of cool flames. Progress in Energy and Combustion Science | https://doi.org/10.1016/j.pecs.2019.100787 |
| Understanding Cool Flames and Warm Flames. Proceedings of the Combustion Institute (2021) | https://doi.org/10.1016/j.proci.2020.09.019 |
| Study of the low-temperature reactivity of large n-alkanes through cool diffusion flame extinction. Combustion and Flame (2017) | https://doi.org/10.1016/j.combustflame.2017.01.028 |

## Past cabin fires and smoke events

| Account | Link |
|---|---|
| Mir EO-23 (the 1997 Mir fire) | https://en.wikipedia.org/wiki/Mir_EO-23 |
| Spacefacts: Mir-23 crew and the fire | https://spacefacts.de/mir/english/mir-23.htm |
| ARRL bulletin ARLS005 (1997), the Mir fire | https://www.arrl.org/w1aw-bulletins-archive/ARLS005/1997 |
| SpaceRef: ISS Elektron leak and emergency (2006) | https://spaceref.com/?p=25110 |
| Slice of SciFi: ISS crew detects smoke-like smell in the Russian segment (2006) | https://www.sliceofscifi.com/2006/09/18/space-station-crew-detects-smoke-like-smell-in-russian-segment/ |
| GlobalSecurity / RIA Novosti: ISS Russian segment incident (2006) | https://www.globalsecurity.org/space/library/news/2006/space-061101-rianovosti01.htm |
| Aerospace America (AIAA): Artemis II astronauts reflect on the mission | https://aerospaceamerica.aiaa.org/artemis-ii-astronauts-praise-orion-capsule-reflect-on-mission-impact/ |

## Market, insurance and business figures

| Source | Link |
|---|---|
| OECD (2023). The Space Economy in Figures: Responding to Global Challenges | https://doi.org/10.1787/fa5494aa-en |
| World Economic Forum and McKinsey (2024). Space: The $1.8 Trillion Opportunity for Global Economic Growth | https://www.weforum.org/publications/space-the-1-8-trillion-opportunity-for-global-economic-growth/ |
| Paravano et al. (2025). Toward the LEO economy: A value assessment of commercial space stations. Acta Astronautica | https://doi.org/10.1016/j.actaastro.2024.11.060 |
| SpaceNews: NASA ISS transition report (2022) | https://spacenews.com/?p=123641 |
| Seradata: Profitable 2024 for space insurers does not make up for dire 2023 | https://www.seradata.com/profitable-2024-for-space-insurers-does-not-make-up-for-dire-2023 |
| Seradata: Space insurance, promising start to the year marred only by MethaneSAT claim | https://www.slingshot.space/seradata-blog/space-insurance-promising-start-to-the-year-marred-only-by-methanesat-claim |
| Gallagher: Space Insurance Market Update Q1 2025 | https://specialty.ajg.com/plane-talking/space-insurance-update-q1-2025 |
| Gallagher: Space Insurance Market Update Q1 2026 | https://specialty.ajg.com/plane-talking/space-insurance-market-update-q1-2026 |
| Bensoussan (2010). Space tourism risks: A space insurance perspective. Acta Astronautica | https://doi.org/10.1016/j.actaastro.2010.01.009 |
| van Oijhuizen Galhego Rosa (2013). New challenges for the insurance sector to private human access to space. Acta Astronautica 92 | https://doi.org/10.1016/j.actaastro.2012.11.016 |
| Luinaud and Salmon (2023). The contribution of space objects insurance regulations to space traffic management. J. Space Safety Engineering 10 | https://doi.org/10.1016/j.jsse.2022.12.004 |

## Standards

| Standard | Link |
|---|---|
| ASTM D2863: Limiting Oxygen Index (handbook flammability values for materials without NASA data) | https://www.astm.org/d2863-19.html |

## Software, models and services

| Tool | What we use it for | Link |
|---|---|---|
| Three.js | 3D rendering in the browser (cabin, CFD view) | https://threejs.org/ |
| Blender | building and baking the 3D habitat, terrain and globe assets from code | https://www.blender.org/ |
| FastAPI | the web backend and API | https://fastapi.tiangolo.com/ |
| Model Context Protocol | the SI's tool server | https://modelcontextprotocol.io/ |
| gpt-oss (OpenAI open-weight models) | the SI's language model | https://huggingface.co/openai/gpt-oss-120b |
| Groq | hosting the open models | https://groq.com/ |
| Google Gemini API | fallback language model | https://ai.google.dev/ |
| all-MiniLM-L6-v2 | local semantic search over the NASA PDFs | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 |
