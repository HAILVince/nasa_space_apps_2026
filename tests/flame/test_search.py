"""Keyword search over the 24 investigations (runs on the committed dataset)."""

from flame import data
from flame.search import search_investigations


def accessions(*args, **kw):
    return [hit.accession for hit in search_investigations(*args, **kw)]


def test_acronym_beats_everything_else():
    assert accessions("BASS-II")[0] == "PSI-25"
    assert accessions("bass")[0] == "PSI-26"            # the exact acronym, not BASS-II or the BASS model study
    assert accessions("FLEX")[0] == "PSI-69"
    assert accessions("PSI-102") == ["PSI-102"] or accessions("PSI-102")[0] == "PSI-102"


def test_words_from_title_and_text():
    assert accessions("flame extinguishment droplet")[0] in ("PSI-69", "PSI-68")
    assert "PSI-22" in accessions("electric field")
    hits = search_investigations("smoke", kind="flight")
    assert {"PSI-101", "PSI-102"} & {h.accession for h in hits}
    assert all(data.get_investigation(h.accession).kind == "flight" for h in hits)


def test_prefix_counts_but_less_than_the_whole_word():
    assert accessions("extinguish")[0] in ("PSI-69", "PSI-68")        # matches "Extinguishment"
    whole, prefix = search_investigations("saffire")[0], search_investigations("saff")[0]
    assert whole.accession.startswith("PSI-") and whole.score > prefix.score > 0


def test_filters():
    solids = search_investigations("", fuel_phase="solid", k=None)
    assert solids and all(data.get_investigation(h.accession).fuel_phase == "solid" for h in solids)
    assert accessions("", topic="detection", kind="ground", k=None) == ["PSI-115"]
    assert set(accessions("", hardware="mdca", k=None)) == {"PSI-39", "PSI-68", "PSI-69"}


def test_empty_query_lists_everything_in_accession_order():
    everything = accessions("", k=None)
    assert len(everything) == 24 and everything[:3] == ["PSI-10", "PSI-20", "PSI-21"]
    assert len(accessions("")) == 5                       # default page size


def test_no_match_and_noise_words():
    assert accessions("xylophone") == []
    assert accessions("the of and") == []                 # words that are in every record say nothing
    hit = search_investigations("cool flames")[0]
    assert hit.acronym and hit.title and hit.summary and hit.score > 0
