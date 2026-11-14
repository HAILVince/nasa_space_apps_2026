"""Research database tools (read + write) over blackfox.db.get_store().

The database is a folder of JSON files (blackfox/db/knowledge): text records about three
gravity environments - moon, mars, zero_g - each filed under one topic."""

from ..db import GRAVITIES, KINDS, get_store
from .registry import tool


def _gravity(value: str) -> tuple[str | None, dict | None]:
    g = (value or "").strip().lower().replace("0g", "zero_g").replace("zero-g", "zero_g").replace("microgravity", "zero_g")
    if g and g not in GRAVITIES:
        return None, {"error": f"gravity must be one of {', '.join(GRAVITIES)} (or empty for all)"}
    return g or None, None


@tool("research")
def search_research(query: str, gravity: str = "", topic: str = "", kind: str = "", limit: int = 6) -> dict:
    """Search the research database: NASA reports, journal papers, technology projects and
    space-biology studies about the Moon (lunar gravity), Mars (Martian gravity) and 0 g
    (microgravity / weightlessness). Use it for any engineering or science question about
    those environments: habitats, regolith and dust, life support, fire, fluids, human
    health, power, landing, radiation...
    query: a few specific words, e.g. "lunar dust airlock mitigation".
    gravity optionally filters: moon, mars or zero_g. topic optionally filters (names from
    research_stats, e.g. habitats_structures, combustion_fire). kind: report, paper, project,
    dataset, article, experiment, facility, finding, concept, incident.
    Returns short summaries; call get_research(slug) for the full record."""
    g, err = _gravity(gravity)
    if err:
        return err
    results = get_store().search(query, kind=kind or None, limit=limit, gravity=g, topic=topic or None)
    if results and results[0].get("error"):
        return results[0]
    return {"count": len(results), "results": results}


@tool("research")
def get_research(slug: str) -> dict:
    """Full record by slug: complete summary, keywords, authors, year, source url, numeric
    facts (with units) and whether its full text is stored (then use read_research_text)."""
    rec = get_store().get(slug)
    if not rec:
        return {"error": f"no record '{slug}' - use search_research to find slugs"}
    return rec


@tool("research")
def read_research_text(slug: str, page: int = 1, find: str = "") -> dict:
    """Read the stored full text of a record, one page (about 4500 characters) at a time.
    Give find="some words" to jump to the passages that contain them instead of paging.
    Only records whose get_research says full_text: true have one."""
    return get_store().read_text(slug, page=page, find=find)


@tool("research")
def list_research(gravity: str = "", topic: str = "", kind: str = "", limit: int = 30) -> dict:
    """Browse records newest first, filtered by gravity (moon, mars, zero_g), topic and/or kind.
    Curated (hand-checked) records come first."""
    g, err = _gravity(gravity)
    if err:
        return err
    rows = get_store().list(kind=kind or None, gravity=g, topic=topic or None, limit=limit)
    if rows and rows[0].get("error"):
        return rows[0]
    return {"count": len(rows), "records": rows}


@tool("research")
def research_stats() -> dict:
    """What the research database holds: number of records per gravity environment and per
    topic inside each, per kind and per source. Use it to pick a topic filter."""
    return get_store().stats()


@tool("research", writes=True)
def add_research(title: str, kind: str, summary: str, gravity: str, details: str = "", topic: str = "",
                 tags: str = "", source: str = "") -> dict:
    """Add a new record to the research database. Only add information that came from the
    user or a source you can name - never invent facts. The record is stored as 'community'
    (unverified) and shown as such. gravity: moon, mars or zero_g (comma-separated if several).
    kind: experiment, facility, finding, concept, incident, report, paper, project, dataset,
    article or other. tags: comma-separated. source: citation or URL."""
    if kind not in KINDS:
        return {"error": f"kind must be one of {', '.join(KINDS)}"}
    try:
        rec = get_store().add({"title": title, "kind": kind, "summary": summary, "details": details,
                               "gravity": gravity, "topic": topic, "tags": tags, "source": source}, created_by="ai")
    except ValueError as e:
        return {"error": str(e)}
    return {"added": rec["slug"], "status": rec["status"]}


@tool("research", writes=True)
def add_research_fact(slug: str, name: str, value: float, unit: str, note: str = "") -> dict:
    """Attach a numeric fact (e.g. name='drop duration', value=5.18, unit='s') to an existing
    record. Stored as 'community' (unverified). Curated facts cannot be overwritten."""
    try:
        rec = get_store().add_fact(slug, name, value, unit, note, created_by="ai")
    except ValueError as e:
        return {"error": str(e)}
    return {"ok": True, "slug": rec["slug"], "facts": len(rec["facts"])}
