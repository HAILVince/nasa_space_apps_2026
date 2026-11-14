"""Matching PSI publication titles to NTRS abstracts. Offline: NTRS is faked."""

from types import SimpleNamespace

from flame.ingest import papers

TITLE = "Methanol Droplet Combustion in Oxygen-Inert Environments in Microgravity"
ABSTRACT = "Methanol droplets were burned aboard the International Space Station in oxygen-inert mixtures. " * 3


class FakeNtrs:
    """Answers every search with the same results and remembers the queries."""

    def __init__(self, *results):
        self.results, self.queries = list(results), []

    def json(self, method, url, **kw):
        self.queries.append(kw["json"]["q"])
        return {"results": self.results}


def test_similarity():
    assert papers.title_similarity(TITLE, TITLE) == 1.0
    assert papers.title_similarity(TITLE, TITLE.upper().replace("-", " ") + ".") == 1.0
    assert papers.title_similarity(TITLE, "Lunar regolith excavation with a bucket drum") < 0.2
    assert papers.title_similarity("", TITLE) == 0.0


def test_strong_match_is_returned_with_its_abstract():
    hit = papers.search_ntrs(TITLE, FakeNtrs({"id": 20130014061, "title": TITLE, "abstract": ABSTRACT}))
    assert hit["ntrsId"] == "20130014061" and hit["url"].endswith("/citations/20130014061")
    assert hit["abstract"].startswith("Methanol droplets") and hit["title"] == TITLE


def test_weak_match_is_rejected():
    # same topic, different paper: similarity is about 0.3, under the 0.6 bar
    other = {"id": 1, "title": "Microgravity Flammability of PMMA Rods in Concurrent Flow", "abstract": ABSTRACT}
    asked = "Microgravity flammability boundary for PMMA rods in axial stagnation flow: Experimental results"
    assert 0.2 < papers.title_similarity(asked, other["title"]) < papers.THRESHOLD
    assert papers.search_ntrs(asked, FakeNtrs(other)) is None
    assert papers.search_ntrs(asked, FakeNtrs()) is None


def test_match_without_an_abstract_is_useless():
    assert papers.search_ntrs(TITLE, FakeNtrs({"id": 2, "title": TITLE, "abstract": ""})) is None


def test_query_drops_the_subtitle():
    ntrs = FakeNtrs()
    papers.search_ntrs("Opposed-flow flame spread: A comparison of microgravity and normal gravity", ntrs)
    assert ntrs.queries == ["Opposed-flow flame spread"]


class NumberedNtrs(FakeNtrs):
    """Every search finds a different record, as if each title were its own paper."""

    def json(self, method, url, **kw):
        self.queries.append(kw["json"]["q"])
        return {"results": [{"id": len(self.queries), "title": TITLE, "abstract": ABSTRACT}]}


def test_collect_stops_at_three_abstracts_per_investigation():
    pubs = [SimpleNamespace(title=TITLE) for _ in range(8)]
    invs = [SimpleNamespace(accession="PSI-69", publications=pubs), SimpleNamespace(accession="PSI-68", publications=pubs[:1])]
    ntrs = NumberedNtrs()
    rows = papers.collect(invs, ntrs)
    assert [r["accession"] for r in rows] == ["PSI-69"] * 3 + ["PSI-68"] and len(ntrs.queries) == 4
    assert set(rows[0]) == {"accession", "pubTitle", "ntrsId", "abstract", "url"}


def test_collect_keeps_one_row_when_two_titles_find_the_same_record():
    inv = SimpleNamespace(accession="PSI-21", publications=[SimpleNamespace(title=TITLE)] * 2)
    assert len(papers.collect([inv], FakeNtrs({"id": 7, "title": TITLE, "abstract": ABSTRACT}))) == 1
