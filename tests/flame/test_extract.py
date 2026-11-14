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


# ---- the LLM call and the command (the model is faked; nothing goes over the network) ----

import asyncio
import json
import shutil
from types import SimpleNamespace

import pytest

from blackfox.llm import LLMError

ANSWER = {"summary": "FLEX burned droplets.", "envelopes": [RAW]}


class FakeLLM:
    def __init__(self, fail_on=()):
        self.fail_on, self.asked = fail_on, []

    async def chat(self, messages, tools=None, max_tokens=1500):
        self.asked.append(messages[1]["content"])
        if any(f"[{acc} " in messages[1]["content"] for acc in self.fail_on):
            raise LLMError("HTTP 429")
        # models like to wrap JSON in chatter; only the outermost {...} counts
        return SimpleNamespace(message={"content": f"Here you go:\n```json\n{json.dumps(ANSWER)}\n```"})


def test_parse_json_takes_the_outermost_object():
    assert extract.parse_json('noise {"a": {"b": 1}} trailing') == {"a": {"b": 1}}
    with pytest.raises(ValueError):
        extract.parse_json("I could not find any numbers.")


def test_extract_one_checks_the_answer_against_what_it_sent():
    llm = FakeLLM()
    summary, rows = asyncio.run(extract.extract_one(data.get_investigation("PSI-69"), [], llm))
    assert summary == "FLEX burned droplets." and "[PSI-69 Approach]" in llm.asked[0]
    # the pressure quote is in PSI's own text; the oxygen quote came from an abstract that was not sent
    assert rows[0].pressure_kpa == (50.7, 152.0) and rows[0].o2_pct is None


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    shutil.copytree(data.DATA, tmp_path / "data")
    monkeypatch.setattr(data, "DATA", tmp_path / "data")
    monkeypatch.setattr(extract, "PAPERS", tmp_path / "no-papers.json")
    (tmp_path / "data" / "envelopes.json").write_text(json.dumps([row("checked by hand", True, "PSI-25").model_dump(by_alias=True)]))
    data._load.cache_clear()
    yield tmp_path / "data"
    data._load.cache_clear()


def test_main_writes_rows_fills_summaries_and_survives_failures(workdir):
    llm = FakeLLM(fail_on=("PSI-68",))
    assert extract.main(only=["PSI-25", "PSI-68", "PSI-69"], llm=llm, pause=0) == 0
    rows = json.loads((workdir / "envelopes.json").read_text())
    assert [(r["accession"], r["verified"]) for r in rows] == [("PSI-25", True), ("PSI-69", False)]
    assert len(llm.asked) == 2                                     # PSI-25 is verified, so it is not asked again
    summaries = {r["accession"]: r["summary"] for r in json.loads((workdir / "investigations.json").read_text())}
    assert summaries["PSI-69"] == "FLEX burned droplets." and summaries["PSI-68"] == ""


def test_main_leaves_the_files_alone_when_every_call_fails(workdir):
    before = (workdir / "envelopes.json").read_bytes()
    assert extract.main(only=["PSI-68"], llm=FakeLLM(fail_on=("PSI-68",)), pause=0) == 1
    assert (workdir / "envelopes.json").read_bytes() == before
