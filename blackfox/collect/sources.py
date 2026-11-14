"""The public sources the knowledge base is collected from. Text and numbers only:
no images, PDFs or data files are downloaded.

Every source is a function  harvest(http, sink, progress)  that calls sink(records) with
normalised records and remembers finished work in `progress`, so an interrupted run
continues where it stopped.

Normalised record (before classification):
  id, title, summary, year, kind, source, url   always
  authors, org, keywords, doc_type, doi, license, fulltext_url   when the source has them
"""

import html
import json
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import httpx

USER_AGENT = "blackfox-research-collector/1.0 (NASA Space Apps educational project)"
SUMMARY_MAX = 3000
RETRY_STATUS = {429, 500, 502, 503, 504}

Sink = Callable[[list[dict]], None]


class Http:
    """Shared client with retries and a per-host minimum delay (to stay polite)."""

    def __init__(self):
        self.client = httpx.Client(timeout=httpx.Timeout(180, connect=30), follow_redirects=True,
                                   headers={"User-Agent": USER_AGENT})
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def _wait(self, host: str, delay: float):
        if delay <= 0:
            return
        with self._lock:
            now = time.monotonic()
            at = max(now, self._last.get(host, 0) + delay)
            self._last[host] = at
        time.sleep(max(0.0, at - now))

    def request(self, method: str, url: str, delay: float = 0.0, tries: int = 6, **kw) -> httpx.Response:
        host = urllib.parse.urlsplit(url).netloc
        err: Exception | None = None
        for attempt in range(tries):
            self._wait(host, delay)
            try:
                r = self.client.request(method, url, **kw)
                if r.status_code not in RETRY_STATUS:
                    return r
                err = httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                wait = r.headers.get("retry-after", "")
                if wait.isdigit():       # the server says when to come back
                    time.sleep(min(180, int(wait) + 1))
                    continue
            except httpx.HTTPError as e:
                err = e
            time.sleep(min(60, 2 ** attempt * 1.5))
        raise err  # type: ignore[misc]

    def json(self, method: str, url: str, **kw):
        r = self.request(method, url, **kw)
        r.raise_for_status()
        return r.json()


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean(text, limit: int = 0) -> str:
    """Plain text: no HTML/XML tags, single spaces."""
    s = _WS.sub(" ", html.unescape(_TAG.sub(" ", str(text or "")))).strip()
    if limit and len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + " ..."
    return s


def _year(*values) -> int | None:
    for v in values:
        m = re.search(r"(1[89]\d\d|20\d\d)", str(v or ""))
        if m:
            return int(m.group(1))
    return None


def _uniq(items, limit: int) -> list[str]:
    out, seen = [], set()
    for x in items:
        x = clean(x)
        if x and x.lower() not in seen and len(x) <= 120:
            seen.add(x.lower())
            out.append(x)
    return out[:limit]


# ---- NASA Technical Reports Server ---------------------------------------------------
NTRS = "https://ntrs.nasa.gov"
NTRS_TERMS = ["microgravity", "weightlessness", "zero gravity", "reduced gravity", "partial gravity", "low gravity",
              "hypogravity", "drop tower", "parabolic flight", "space station", "lunar", "moon", "regolith",
              "mars", "martian",
              # wider nets; the classifier keeps only what is really about the Moon, Mars or 0 g
              "spaceflight", "astronaut", "apollo", "artemis", "skylab", "spacelab", "extravehicular", "free fall",
              "life support", "space habitat", "surface habitat", "in-situ resource utilization", "planetary surface",
              "crew health", "bed rest", "space medicine", "space manufacturing", "cislunar"]
NTRS_WINDOW = 9900     # the API refuses to page past 10000 results, so big queries are split by publication date


def _ntrs_record(r: dict) -> dict | None:
    summary = clean(r.get("abstract"), SUMMARY_MAX)
    title = clean(r.get("title"))
    if len(summary) < 100 or not title:
        return None
    pubs = r.get("publications") or [{}]
    rec = {"id": f"ntrs-{r['id']}", "title": title, "summary": summary,
           "year": _year(pubs[0].get("publicationDate"), r.get("distributionDate"), r.get("created")),
           "kind": "report", "source": "NASA Technical Reports Server", "url": f"{NTRS}/citations/{r['id']}",
           "doc_type": clean(r.get("stiTypeDetails") or r.get("stiType")),
           "authors": _uniq((((a.get("meta") or {}).get("author") or {}).get("name")
                             for a in r.get("authorAffiliations") or []), 8),
           "org": clean((r.get("center") or {}).get("name")),
           "keywords": _uniq((r.get("keywords") or []) + (r.get("subjectCategories") or []), 12)}
    if r.get("distribution") == "PUBLIC":
        for d in r.get("downloads") or []:
            ft = (d.get("links") or {}).get("fulltext")
            if ft:
                rec["fulltext_url"] = NTRS + ft
                break
    return rec


def _ntrs_windows(http: Http, term: str, gte: str | None = None, lte: str | None = None) -> list[tuple[str | None, str | None, int]]:
    body: dict = {"q": term, "page": {"size": 1, "from": 0}}
    if gte:
        body["published"] = {"gte": gte, "lte": lte}
    total = http.json("POST", f"{NTRS}/api/citations/search", json=body)["stats"]["total"]
    if total <= NTRS_WINDOW:
        return [(gte, lte, total)] if total else []
    lo, hi = int((gte or "1900-01-01")[:4]), int((lte or f"{time.gmtime().tm_year}-12-31")[:4])
    if lo == hi:     # one single year over the limit: split it into halves
        if gte and gte[5:] != "01-01" or lte and lte[5:] != "12-31":
            return [(gte, lte, NTRS_WINDOW)]
        return (_ntrs_windows(http, term, f"{lo}-01-01", f"{lo}-06-30")
                + _ntrs_windows(http, term, f"{lo}-07-01", f"{lo}-12-31"))
    mid = (lo + hi) // 2
    return (_ntrs_windows(http, term, f"{lo}-01-01", f"{mid}-12-31")
            + _ntrs_windows(http, term, f"{mid + 1}-01-01", f"{hi}-12-31"))


def harvest_ntrs(http: Http, sink: Sink, progress: dict, workers: int = 4):
    tasks = []
    for term in NTRS_TERMS:
        for gte, lte, total in _ntrs_windows(http, term):
            for start in range(0, min(total, 10000), 100):
                key = f"ntrs|{term}|{gte}|{lte}|{start}"
                if key not in progress:
                    tasks.append((key, term, gte, lte, start))

    def page(task):
        key, term, gte, lte, start = task
        body: dict = {"q": term, "page": {"size": 100, "from": start}}
        if gte:
            body["published"] = {"gte": gte, "lte": lte}
        results = http.json("POST", f"{NTRS}/api/citations/search", json=body).get("results") or []
        return key, [x for x in map(_ntrs_record, results) if x]

    with ThreadPoolExecutor(workers) as pool:
        for key, records in pool.map(page, tasks):
            sink(records)
            progress[key] = len(records)


# ---- Europe PMC (journal articles; includes PubMed) ----------------------------------
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EPMC_QUERIES = {
    "zero_g": '"microgravity" OR "weightlessness" OR "spaceflight" OR "space flight" OR "parabolic flight" OR "hypogravity" '
              'OR "partial gravity" OR "reduced gravity" OR "zero gravity" OR "international space station" '
              'OR "hindlimb unloading" OR "simulated microgravity"',
    "moon": '"lunar gravity" OR "lunar regolith" OR "lunar surface" OR "lunar dust" OR "lunar base" OR "lunar habitat" '
            'OR "moon base" OR "lunar exploration" OR "lunar soil" OR "lunar simulant" OR "lunar mission"',
    "mars": '"martian gravity" OR "mars gravity" OR "martian regolith" OR "martian surface" OR "mars mission" '
            'OR "mars exploration" OR "martian soil" OR "mars habitat" OR "martian atmosphere" OR "martian dust" '
            'OR "mars simulant" OR "human mission to mars"',
}


def _epmc_record(r: dict) -> dict | None:
    summary = clean(re.sub(r"</h4>", ": ", r.get("abstractText") or ""), SUMMARY_MAX)
    title = clean(r.get("title")).rstrip(".")
    if len(summary) < 100 or not title:
        return None
    pmcid, src, rid = r.get("pmcid"), r.get("source", "MED"), r.get("id")
    journal = ((r.get("journalInfo") or {}).get("journal") or {}).get("title") or (r.get("bookOrReportDetails") or {}).get("publisher")
    mesh = [m.get("descriptorName") for m in (r.get("meshHeadingList") or {}).get("meshHeading") or []]
    rec = {"id": f"pmc-{pmcid[3:]}" if pmcid else f"epmc-{src.lower()}-{rid}", "title": title, "summary": summary,
           "year": _year(r.get("pubYear"), r.get("firstPublicationDate")), "kind": "paper",
           "source": "Europe PMC", "url": f"https://europepmc.org/article/{src}/{rid}",
           "doc_type": "Preprint" if src == "PPR" else "Journal article",
           "authors": _uniq((r.get("authorString") or "").rstrip(".").split(", "), 8), "org": clean(journal),
           "keywords": _uniq(((r.get("keywordList") or {}).get("keyword") or []) + mesh, 12)}
    if r.get("doi"):
        rec["doi"] = r["doi"]
    if r.get("isOpenAccess") == "Y" and pmcid:
        rec["license"] = clean(r.get("license")) or "open access"
        rec["fulltext_url"] = f"{EPMC}/{pmcid}/fullTextXML"
    return rec


def harvest_epmc(http: Http, sink: Sink, progress: dict):
    for name, query in EPMC_QUERIES.items():
        key = f"epmc|{name}"
        cursor = progress.get(key, "*")
        while cursor != "done":
            d = http.json("GET", f"{EPMC}/search", delay=0.3, params={
                "query": f"({query})", "format": "json", "resultType": "core", "pageSize": 1000, "cursorMark": cursor})
            results = (d.get("resultList") or {}).get("result") or []
            sink([x for x in map(_epmc_record, results) if x])
            nxt = d.get("nextCursorMark")
            cursor = nxt if results and nxt and nxt != cursor else "done"
            progress[key] = cursor


# ---- arXiv (preprints; metadata is CC0) ----------------------------------------------
ARXIV = "https://export.arxiv.org/api/query"
ARXIV_QUERIES = {
    "zero_g": 'abs:microgravity OR abs:weightlessness OR abs:"reduced gravity" OR abs:"partial gravity" OR abs:"zero gravity" '
              'OR abs:"space station" OR abs:"parabolic flight" OR abs:"drop tower"',
    "moon": 'abs:lunar OR ti:moon OR abs:"lunar regolith" OR abs:"lunar surface"',
    "mars": 'abs:mars OR abs:martian',
}
_ATOM = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}


def harvest_arxiv(http: Http, sink: Sink, progress: dict):
    for name, query in ARXIV_QUERIES.items():
        key = f"arxiv|{name}"
        start = progress.get(key, 0)
        while start != "done":
            r = http.request("GET", ARXIV, delay=3.1, params={"search_query": query, "start": start, "max_results": 500,
                                                               "sortBy": "submittedDate", "sortOrder": "descending"})
            r.raise_for_status()
            entries = ET.fromstring(r.content).findall("a:entry", _ATOM)
            records = []
            for e in entries:
                link = (e.findtext("a:id", "", _ATOM) or "").strip()
                summary = clean(e.findtext("a:summary", "", _ATOM), SUMMARY_MAX)
                if not link or len(summary) < 100:
                    continue
                aid = re.sub(r"v\d+$", "", link.rsplit("/abs/", 1)[-1])
                records.append({"id": "arxiv-" + aid.replace("/", "-"), "title": clean(e.findtext("a:title", "", _ATOM)),
                                "summary": summary, "year": _year(e.findtext("a:published", "", _ATOM)), "kind": "paper",
                                "source": "arXiv", "url": f"https://arxiv.org/abs/{aid}", "doc_type": "Preprint",
                                "authors": _uniq((a.findtext("a:name", "", _ATOM) for a in e.findall("a:author", _ATOM)), 8),
                                "keywords": _uniq((c.get("term") for c in e.findall("a:category", _ATOM)), 6)})
            sink(records)
            start = start + 500 if len(entries) == 500 and start + 500 < 30000 else "done"
            progress[key] = start


# ---- NASA TechPort (technology projects) ---------------------------------------------
def harvest_techport(http: Http, sink: Sink, progress: dict):
    if "techport" in progress:
        return
    d = http.json("GET", "https://techport.nasa.gov/api/projects/search", params={"searchQuery": "gravity"})
    records = []
    for p in d.get("results") or []:
        summary = clean(p.get("description"), SUMMARY_MAX - 600)
        benefits = clean(p.get("benefits"), 600)
        if len(summary) < 100 or not p.get("projectId"):
            continue
        if benefits:
            summary += " Benefits: " + benefits
        trl = [p.get("trlBegin"), p.get("trlCurrent"), p.get("trlEnd")]
        rec = {"id": f"techport-{p['projectId']}", "title": clean(p.get("title")), "summary": summary,
               "year": _year(p.get("startDate"), p.get("endDate")), "kind": "project", "source": "NASA TechPort",
               "url": f"https://techport.nasa.gov/projects/{p['projectId']}",
               "doc_type": clean(f"Technology project ({p.get('status') or 'status unknown'})"),
               "org": clean((p.get("leadOrganization") or {}).get("organization_name")),
               "keywords": _uniq([(p.get("primaryTx") or {}).get("title"), (p.get("program") or {}).get("title")]
                                 + list(p.get("destinationTypes") or []), 10)}
        if all(str(t or "").isdigit() for t in trl):
            rec["trl"] = {"begin": int(trl[0]), "current": int(trl[1]), "end": int(trl[2])}
        records.append(rec)
    sink(records)
    progress["techport"] = len(records)


# ---- NASA Open Science Data Repository (space biology studies) -------------------------
def harvest_osdr(http: Http, sink: Sink, progress: dict):
    start = progress.get("osdr", 0)
    while start != "done":
        d = http.json("GET", "https://osdr.nasa.gov/osdr/data/search", delay=0.5,
                      params={"term": "", "type": "cgene", "from": start, "size": 100})
        hits = (d.get("hits") or {}).get("hits") or []
        records = []
        for h in hits:
            s = h.get("_source") or {}
            acc, summary = s.get("Accession") or s.get("Study Identifier"), clean(s.get("Study Description"), SUMMARY_MAX)
            if not acc or len(summary) < 100:
                continue
            release = s.get("Study Public Release Date")
            year = time.gmtime(float(release)).tm_year if str(release or "").replace(".", "").isdigit() else None
            mission = (s.get("Mission") or {}).get("Name") if isinstance(s.get("Mission"), dict) else ""
            kw = [s.get("organism"), s.get("Project Type"), s.get("Study Assay Measurement Type"), s.get("Material Type"),
                  mission, s.get("Flight Program")] + re.split(r"\s{2,}", str(s.get("Study Factor Name") or ""))
            records.append({"id": f"osdr-{acc.lower()}", "title": clean(s.get("Study Title")), "summary": summary, "year": year,
                            "kind": "dataset", "source": "NASA Open Science Data Repository",
                            "url": f"https://osdr.nasa.gov/bio/repo/data/studies/{acc}", "doc_type": "Space biology study",
                            "org": clean(s.get("Managing NASA Center")), "keywords": _uniq(kw, 12)})
        sink(records)
        start = start + 100 if len(hits) == 100 else "done"
        progress["osdr"] = start


# ---- Wikipedia (overview articles; text is CC BY-SA 4.0) -------------------------------
WIKI = "https://en.wikipedia.org/w/api.php"
WIKI_SEARCHES = [
    "microgravity", "weightlessness", "micro-g environment", "effect of spaceflight on the human body", "space medicine",
    "space manufacturing", "International Space Station research", "space station", "drop tower reduced gravity",
    "combustion in microgravity", "plants in space", "space habitat", "artificial gravity", "life support system spacecraft",
    "gravitation of the Moon", "lunar regolith", "lunar soil", "moonbase", "colonization of the Moon", "lunar habitat",
    "lunar resources", "lunar lander", "Artemis program", "Apollo program", "exploration of the Moon", "lunar dust",
    "geology of the Moon", "lunar water", "lunar rover", "gravity of Mars", "Martian regolith", "Martian soil",
    "colonization of Mars", "Mars habitat", "human mission to Mars", "exploration of Mars", "atmosphere of Mars",
    "Mars rover", "Mars landing", "in situ resource utilization", "climate of Mars", "geology of Mars", "water on Mars",
    "Mars analog habitat", "terraforming of Mars", "space radiation health threat", "space suit", "extravehicular activity",
]


def harvest_wikipedia(http: Http, sink: Sink, progress: dict):
    """One request returns the intro text of 20 matching articles, so the whole source is ~100 requests."""
    seen = set(progress.get("wiki|pages", []))
    for query in WIKI_SEARCHES:
        key = f"wiki|{query}"
        if key in progress:
            continue
        records = []
        for offset in (0, 20):
            d = http.json("GET", WIKI, delay=2.0, params={
                "action": "query", "generator": "search", "gsrsearch": query, "gsrlimit": 20, "gsroffset": offset,
                "prop": "extracts", "exintro": 1, "explaintext": 1, "exlimit": 20, "format": "json"})
            for page in ((d.get("query") or {}).get("pages") or {}).values():
                summary, pid, title = clean(page.get("extract"), SUMMARY_MAX), page.get("pageid"), page.get("title")
                if not pid or pid in seen or len(summary) < 200:
                    continue
                seen.add(pid)
                records.append({
                    "id": f"wiki-{pid}", "title": title, "summary": summary, "year": None, "kind": "article",
                    "source": "Wikipedia", "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                    "doc_type": "Encyclopedia article", "license": "CC BY-SA 4.0",
                    "fulltext_url": WIKI + "?" + urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1,
                                                                         "pageids": pid, "format": "json"})})
        sink(records)
        progress["wiki|pages"] = sorted(seen)
        progress[key] = len(records)


SOURCES: dict[str, Callable] = {"ntrs": harvest_ntrs, "epmc": harvest_epmc, "arxiv": harvest_arxiv,
                                "techport": harvest_techport, "osdr": harvest_osdr, "wikipedia": harvest_wikipedia}


class Progress(dict):
    """A dict that saves itself to disk, so a stopped harvest can continue."""

    def __init__(self, path):
        super().__init__()
        self.path, self._lock, self._n = path, threading.Lock(), 0
        if path.exists():
            self.update(json.loads(path.read_text(encoding="utf-8")))

    def __setitem__(self, key, value):
        with self._lock:
            super().__setitem__(key, value)
            self._n += 1
            if self._n % 20 == 0 or not str(key).startswith("ntrs|"):
                self._save()

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self), encoding="utf-8")
        tmp.replace(self.path)

    def save(self):
        with self._lock:
            self._save()
