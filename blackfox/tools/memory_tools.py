"""Long-term memory tools. visitor_id is a context parameter: the harness fills it
in, the model never sees or chooses it."""

from ..memory import get_memory
from .registry import tool


@tool("memory", writes=True)
def remember(note: str, visitor_id: str = "") -> dict:
    """Save a short fact about the user or the ongoing work to long-term memory
    (e.g. 'User's team is building a wildfire app for the NASA Space Apps challenge').
    Only save things worth recalling in later conversations."""
    if not visitor_id:
        return {"error": "no visitor context"}
    try:
        return get_memory().remember(visitor_id, note)
    except ValueError as e:
        return {"error": str(e)}


@tool("memory")
def recall(query: str = "", visitor_id: str = "") -> dict:
    """Look up long-term memory notes, most relevant to query first."""
    if not visitor_id:
        return {"error": "no visitor context"}
    return {"notes": get_memory().recall(visitor_id, query)}


@tool("memory", writes=True)
def forget(note_id: int, visitor_id: str = "") -> dict:
    """Delete one long-term memory note by id (when the user asks you to forget something)."""
    if not visitor_id:
        return {"error": "no visitor context"}
    return {"deleted": get_memory().forget(visitor_id, note_id)}
