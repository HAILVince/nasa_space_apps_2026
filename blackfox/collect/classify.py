"""Decides which gravity environment(s) a record belongs to and its topic.

Only three environments are kept: the Moon (lunar gravity), Mars (Martian gravity) and
0 g (microgravity / weightlessness). A record that is not clearly about at least one of
them is dropped by the build step.
"""

import re

GRAVITY = {
    "moon": {"label": "Moon - lunar gravity", "g_m_s2": 1.62, "g_earth": 0.165},
    "mars": {"label": "Mars - Martian gravity", "g_m_s2": 3.71, "g_earth": 0.378},
    "zero_g": {"label": "0 g - microgravity / weightlessness (orbit, free fall)", "g_m_s2": 0.0, "g_earth": 0.0},
}
THRESHOLD = 3.0   # title mention = 3, keyword mention = 2, each mention in the summary = 1 (max 3 per term)


def _rx(*alts: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alts) + r")(?![a-z0-9])")


_NOT_OUR_MOON = re.compile(r"(?:icy|galilean|jovian|saturnian|martian|inner|outer|small|regular|irregular|shepherd|"
                           r"jupiter'?s?|saturn'?s?|neptune'?s?|uranus'?s?|pluto'?s?|mars'?s?|a|its|largest) moon(?![a-z])")

_SIGNALS: dict[str, list[tuple[re.Pattern, float]]] = {
    "moon": [
        (_rx(r"lunar", r"moon", r"moon's", r"cislunar", r"translunar", r"selenodesy", r"selenograph\w*"), 1.0),
        (_rx(r"apollo 1[1-7]", r"apollo (?:program|missions?|lunar|astronauts?|samples?)", r"artemis"), 1.0),
        (_rx(r"lunar[- ]gravity", r"1/6(?:th)?[- ]?g", r"one[- ]sixth[- ]?g\w*", r"0\.16\d? ?g"), 2.0),
        (_rx(r"partial[- ]gravity", r"hypogravity", r"fractional[- ]gravity"), 1.0),
        (_rx(r"regolith"), 0.5),
    ],
    "mars": [
        (_rx(r"mars", r"mars's", r"martian", r"red planet"), 1.0),
        (_rx(r"martian[- ]gravity", r"mars[- ]gravity", r"3/8(?:th)?s?[- ]?g", r"three[- ]eighths[- ]?g\w*", r"0\.38 ?g"), 2.0),
        (_rx(r"partial[- ]gravity", r"hypogravity", r"fractional[- ]gravity"), 1.0),
        (_rx(r"phobos", r"deimos", r"regolith"), 0.5),
    ],
    "zero_g": [
        (_rx(r"microgravity", r"micro[- ]gravity", r"weightless\w*", r"zero[- ]g(?:ravity)?", r"(?<![.,])0[- ]?g",
             r"reduced[- ]gravity", r"low[- ]gravity", r"free[- ]fall(?:ing)?", r"drop[- ](?:tower|shaft|tube)s?",
             r"parabolic[- ]flights?", r"space[- ]?flights?", r"space stations?", r"iss", r"spacelab", r"skylab",
             r"clinostat\w*", r"random positioning machine", r"hind[- ]?limb (?:unloading|suspension)",
             r"head[- ]down (?:tilt|bed ?rest)"), 1.0),
        (_rx(r"partial[- ]gravity", r"hypogravity", r"astronauts?", r"cosmonauts?", r"spacecraft", r"orbital", r"bed ?rest",
             r"on[- ]orbit", r"in[- ]orbit", r"low[- ]earth[- ]orbit", r"space shuttle", r"crew(?:ed)?"), 0.5),
    ],
}

# topic -> terms; the best-scoring topic wins (title counts 3x). Order = tie-break priority.
_TOPICS: list[tuple[str, str, re.Pattern]] = [(name, label, _rx(*terms)) for name, label, terms in [
    ("combustion_fire", "Combustion, flames and fire safety",
     [r"combustion", r"flames?", r"fires?", r"ignition", r"soot", r"burning", r"flammab\w*", r"extinguish\w*", r"smolder\w*", r"flame spread"]),
    ("fluids_heat_transfer", "Fluids, boiling and heat transfer",
     [r"fluids?", r"boiling", r"capillar\w*", r"two[- ]phase", r"heat transfer", r"convection", r"bubbles?", r"droplets?", r"wetting",
      r"slosh\w*", r"cryogen\w*", r"propellant (?:management|transfer|tank)s?", r"heat pipes?", r"condens\w*", r"marangoni", r"surface tension"]),
    ("materials_manufacturing", "Materials science and in-space manufacturing",
     [r"crystal growth", r"solidification", r"alloys?", r"materials (?:processing|science)", r"manufactur\w*", r"3d[- ]print\w*",
      r"additive", r"welding", r"sinter\w*", r"semiconductors?", r"containerless", r"levitat\w*", r"ceramics?", r"polymers?", r"composites?"]),
    ("human_health", "Human health, physiology and performance",
     [r"bone", r"muscle", r"musculoskeletal", r"cardiovascular", r"physiolog\w*", r"medical", r"medicine", r"vestibular", r"immune",
      r"sleep", r"crew health", r"countermeasures?", r"exercise", r"psycholog\w*", r"behaviou?ral", r"nutrition", r"vision", r"ocular",
      r"intracranial", r"locomotion", r"gait", r"posture", r"orthostatic", r"astronaut health", r"human factors", r"neuro\w*", r"cognitive"]),
    ("biology_plants", "Space biology, plants and microbes",
     [r"plants?", r"cells?", r"genes?", r"genom\w*", r"transcript\w*", r"microb\w*", r"bacteri\w*", r"mice", r"mouse", r"rats?", r"rodents?",
      r"arabidopsis", r"seeds?", r"seedlings?", r"organisms?", r"tissue", r"drosophila", r"elegans", r"protein", r"biofilms?", r"fung\w*",
      r"astrobiolog\w*", r"crop", r"germination", r"gravitropism"]),
    ("life_support", "Life support, air, water and food",
     [r"life support", r"eclss?", r"co2 removal", r"carbon dioxide removal", r"water (?:recovery|recycling|reclamation|processing)",
      r"oxygen generation", r"air revitalization", r"atmosphere revitalization", r"waste (?:water|management|processing)",
      r"food (?:production|system)s?", r"bioregenerative", r"trace contaminants?", r"cabin atmosphere", r"closed[- ]loop", r"hydroponic\w*"]),
    ("habitats_structures", "Habitats, bases and structures",
     [r"habitats?", r"habitation", r"outposts?", r"shelters?", r"inflatable", r"pressurized modules?", r"structures?", r"structural",
      r"construction", r"airlocks?", r"settlements?", r"lunar base", r"moon base", r"mars base", r"surface base",
      r"colon\w+", r"greenhouse", r"lava tubes?"]),
    ("isru_regolith_dust", "Regolith, dust and in-situ resources (ISRU)",
     [r"regolith", r"in[- ]situ resource\w*", r"isru", r"dust", r"simulants?", r"excavat\w*", r"mining", r"water ice", r"propellant production",
      r"oxygen (?:extraction|production)", r"soil mechanics", r"geotechnical", r"resource utilization", r"volatiles?", r"electrostatic"]),
    ("power_thermal", "Power and thermal control",
     [r"power (?:system|generation|source|supply|plant|station)s?", r"solar (?:array|cell|power|panel)s?", r"photovoltaic\w*", r"fission",
      r"nuclear (?:power|reactor)s?", r"reactors?", r"batter(?:y|ies)", r"fuel cells?", r"thermal control", r"radiators?", r"energy storage",
      r"radioisotope", r"thermal management", r"heat rejection"]),
    ("propulsion_landing_mobility", "Propulsion, landing and mobility",
     [r"landers?", r"landing", r"descent", r"ascent", r"propulsion", r"rovers?", r"mobility", r"entry", r"aerobrak\w*", r"aerocapture",
      r"trajector\w*", r"orbit insertion", r"launch", r"plumes?", r"engines?", r"thrusters?", r"parachutes?", r"wheels?", r"traverse"]),
    ("communications_navigation", "Communications, navigation and data",
     [r"communications?", r"telecommunications?", r"networks?", r"networking", r"antennas?", r"navigation", r"gps", r"gnss", r"telemetry",
      r"relay", r"radio", r"optical comm\w*", r"laser comm\w*", r"data systems?", r"avionics", r"positioning", r"tracking"]),
    ("radiation", "Radiation environment and shielding",
     [r"radiation", r"cosmic rays?", r"gcr", r"solar particle\w*", r"dosimet\w*", r"shielding", r"heavy ions?", r"dose"]),
    ("gravity_field_geodesy", "Gravity field and geodesy",
     [r"gravity (?:field|model|anomal\w+|data|mapping|map|gradient)s?", r"mascons?", r"geodesy", r"geodetic", r"grail", r"gravimet\w*",
      r"bouguer", r"free[- ]air", r"tidal", r"tides", r"love number", r"moment of inertia", r"crustal thickness"]),
    ("spacesuits_eva", "Spacesuits and EVA",
     [r"eva", r"extravehicular", r"space ?suits?", r"pressure suits?", r"gloves?"]),
    ("robotics_operations", "Robotics, autonomy and operations",
     [r"robot\w*", r"teleoperat\w*", r"autonom\w*", r"mission operations", r"logistics", r"crew time", r"telerobotic\w*", r"manipulators?"]),
    ("surface_environment_geology", "Surface environment and geology",
     [r"geolog\w*", r"geophys\w*", r"geochem\w*", r"craters?", r"cratering", r"basalt\w*", r"minerals?", r"mineralogy", r"volcan\w*",
      r"magma\w*", r"tecton\w*", r"atmospher\w*", r"climate", r"seismic\w*", r"meteorites?", r"topograph\w*", r"dust storms?",
      r"sediment\w*", r"stratigraph\w*", r"crust", r"crustal", r"mantle", r"polar (?:caps?|ice|regions?|deposits?|layered)",
      r"lunar samples?", r"mare", r"maria", r"highlands?", r"permafrost", r"aeolian", r"fluvial", r"surface (?:composition|temperatures?)"]),
    ("missions_architecture", "Missions, programs and architectures",
     [r"mission (?:design|architecture|concept|planning)s?", r"exploration (?:program|architecture|strategy|initiative)", r"architectures?",
      r"missions?", r"program", r"roadmap", r"systems engineering", r"requirements", r"spacecraft"]),
]]
TOPICS = {name: label for name, label, _ in _TOPICS} | {"general": "General / other"}


# names that contain a signal word without being about the environment
_NOISE = re.compile(r"space ?flight cent(?:er|re)s?|human space ?flight (?:program|office)")
# "MARS" in capitals is usually an acronym (software, statistics, instruments) unless the text is about the planet
_MARS_ACRONYM = re.compile(r"\bMARS\b")
_MARS_CONTEXT = re.compile(r"martian|planet|rover|lander|landing|spacecraft|regolith|atmospher|orbit|exploration|astronaut|"
                           r"habitat|nasa|phobos|crater|red planet|solar system|missions? to mars|on mars|mars mission")


def _text(v) -> str:
    if isinstance(v, (list, tuple)):
        v = "; ".join(str(x) for x in v)
    return _NOISE.sub(" ", _NOT_OUR_MOON.sub(" ", str(v or "").lower()))


def gravity_scores(title, keywords, summary) -> dict[str, float]:
    t, k, s = _text(title), _text(keywords), _text(summary)
    out = {}
    for g, signals in _SIGNALS.items():
        score = 0.0
        for rx, w in signals:
            score += w * (3 * bool(rx.search(t)) + 2 * bool(rx.search(k)) + min(3, len(rx.findall(s))))
        out[g] = score
    if out["mars"] and _MARS_ACRONYM.search(f"{title} {summary}") and not _MARS_CONTEXT.search(f"{t} {k} {s}"):
        out["mars"] = 0.0
    return out


def classify(title, keywords, summary) -> tuple[list[str], str, float]:
    """-> (gravity list, best first; topic; relevance score). Empty list = not relevant."""
    scores = gravity_scores(title, keywords, summary)
    gravity = [g for g, s in sorted(scores.items(), key=lambda kv: -kv[1]) if s >= THRESHOLD]
    if not gravity:
        return [], "general", 0.0
    t, k, s = _text(title), _text(keywords), _text(summary)
    best, best_score = "general", 0.0
    for name, _, rx in _TOPICS:
        sc = 3 * len(rx.findall(t)) + 2 * len(rx.findall(k)) + min(6, len(rx.findall(s)))
        if sc > best_score:
            best, best_score = name, sc
    return gravity, best, max(scores.values())


# Wikipedia search also returns songs, films and people that merely share a word with the topic
_POP_TITLE = re.compile(r"\((?:[^)]*\b)?(?:album|song|film|novel|band|ep|series|episode|game|soundtrack|book|magazine|comics?|"
                        r"musical|play|single|opera|manga|anime|painting|poem)\)", re.I)
_POP_INTRO = re.compile(r"\b(?:is|was|are) (?:an?|the) [^.]{0,90}\b(?:songs?|albums?|films?|novels?|bands?|television|video game|"
                        r"pornographic|singles?|comics?|manga|anime|episodes?|musician|actor|actress|singer|rapper|"
                        r"documentary|sitcom|poem|painting|studio|record label)\b", re.I)


def is_pop_culture(title: str, summary: str) -> bool:
    return bool(_POP_TITLE.search(title or "") or _POP_INTRO.search((summary or "")[:300]))
