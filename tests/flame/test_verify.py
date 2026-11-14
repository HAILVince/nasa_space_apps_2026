"""Every test envelope shown in the lab is checked against the PSI tables or a quoted NASA source."""
from flame import data
from flame.ingest import verify
from flame.ingest.clean_tables import summarise


def test_committed_envelopes_pass_the_source_check_unchanged():
    envelopes = data.get_envelopes()
    checked, problems = verify.check(envelopes, summarise(data._load("psi_tests")))
    assert problems == []
    assert [e.model_dump(by_alias=True) for e in checked] == [e.model_dump(by_alias=True) for e in envelopes]
    assert all(e.verified for e in envelopes)


def test_every_value_has_a_source_and_every_gap_a_reason():
    for e in data.get_envelopes():
        sources = {p.source for p in e.provenance}
        for alias in ("o2Pct", "pressureKPa", "flowMps"):
            value = e.model_dump(by_alias=True)[alias]
            if value is None:
                assert e.not_reported.get(alias), f"{e.accession} {alias}: empty without a reason"
            else:
                assert alias not in e.not_reported
        assert verify.CHECK_TAG in sources or all(v is None for v in (e.o2_pct, e.pressure_kpa, e.flow_mps))
        assert "assumption" not in sources                     # assumptions were replaced by sources or gaps


def test_a_table_mismatch_is_reported_not_written():
    e = next(x for x in data.get_envelopes() if x.accession == "PSI-69")
    bad = e.model_copy(update={"o2_pct": (10.0, 34.0)})
    out, problems = verify.check([bad], summarise(data._load("psi_tests")))
    assert problems and not out[0].verified
