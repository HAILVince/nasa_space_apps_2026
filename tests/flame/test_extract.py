"""Envelope extraction: what the LLM returns is only kept when the source text backs it."""

from flame import data
from flame.ingest import extract
from flame.models import Envelope

CONTEXT = ("[PSI-69 Approach] Select the test pressure (0.5 − 1.5 atm) for the LOI tests.\n"
           "[NTRS 20130014061] Ambient oxygen was varied from 13 to 40 percent by volume in nitrogen.")
RAW = {
    "label": "Droplets in O2/N2", "fuel": "methanol", "geometry": "droplet, 3 mm", "o2Pct": [13, 40],
    "pressureKPa": [50.7, 152.0], "flowMps": None, "gravity": "micro", "diluent": "N2",
    "measured": ["extinction diameter"], "sensors": ["video"], "keyFinding": "k", "verified": True,
    "provenance": [
        {"field": "o2Pct", "source": "NTRS 20130014061", "quote": "varied from 13 to 40 percent by volume"},
        {"field": "pressureKPa", "source": "PSI-69 Approach", "quote": "test pressure (0.5 - 1.5 atm)"},
    ],
}


def envelopes(*rows, summary="s"):
    return extract.validate_extraction({"summary": summary, "envelopes": list(rows)}, CONTEXT, "PSI-69")


def test_real_quotes_keep_their_ranges():
    summary, (env,) = envelopes({**RAW, "accession": "PSI-999"})
    assert summary == "s" and env.o2_pct == (13, 40) and env.pressure_kpa == (50.7, 152.0)
    assert env.accession == "PSI-69" and env.verified is False       # never trusted from the model
    assert [p.source for p in env.provenance] == ["NTRS 20130014061", "PSI-69 Approach"]


def test_fake_quote_drops_its_range():
    fake = {"field": "o2Pct", "source": "NTRS 20130014061", "quote": "oxygen ranged from 21 to 40 percent"}
    _, (env,) = envelopes({**RAW, "provenance": [fake, RAW["provenance"][1]]})
    assert env.o2_pct is None and env.pressure_kpa == (50.7, 152.0) and len(env.provenance) == 1


def test_a_quote_only_backs_the_field_it_names():
    _, (env,) = envelopes({**RAW, "flowMps": [0, 0.4]})              # nothing in the text is about flow
    assert env.flow_mps is None
    _, (env,) = envelopes({**RAW, "provenance": [{"field": "o2Pct", "source": "x", "quote": "13"}]})
    assert env.o2_pct is None                                        # a bare number matches anywhere


def test_malformed_rows_are_dropped_not_fatal():
    summary, rows = envelopes({"label": "no fuel given"}, {**RAW, "gravity": "lunar"}, "not a dict", RAW)
    assert len(rows) == 1 and summary == "s"
    assert extract.validate_extraction({}, CONTEXT, "PSI-69") == ("", [])


def row(label, verified, accession="PSI-69", finding="k"):
    return Envelope.model_validate({**RAW, "accession": accession, "label": label, "verified": verified,
                                    "keyFinding": finding, "provenance": []})


def test_merge_keeps_verified_rows():
    checked = row("Droplets in O2/N2", True, finding="checked by hand")
    assert extract.merge([checked], [row("Droplets in O2/N2", False)]) == [checked]


def test_merge_replaces_unverified_rows_of_the_same_investigation_only():
    old, other = row("old guess", False), row("BASS-II rods", False, accession="PSI-25")
    merged = extract.merge([old, other], [row("new guess", False)])
    assert [e.label for e in merged] == ["BASS-II rods", "new guess"]


def test_context_stays_inside_the_budget():
    inv = data.get_investigation("PSI-69")
    papers = [{"ntrsId": str(n), "abstract": "word " * 800} for n in range(3)]
    ctx = extract.build_context(inv, papers)
    assert len(ctx) <= 3500 * 4 and "[PSI-69 Approach]" in ctx and "[NTRS 0]" in ctx
    assert len(extract.build_context(inv, papers, max_tokens=500)) <= 500 * 4
