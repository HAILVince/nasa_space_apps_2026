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
        "nav_ask": "Kérdezd a rókát",
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
        "ask_lead": "Kérdezz a hackathonról, a NASA adatokról vagy egy projektötletről – a róka válaszol.",
        "ask_placeholder": "Pl.: Milyen NASA adatkészlettel lehet erdőtüzeket követni?",
        "ask_button": "Kérdezem",
        "ask_answer": "A róka válasza",
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
        "nav_ask": "Ask the Fox",
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
        "ask_lead": "Ask about the hackathon, NASA data or a project idea - the fox will answer.",
        "ask_placeholder": "E.g. Which NASA dataset can track wildfires?",
        "ask_button": "Ask",
        "ask_answer": "The Fox says",
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
