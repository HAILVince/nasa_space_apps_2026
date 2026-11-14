"""Site text in Hungarian and English.

blackfoxhackathon.hu is Hungarian by default, blackfoxhackathon.online is
English; `?lang=hu` / `?lang=en` overrides it (remembered in a cookie).
Edit the copy here - the templates only reference these keys.
"""

LANGS = ("hu", "en")

TEXT = {
    "hu": {
        "lang_name": "Magyar",
        "other_lang": "en",
        "other_lang_label": "English",
        "title": "Black Fox Hackathon",
        "tagline": "NASA Space Apps Challenge 2026",
        "nav_home": "Főoldal",
        "nav_about": "Rólunk",
        "nav_how": "Hogyan működik",
        "nav_faq": "GYIK",
        "nav_research": "Kutatási adatbázis",
        "nav_mars": "Mars 3D",
        "nav_ask": "Kérdezd a rókát",
        "home_research_title": "Tűz súlytalanságban",
        "home_research_lead": "Központi adatbázis a NASA kutatásairól: hogyan ég a láng mikrogravitációban és szabadesésben – "
                              "ejtőtornyoktól az ISS-en végzett kísérletekig.",
        "home_research_cta": "Az adatbázis megnyitása",
        "home_lab_title": "A róka: MI-ügynök eszközökkel",
        "home_lab_lead": "A róka nem csak beszél: keres az adatbázisban, fizikai számításokat futtat, és emlékszik rád. "
                         "Egy MCP szerveren keresztül éri el az eszközeit.",
        "home_mars_title": "Mars, élőben renderelve",
        "home_mars_lead": "Procedurálisan generált, forgatható 3D Mars – közvetlenül a böngésződben.",
        "home_mars_cta": "Teljes képernyő",
        "records": "rekord",
        "facts": "mérési adat",
        "research_title": "Kutatási adatbázis",
        "research_lead": "NASA (és partner) kutatások a tűzről és lángokról mikrogravitációban. A „kurált” rekordok a "
                         "repóból jönnek; a „közösségi” rekordokat az MI vagy felhasználók adták hozzá, nincsenek ellenőrizve.",
        "research_search": "Keresés (pl. cool flame, ejtőtorony, Saffire)",
        "research_all": "Mind",
        "research_none": "Nincs találat.",
        "research_facts": "Adatok",
        "research_sources": "Források",
        "research_back": "Vissza az adatbázishoz",
        "research_ask": "Kérdezd a rókát erről",
        "status_curated": "kurált",
        "status_community": "közösségi",
        "kind_experiment": "kísérlet", "kind_facility": "létesítmény", "kind_finding": "eredmény",
        "kind_concept": "fogalom", "kind_incident": "esemény", "kind_dataset": "adatkészlet", "kind_other": "egyéb",
        "mars_title": "Mars 3D",
        "mars_lead": "Húzd a forgatáshoz, görgess a nagyításhoz. A felszín procedurálisan generált – vizuális illusztráció, nem térkép.",
        "lab_new": "Új beszélgetés",
        "lab_thinking": "A róka gondolkodik és eszközöket használ…",
        "lab_tools_used": "Használt eszközök",
        "lab_memory": "Amire a róka emlékszik rólad",
        "lab_memory_empty": "Még semmi. Mondd el pl. a csapatod nevét vagy a projektötleted.",
        "lab_forget_all": "Mindent felejts el",
        "lab_examples": ["Mennyi ideig tart a szabadesés a NASA legnagyobb ejtőtornyában?",
                         "Mit fedezett fel a FLEX kísérlet?",
                         "Mekkora a felhajtóerő okozta áramlás egy 2 cm-es lángnál a Földön és az ISS-en?",
                         "Mennyi idő alatt ég el egy 3 mm-es heptáncsepp?"],
        "lab_intro": "Kérdezz a mikrogravitációs égésről, kérj számítást, vagy mondd el, min dolgozik a csapatod.",
        "hero_kicker": "NASA Space Apps Challenge 2026",
        "hero_title": "Kódolj a csillagokig.",
        "hero_lead": "A Black Fox Hackathon csapata NASA nyílt adataiból épít valódi megoldásokat "
                     "a Föld és az űr problémáira – egyetlen hétvége alatt.",
        "hero_cta": "Kérdezd a rókát",
        "hero_cta2": "Hogyan működik?",
        "about_title": "Miről szól?",
        "about_body": [
            "A NASA Space Apps Challenge a világ legnagyobb éves űr- és tudományos hackathonja. "
            "A NASA és partnerügynökségei kihívásokat tesznek közzé, a csapatok pedig nyílt "
            "adatokból készítenek rájuk alkalmazásokat, vizualizációkat és prototípusokat.",
            "A Black Fox csapat programozókat, tervezőket és tudomány iránt rajongókat hoz össze, "
            "hogy együtt építsünk valami olyat, ami a hétvége után is számít.",
        ],
        "how_title": "Hogyan működik",
        "steps": [
            ("Csapatépítés", "Fejlesztők, designerek, kutatók – minden tudásra szükség van."),
            ("Kihívás kiválasztása", "A NASA kihívásai közül választunk egyet, ami tényleg érdekel minket."),
            ("Építés", "NASA nyílt adatokból, gyorsan és sokat iterálva készül a prototípus."),
            ("Bemutatás", "Rövid videó és demó a zsűrinek – és a világnak."),
        ],
        "faq_title": "Gyakori kérdések",
        "faq": [
            ("Kell hozzá űrkutatási tudás?", "Nem. A kíváncsiság fontosabb – az adatokat és a "
             "háttéranyagot a NASA biztosítja."),
            ("Milyen technológiát használunk?", "Bármit, ami működik: Python, web, adatvizualizáció, "
             "gépi tanulás, hardver."),
            ("Hol látom a projektet?", "A forráskód nyilvános a GitHubon, ez a weboldal is onnan "
             "frissül automatikusan."),
        ],
        "ask_title": "Kérdezd a rókát",
        "ask_lead": "MI-ügynök a NASA mikrogravitációs égéskutatásaihoz: adatbázis, fizikai számítások, memória.",
        "ask_placeholder": "Pl.: Miért gömb alakú a gyertyaláng az űrben?",
        "ask_button": "Kérdezem",
        "ask_answer": "A róka",
        "ask_you": "Te",
        "ask_model": "Modell",
        "ask_empty": "Írj be egy kérdést.",
        "ask_too_long": "A kérdés túl hosszú (legfeljebb {n} karakter).",
        "ask_rate": "Túl sok kérdés rövid idő alatt – várj egy percet.",
        "ask_unavailable": "A róka most nem elérhető. Próbáld újra kicsit később.",
        "ask_disclaimer": "A válaszokat mesterséges intelligencia generálja, tévedhet.",
        "ai_system": "Te vagy a Black Fox Hackathon csapat segítője (NASA Space Apps Challenge 2026). "
                     "Segíts hackathon-ötletekben, NASA nyílt adatokban, űr- és földtudományban, "
                     "programozásban. Válaszolj magyarul, tömören, legfeljebb néhány bekezdésben. "
                     "Ha nem tudsz valamit (pl. konkrét időpontot, helyszínt), mondd meg őszintén.",
        "footer_source": "Forráskód a GitHubon",
        "footer_note": "Nem hivatalos NASA oldal.",
        "not_found": "Ez az oldal elveszett az űrben.",
        "back_home": "Vissza a főoldalra",
    },
    "en": {
        "lang_name": "English",
        "other_lang": "hu",
        "other_lang_label": "Magyar",
        "title": "Black Fox Hackathon",
        "tagline": "NASA Space Apps Challenge 2026",
        "nav_home": "Home",
        "nav_about": "About",
        "nav_how": "How it works",
        "nav_faq": "FAQ",
        "nav_research": "Research DB",
        "nav_mars": "Mars 3D",
        "nav_ask": "Ask the Fox",
        "home_research_title": "Fire in microgravity",
        "home_research_lead": "A central database of NASA research on how flames burn in microgravity and free fall - "
                              "from drop towers to experiments on the ISS.",
        "home_research_cta": "Open the database",
        "home_lab_title": "The Fox: an AI agent with tools",
        "home_lab_lead": "The Fox doesn't just chat: it searches the database, runs physics calculations and remembers you, "
                         "reaching its tools through an MCP server.",
        "home_mars_title": "Mars, rendered live",
        "home_mars_lead": "A procedurally generated, rotatable 3D Mars - right in your browser.",
        "home_mars_cta": "Full screen",
        "records": "records",
        "facts": "facts",
        "research_title": "Research database",
        "research_lead": "NASA (and partner) research on fire and flames in microgravity. 'Curated' records come from the "
                         "repository; 'community' records were added by the AI or users and are unverified.",
        "research_search": "Search (e.g. cool flame, drop tower, Saffire)",
        "research_all": "All",
        "research_none": "No results.",
        "research_facts": "Facts",
        "research_sources": "Sources",
        "research_back": "Back to the database",
        "research_ask": "Ask the Fox about this",
        "status_curated": "curated",
        "status_community": "community",
        "kind_experiment": "experiment", "kind_facility": "facility", "kind_finding": "finding",
        "kind_concept": "concept", "kind_incident": "incident", "kind_dataset": "dataset", "kind_other": "other",
        "mars_title": "Mars 3D",
        "mars_lead": "Drag to rotate, scroll to zoom. The surface is procedurally generated - a visual, not a map.",
        "lab_new": "New conversation",
        "lab_thinking": "The Fox is thinking and using tools…",
        "lab_tools_used": "Tools used",
        "lab_memory": "What the Fox remembers about you",
        "lab_memory_empty": "Nothing yet. Tell it your team name or project idea.",
        "lab_forget_all": "Forget everything",
        "lab_examples": ["How long is free fall in NASA's biggest drop tower?",
                         "What did the FLEX experiment discover?",
                         "How fast is the buoyant flow near a 2 cm flame on Earth vs on the ISS?",
                         "How long does a 3 mm heptane droplet take to burn?"],
        "lab_intro": "Ask about microgravity combustion, request a calculation, or tell it what your team is building.",
        "hero_kicker": "NASA Space Apps Challenge 2026",
        "hero_title": "Code your way to the stars.",
        "hero_lead": "The Black Fox Hackathon team builds real solutions for problems on Earth "
                     "and in space from NASA's open data - in a single weekend.",
        "hero_cta": "Ask the Fox",
        "hero_cta2": "How it works",
        "about_title": "What is it?",
        "about_body": [
            "The NASA Space Apps Challenge is the largest annual space and science hackathon in the world. "
            "NASA and its partner agencies publish challenges, and teams answer them with apps, "
            "visualizations and prototypes built on open data.",
            "Black Fox brings coders, designers and science enthusiasts together to build something "
            "that still matters after the weekend is over.",
        ],
        "how_title": "How it works",
        "steps": [
            ("Form the team", "Developers, designers, researchers - every skill counts."),
            ("Pick a challenge", "We choose one of NASA's challenges that we genuinely care about."),
            ("Build", "A prototype on NASA open data, built fast with lots of iteration."),
            ("Present", "A short video and demo for the judges - and the world."),
        ],
        "faq_title": "FAQ",
        "faq": [
            ("Do I need space science knowledge?", "No. Curiosity matters more - NASA provides the data "
             "and the background material."),
            ("What technology do we use?", "Whatever works: Python, the web, data visualization, "
             "machine learning, hardware."),
            ("Where can I see the project?", "The source code is public on GitHub, and this website "
             "updates itself from it automatically."),
        ],
        "ask_title": "Ask the Fox",
        "ask_lead": "An AI agent for NASA microgravity combustion research: database, physics tools, memory.",
        "ask_placeholder": "E.g. Why is a candle flame spherical in space?",
        "ask_button": "Ask",
        "ask_answer": "The Fox",
        "ask_you": "You",
        "ask_model": "Model",
        "ask_empty": "Type a question.",
        "ask_too_long": "The question is too long (at most {n} characters).",
        "ask_rate": "Too many questions in a short time - wait a minute.",
        "ask_unavailable": "The fox is unavailable right now. Try again a bit later.",
        "ask_disclaimer": "Answers are AI-generated and may be wrong.",
        "ai_system": "You are the assistant of the Black Fox Hackathon team (NASA Space Apps Challenge 2026). "
                     "Help with hackathon ideas, NASA open data, space and Earth science, and programming. "
                     "Answer in English, concisely, in a few paragraphs at most. If you don't know "
                     "something (e.g. a specific date or venue), say so honestly.",
        "footer_source": "Source on GitHub",
        "footer_note": "Not an official NASA website.",
        "not_found": "This page got lost in space.",
        "back_home": "Back to the home page",
    },
}


def pick_lang(host: str, query_lang: str | None, cookie_lang: str | None) -> str:
    if query_lang in LANGS:
        return query_lang
    if cookie_lang in LANGS:
        return cookie_lang
    host = (host or "").split(":")[0].lower()
    return "hu" if host.endswith(".hu") else "en"
