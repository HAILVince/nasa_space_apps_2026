"""flame/data/finance.json: the sourced cost figures for the business case."""

import pytest

from flame import data


def test_finance_items_are_unique_and_sourced():
    items = data.get_finance()
    assert len({f.id for f in items}) == len(items) >= 20
    for f in items:
        assert f.url.startswith("https://") and f.quote.strip(), f.id
        assert f.source_level == "primary" or f.note or "SpaceNews" in f.source, f.id   # secondary sources say so


def test_key_figures_match_their_sources():
    by = {f.id: f for f in data.get_finance()}
    assert by["iss_crew_time_price"].value == 130_000 and by["iss_crew_time_price"].unit == "USD/h"
    assert by["iss_upmass_price"].value == 20_000 and by["iss_downmass_price"].value == 40_000
    assert by["iss_cost_per_year"].value == 3e9
    assert by["cargo_cost_per_kg_crs1"].value == 63_200 and by["cargo_cost_per_kg_crs1"].kind == "cost_estimate"


def test_derived_items_follow_their_formula():
    by = {f.id: f for f in data.get_finance()}
    for f in by.values():
        if f.kind == "derived":
            env = {k: by[k].value for k in f.derived_from}
            assert f.value == pytest.approx(eval(f.formula, {}, env), rel=1e-6), f.id   # formulas are plain arithmetic


def test_group_filter():
    assert {f.group for f in data.get_finance("artemis")} == {"artemis"}


def test_fire_events_are_sourced_and_durations_match_quotes():
    ev = {e.id: e for e in data.get_fire_events()}
    assert ev["mir-1997-candle-fire"].masks_h == 2.5 and ev["iss-2006-elektron"].emergency_h == 2
    for e in ev.values():
        assert e.sources and all(s.quote.strip() for s in e.sources), e.id
