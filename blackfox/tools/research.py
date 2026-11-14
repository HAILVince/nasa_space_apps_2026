"""Research database tools (read + write) over blackfox.db.get_store()."""

from ..db import KINDS, get_store
from .registry import tool


@tool("research")
def search_research(query: str, kind: str = "", limit: int = 6) -> dict:
    """Full-text search of the central database of NASA research on fire and flames in
    microgravity / free fall (experiments, facilities, findings, concepts, incidents).
    kind optionally filters: experiment, facility, finding, concept, incident, dataset, other.
    Returns short summaries; call get_research(slug) for full details, facts and sources."""
    results = get_store().search(query, kind=kind or None, limit=limit)
    return {"count": len(results), "results": results}


@tool("research")
def get_research(slug: str) -> dict:
    """Full record by slug: details, numeric facts (with units) and sources."""
    rec = get_store().get(slug)
    if not rec:
        return {"error": f"no record '{slug}' - use search_research to find slugs"}
    return rec


@tool("research")
def list_research(kind: str = "", tag: str = "", limit: int = 50) -> dict:
    """List records, optionally filtered by kind or a single tag. Curated records come first."""
    rows = get_store().list(kind=kind or None, tag=tag or None, limit=limit)
    return {"count": len(rows), "records": [{k: r[k] for k in ("slug", "title", "kind", "status")} for r in rows]}


@tool("research")
def research_stats() -> dict:
    """Counts of records by kind and status (curated vs community) and number of facts."""
    return get_store().stats()


@tool("research", writes=True)
def add_research(title: str, kind: str, summary: str, details: str = "", platform: str = "",
                 agency: str = "", years: str = "", tags: str = "", source: str = "") -> dict:
    """Add a new record to the central research database. Only add information that came
    from the user or a source you can name - never invent facts. The record is stored as
    'community' (unverified) and shown as such. kind: experiment, facility, finding, concept,
    incident, dataset or other. tags: comma-separated. source: citation or URL."""
    if kind not in KINDS:
        return {"error": f"kind must be one of {', '.join(KINDS)}"}
    try:
        rec = get_store().add({"title": title, "kind": kind, "summary": summary, "details": details,
                               "platform": platform, "agency": agency, "years": years, "tags": tags,
                               "sources": [{"title": source}] if source else []}, created_by="ai")
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
