"""The README's dashboard paragraph quotes numbers (how many investigations, how many have measurements, how
many raw rows, how many envelopes the gap map can place). They are computed here from the live endpoints, so
the README cannot drift from the data again: change the data and this test tells you which sentence to fix."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from flame import data

README = Path(__file__).resolve().parents[2] / "README.md"


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def readme_section() -> str:
    text = README.read_text(encoding="utf-8")
    start = text.index("## Fire safety research dashboards")
    return " ".join(text[start:text.index("\n## ", start + 5)].split())     # one line per paragraph run


def test_readme_dashboard_numbers_match_the_endpoints(client):
    dash = client.get("/api/research/dashboard", params={"scenario": "lunar_base"}).json()
    inv = dash["investigations"]
    n = len(inv)
    measured = sum(1 for i in inv if i["measurements_available"])
    both = sum(1 for i in inv if i["oxygen_percent"] and i["pressure_kpa"])
    with_o2 = sum(1 for i in inv if i["oxygen_percent"])
    rows = data.get_psi_tests()
    with_rows = len({r.accession for r in rows})
    gap = client.get("/api/flame/gapmap").json()
    placed, unplaced = len(gap["rectangles"]), len(gap["unplaced"])
    text = readme_section()

    expected = [
        f"ranks the {n} NASA PSI combustion investigations",
        f"(method `{dash['method']}`)",
        f"for the {measured} investigations that have measurement envelopes",
        f"({both} give both an oxygen and a pressure range, {with_o2} an oxygen range;",
        f"The other {n - measured} are computational studies",
        f"{with_rows} of the {n} also have raw PSI test tables ({len(rows):,} cleaned rows)",
        f"plots the {placed} of {placed + unplaced} envelopes that give both numbers",
        f"lists the {unplaced} it cannot place",
    ]
    missing = [e for e in expected if e not in text]
    assert not missing, f"the README dashboard section no longer matches the data; fix: {missing}"
    assert n == 24 and dash["total"] == n                                         # the claim in every title and sentence


def test_readme_says_the_honest_things_and_has_no_stale_claims():
    text = readme_section()
    for stale in ("does not contain PSI measurements", "curated NASA challenge metadata", "compare two to four experiment families"):
        assert stale not in text, stale
    for kept in ("not a prediction of fire risk", "does not replace NASA-STD-6001 material testing",
                 "aerospace engineers and researchers", "professors and students", "never hidden"):
        assert kept in text, kept
    # the dashboard plan it links to exists and is no longer described as future work
    assert Path(README).parent.joinpath("docs", "DASHBOARD_PLAN.md").is_file() and "docs/DASHBOARD_PLAN.md" in text


def test_the_audience_sentence_is_on_the_investigations_tab():
    root = README.parent
    i18n = (root / "frontend" / "js" / "i18n.js").read_text(encoding="utf-8")
    keys = re.findall(r"dash_intro: '((?:[^'\\]|\\.)*)'", i18n)
    assert len(keys) == 1, "dash_intro must exist once"
    en = keys[0].replace("\\'", "'")                                           # JS escape -> plain text
    assert "aerospace engineers and researchers" in en and "not predictions of fire risk" in en   # the existing caveat stays
    index = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    assert en in index                                                              # the page's fallback text matches
    assert "does not replace NASA-STD-6001" in i18n                                 # the disclaimer is kept
