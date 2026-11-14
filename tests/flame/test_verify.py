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


# ---- material limits (flame/data/material_limits.json) ------------------------------------------
import re
from pathlib import Path

import pytest

OLSON_PDF = (Path(__file__).resolve().parents[2] / "blackfox" / "db" / "knowledge" / "pdf-s"
             / "P0_Flammability_0g_vs_Martian_g_vs_NASA_std_2012.pdf")


def _limit(material_id, gravity):
    return next(m for m in data.get_material_limits(material_id) if m.gravity == gravity)


def test_committed_material_limits_pass_the_source_check_unchanged():
    limits = data.get_material_limits()
    checked, problems = verify.check_material_limits(limits)
    assert problems == []
    assert [m.model_dump(by_alias=True) for m in checked] == [m.model_dump(by_alias=True) for m in limits]


def test_every_material_limit_is_verified_or_states_why_not():
    for m in data.get_material_limits():
        assert m.verified != bool(m.unchecked_reason), f"{m.material_id}/{m.gravity}: flag and reason disagree"
    olson = [m for m in data.get_material_limits() if m.material_id != "pmma"]
    assert len(olson) == 12 and all(m.verified for m in olson)           # Table I numbers are in their quotes
    pmma = _limit("pmma", "lunar")
    assert not pmma.verified and "normal pressure" in pmma.unchecked_reason   # the paper gives no number


def test_a_wrong_number_fails_the_check():
    bad = _limit("mylar_g", "earth").model_copy(update={"uloi_pct": 22.0})
    out, problems = verify.check_material_limits([bad])
    assert problems and "uloiPct" in problems[0] and not out[0].verified and out[0].unchecked_reason


def test_a_number_with_no_quote_is_not_verified():
    bare = _limit("mylar_g", "earth").model_copy(update={"provenance": []})
    out, _ = verify.check_material_limits([bare])
    assert not out[0].verified and "no quote" in out[0].unchecked_reason


def test_pressure_must_match_the_psia_in_the_quote():
    bad = _limit("mylar_g", "earth").model_copy(update={"pressure_kpa": 101.3})     # the quote says 10.2 psia
    out, problems = verify.check_material_limits([bad])
    assert problems and "pressureKPa" in problems[0] and not out[0].verified


def test_a_quote_for_another_gravity_does_not_verify_a_row():
    wrong = _limit("mylar_g", "earth").model_copy(update={"gravity": "lunar", "gravity_g": 0.166})
    out, problems = verify.check_material_limits([wrong])
    assert problems and not out[0].verified


def test_the_zero_g_flow_is_checked_against_a_quote():
    m = _limit("nomex_ht90_40", "micro")
    assert m.flow_mps == 0.3 and any("30 cm/s" in p.quote for p in m.provenance)
    bad = m.model_copy(update={"flow_mps": 0.5})
    out, problems = verify.check_material_limits([bad])
    assert problems and "flowMps" in problems[0] and not out[0].verified


@pytest.mark.skipif(not OLSON_PDF.is_file(), reason="source PDF not in this checkout")
def test_table_i_in_the_paper_matches_the_data():
    """Independent of the quotes: read Table I from the PDF itself."""
    from pypdf import PdfReader
    text = " ".join(p.extract_text() or "" for p in PdfReader(OLSON_PDF).pages)
    text = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", text)
    rows = {("earth", "uloi_pct"): r"1g ULOI", ("earth", "moc_pct"): r"1g MOC",
            ("martian", "uloi_pct"): r"Martian\s+ULOI\s*\*", ("martian", "moc_pct"): r"Martian\s+MOC\s*\*",
            ("lunar", "uloi_pct"): r"Lunar\s+ULOI\s*\*", ("lunar", "moc_pct"): r"Lunar\s+MOC\s*\*",
            ("micro", "uloi_pct"): r"0g\*\s+ULOI\s*\*", ("micro", "moc_pct"): r"0g\*\s+MOC\s*\*"}
    for (gravity, field), label in rows.items():
        hit = re.search(label + r"\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)", text)
        assert hit, f"Table I row {label} not found in the PDF"
        for material, value in zip(("mylar_g", "ultem_1000", "nomex_ht90_40"), hit.groups()):
            assert getattr(_limit(material, gravity), field) == float(value), (material, gravity, field)
