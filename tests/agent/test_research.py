"""Research knowledge base: collector (classify, build, full text) and the JSON store the
agent's research tools read. Uses a tiny database built in a temp folder - no network."""

import json

import pytest

from blackfox.collect.build import build
from blackfox.collect.classify import classify
from blackfox.collect.fulltext import _Shards, to_text
from blackfox.db.json_store import INTAKE_DIRS, JsonResearchStore, read_knowledge_file
from blackfox.settings import get_settings

RAW = [
    {"id": "ntrs-1", "title": "Lunar dust mitigation for habitat airlocks", "year": 2021, "kind": "report",
     "summary": "Dust on the lunar surface sticks to suits. " * 4, "keywords": ["lunar dust"], "source": "NASA Technical Reports Server",
     "url": "https://ntrs.nasa.gov/citations/1", "fulltext_url": "https://ntrs.nasa.gov/api/citations/1/downloads/a.txt"},
    {"id": "ntrs-2", "title": "Flame spread over thin fuels in microgravity", "year": 1999, "kind": "report",
     "summary": "Drop tower experiments show how flames spread in microgravity. " * 3, "source": "NASA Technical Reports Server",
     "url": "https://ntrs.nasa.gov/citations/2"},
    {"id": "arxiv-2401.00001", "title": "Sintering Martian regolith into bricks", "year": 2024, "kind": "paper",
     "summary": "We sinter Martian regolith simulant for construction on Mars. " * 3, "source": "arXiv", "url": "https://arxiv.org/abs/2401.00001"},
    {"id": "ntrs-3", "title": "Lunar habitat structures: an older study", "year": 1990, "kind": "report",
     "summary": "An inflatable habitat for a lunar base is sized for internal pressure. " * 3, "source": "NASA Technical Reports Server",
     "url": "https://ntrs.nasa.gov/citations/3"},
    {"id": "ntrs-4", "title": "Lunar habitat structures: a newer study", "year": 2020, "kind": "report",
     "summary": "A regolith-covered habitat for a lunar base is sized for internal pressure. " * 3,
     "source": "NASA Technical Reports Server", "url": "https://ntrs.nasa.gov/citations/4"},
    {"id": "ntrs-4-dup", "title": "Lunar habitat structures: a newer study", "year": 2020, "kind": "report",
     "summary": "Short duplicate about a lunar base habitat. " * 3, "source": "NASA Technical Reports Server", "url": "https://x"},
    {"id": "ntrs-5", "title": "Tomato yields in Ohio greenhouses", "year": 2010, "kind": "report",
     "summary": "Nothing about space at all, only tomatoes grown on Earth. " * 3, "source": "NASA Technical Reports Server", "url": "https://y"},
]
CURATED = {"records": [{"id": "moon-gravity", "title": "Moon surface gravity", "kind": "concept", "gravity": ["moon"],
                        "topic": "gravity_field_geodesy", "summary": "Gravity on the lunar surface is 1.62 m/s^2.",
                        "facts": [{"name": "surface gravity", "value": 1.62, "unit": "m/s^2"}]}]}


@pytest.fixture()
def db(tmp_path):
    staging, root = tmp_path / "staging", tmp_path / "knowledge"
    staging.mkdir()
    (staging / "test.jsonl").write_text("\n".join(json.dumps(r) for r in RAW) + "\n", encoding="utf-8")
    stats = build(staging, root)
    (root / "curated").mkdir()
    (root / "curated" / "ref.json").write_text(json.dumps(CURATED, indent=2), encoding="utf-8")
    store = JsonResearchStore(root, tmp_path / "data", tmp_path / "fulltext", background=False)
    return store, root, stats, tmp_path


def test_classify_keeps_only_moon_mars_and_zero_g():
    assert classify("Lunar habitat design", [], "")[0] == ["moon"]
    assert classify("Mars ascent vehicle", [], "")[0] == ["mars"]
    assert classify("Boiling in microgravity", [], "")[:2] == (["zero_g"], "fluids_heat_transfer")
    assert set(classify("Partial gravity combustion", [], "")[0]) >= {"moon", "mars"}
    assert classify("Tides of an icy moon of Jupiter", [], "a moon far away")[0] == []
    assert classify("Tomato yields in Ohio", [], "mentions mars once")[0] == []


def test_build_writes_sorted_json_without_duplicates_or_off_topic_records(db):
    _, root, stats, _ = db
    assert stats["records"] == 5 and stats["duplicates"] == 1 and stats["not_about_moon_mars_0g"] == 1
    index = json.loads((root / "index.json").read_text())
    assert set(index["gravity"]) == {"moon", "mars", "zero_g"}
    assert sum(f["records"] for f in index["files"]) == index["totals"]["records"] == 5
    for f in index["files"]:
        data = json.loads((root / f["path"]).read_text())            # every file is ordinary JSON ...
        assert data["gravity"] == f["gravity"] and data["count"] == len(data["records"]) == f["records"]
        rows = read_knowledge_file(root / f["path"])                 # ... with one record per line
        assert [r for _, _, r in rows] == data["records"] and all(off > 0 for off, _, _ in rows)
        years = [r["year"] for r in data["records"]]
        assert years == sorted(years, reverse=True)
    habitats = json.loads((root / "moon" / "habitats_structures-001.json").read_text())["records"]
    assert [r["id"] for r in habitats] == ["ntrs-4", "ntrs-3"]         # newest first, the longer duplicate kept
    assert (root / "mars").is_dir() and "arxiv-2401-00001" in (root / index["gravity"]["mars"]["topics"].popitem()[1]["files"][0]).read_text()


def test_search_get_list_and_stats(db):
    store = db[0]
    hits = store.search("lunar dust airlock")
    assert hits[0]["slug"] == "ntrs-1" and hits[0]["gravity"] == ["moon"]
    assert [h["slug"] for h in store.search("regolith", gravity="mars")] == ["arxiv-2401-00001"]
    assert store.search("flame", gravity="moon") == []
    assert store.search("what is the surface gravity of the moon")[0]["slug"] == "moon-gravity"     # curated first
    rec = store.get("moon-gravity")
    assert rec["status"] == "curated" and rec["facts"][0]["value"] == 1.62 and rec["full_text"] is False
    assert store.get("ntrs-2")["url"].endswith("/2") and store.get("nope") is None
    assert [r["slug"] for r in store.list(gravity="moon", topic="habitats_structures")] == ["ntrs-4", "ntrs-3"]
    stats = store.stats()
    assert stats["records"] == 6 and stats["curated"] == 1 and stats["by_gravity"]["zero_g"]["records"] == 1


def test_index_is_rebuilt_when_the_json_changes(db):
    store, root, _, tmp = db
    assert store.search("basalt") == []
    CURATED2 = {"records": CURATED["records"] + [{"id": "mars-basalt", "title": "Basalt on Mars", "kind": "finding",
                                                   "gravity": ["mars"], "topic": "general", "summary": "Basalt fibre from Mars rock."}]}
    (root / "curated" / "ref.json").write_text(json.dumps(CURATED2), encoding="utf-8")
    again = JsonResearchStore(root, tmp / "data", background=False)
    assert again.search("basalt")[0]["slug"] == "mars-basalt"


def test_intake_folders_are_not_part_of_the_database(db):
    _, root, _, tmp = db
    (root / "raw_data").mkdir()
    (root / "raw_data" / "delete_later.txt").write_text("")
    (root / "raw_data" / "upload.json").write_text(json.dumps({"records": [
        {"id": "raw-1", "title": "Unprocessed lunar upload", "summary": "Not reviewed yet.", "gravity": ["moon"]}]}))
    store = JsonResearchStore(root, tmp / "data2", background=False)
    assert store.get("raw-1") is None and store.search("unprocessed upload") == []
    assert store.stats()["records"] == 6 and "unreadable_files" not in store.stats()


def test_community_records_live_in_their_own_json_file(db):
    store, _, _, tmp = db
    added = store.add({"title": "Seal wear from dust", "kind": "finding", "summary": "Lunar dust wore the seals in our test.",
                       "gravity": "moon", "tags": "dust, seals", "source": "user test report"})
    assert added["status"] == "community" and added["gravity"] == ["moon"]
    assert store.search("seal wear dust")[0]["slug"] == "seal-wear-from-dust"
    store.add_fact("moon-gravity", "relative to Earth", 0.165, "g", "")
    assert [f["name"] for f in store.get("moon-gravity")["facts"]] == ["surface gravity", "relative to Earth"]
    with pytest.raises(ValueError):
        store.add_fact("moon-gravity", "surface gravity", 9.9, "m/s^2", "")       # curated facts are protected
    with pytest.raises(ValueError):
        store.add({"title": "Moon gravity", "kind": "concept", "summary": "x", "gravity": "moon", "slug": "moon-gravity"})
    with pytest.raises(ValueError):
        store.add({"title": "Venus note", "kind": "concept", "summary": "x", "gravity": "venus"})
    saved = json.loads((tmp / "data" / "community.json").read_text())
    assert saved["records"][0]["slug"] == "seal-wear-from-dust" and "moon-gravity" in saved["facts"]
    reopened = JsonResearchStore(db[1], tmp / "data", background=False)
    assert reopened.get("seal-wear-from-dust")["title"] == "Seal wear from dust"


def test_community_records_of_the_old_sqlite_database_are_kept(db, tmp_path):
    import sqlite3
    data = tmp_path / "olddata"
    data.mkdir()
    c = sqlite3.connect(data / "research.db")
    c.executescript("""
        CREATE TABLE records (id INTEGER PRIMARY KEY, slug TEXT, title TEXT, kind TEXT, summary TEXT, details TEXT,
            platform TEXT, agency TEXT, years TEXT, tags TEXT, sources TEXT, status TEXT, created_by TEXT, created_at REAL, updated_at REAL);
        CREATE TABLE facts (id INTEGER PRIMARY KEY, record_id INTEGER, name TEXT, value REAL, unit TEXT, note TEXT,
            status TEXT, created_by TEXT, created_at REAL);
        INSERT INTO records VALUES (1, 'seeded', 'Seeded', 'concept', 's', '', '', '', '', '', '[]', 'curated', 'seed', 1, 1);
        INSERT INTO records VALUES (2, 'user-note', 'User note', 'finding', 'Flames went out.', 'd', '', '', '', 'fire, test',
            '[{"title": "lab book"}]', 'community', 'ai', 1, 1);
        INSERT INTO facts VALUES (1, 2, 'burn time', 4.2, 's', '', 'community', 'ai', 1);
    """)
    c.commit()
    c.close()
    store = JsonResearchStore(db[1], data, background=False)
    rec = store.get("user-note")
    assert rec["status"] == "community" and rec["source"] == "lab book" and rec["facts"][0]["value"] == 4.2
    assert store.get("seeded") is None and (data / "community.json").exists()


def test_full_text_is_stored_as_json_and_read_in_pages(db):
    store, root, _, tmp = db
    html = b"<html><head><meta name='x' content='y'><title>t</title></head><body><p>First paragraph.</p><p>Second &amp; last.</p></body></html>"
    assert to_text("https://ntrs.nasa.gov/a.txt", html) == "First paragraph.\nSecond & last."
    shards = _Shards(tmp / "fulltext")
    text = "Lunar dust is abrasive. " * 400 + "The airlock seal failed after 200 cycles. " + "More text. " * 300
    shards.add("moon", {"id": "ntrs-1", "title": "Lunar dust mitigation", "url": "u", "chars": len(text), "text": text})
    shards.add("moon", {"id": "ntrs-4", "title": "Other", "url": "u", "chars": 5, "text": "hello"})
    shards.flush()
    shard = tmp / "fulltext" / "moon" / "text-0001.json"
    assert [r["id"] for r in json.loads(shard.read_text())["records"]] == ["ntrs-1", "ntrs-4"]      # valid JSON
    assert _Shards(tmp / "fulltext").known() == {"ntrs-1", "ntrs-4"}                              # resumable
    store = JsonResearchStore(root, tmp / "data", tmp / "fulltext", background=False)
    assert store.get("ntrs-1")["full_text"] is True
    page = store.read_text("ntrs-1", page=2)
    assert page["pages"] >= 3 and page["page"] == 2 and len(page["text"]) == 4500
    found = store.read_text("ntrs-1", find="airlock seal")
    assert "failed after 200 cycles" in found["matches"][0]["text"]
    assert "error" in store.read_text("ntrs-2")


def test_research_tools_use_the_store(db, monkeypatch):
    import blackfox.db as dbmod
    from blackfox.tools import research
    monkeypatch.setattr(dbmod, "_store", db[0])
    out = research.search_research("lunar dust", gravity="moon")
    assert out["count"] >= 1 and out["results"][0]["slug"] == "ntrs-1"
    assert "error" in research.search_research("dust", gravity="venus")
    assert research.get_research("ntrs-1")["title"].startswith("Lunar dust")
    assert research.list_research(gravity="zero_g")["records"][0]["slug"] == "ntrs-2"
    assert research.research_stats()["records"] == 6
    assert research.add_research("Note", "finding", "A lunar note.", "moon")["status"] == "community"
    assert "error" in research.add_research("Note", "finding", "x", "pluto")


def test_shipped_database_is_text_only_json_and_matches_its_index():
    root = get_settings().knowledge_dir
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    assert set(index["gravity"]) <= {"moon", "mars", "zero_g"} and index["totals"]["records"] > 1000
    # pdf-s/ (source documents) and raw_data/ (unprocessed uploads) are intake folders, not the database
    records = [p for p in root.rglob("*") if p.is_file() and p.relative_to(root).parts[0] not in INTAKE_DIRS]
    on_disk = {str(p.relative_to(root)) for p in records if p.suffix == ".json"} - {"index.json"}
    assert {f["path"] for f in index["files"]} == {p for p in on_disk if not p.startswith("curated")}
    # no pictures, no binaries. Other text files (placeholders, a page a teammate uploads on GitHub)
    # are allowed: the store reads only *.json, so they never become records.
    pictures = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg", ".ico", ".heic", ".pdf"}
    others = [p for p in records if p.suffix != ".json"]
    assert not [p.name for p in others if p.suffix.lower() in pictures]
    for p in others:
        p.read_bytes().decode("utf-8")          # raises on binary content
    assert all(p.suffix in {".pdf", ".md"} for p in (root / "pdf-s").rglob("*") if p.is_file())
    for f in index["files"]:
        path = root / f["path"]
        assert path.stat().st_size == f["bytes"] <= 50_000_000                       # GitHub-friendly files
        with open(path, "rb") as fh:
            header = fh.readline()
            first = json.loads(fh.readline().strip().rstrip(b","))
        assert header.rstrip().endswith(b'"records": [') and f["gravity"] in first["gravity"] and first["topic"] == f["topic"]
    smallest = min(index["files"], key=lambda f: f["bytes"])
    data = json.loads((root / smallest["path"]).read_text(encoding="utf-8"))
    assert data["count"] == len(data["records"]) == smallest["records"]
    for p in (root / "curated").glob("*.json"):
        for r in json.loads(p.read_text(encoding="utf-8"))["records"]:
            assert r["id"] and r["summary"] and set(r["gravity"]) <= {"moon", "mars", "zero_g"}
