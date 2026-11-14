"""Model memory.

Two kinds, both scoped to one visitor (a random id in a cookie, never shared):
  * conversation history - the rolling chat the harness replays to the model
  * notes - long-term facts the model chose to remember (remember / recall /
    forget tools), injected into the system prompt on every turn

Add a backend: implement MemoryStore and register it in BACKENDS; select it with
BLACKFOX_MEMORY_BACKEND.
"""

from typing import Any, Protocol

from ..settings import get_settings


class MemoryStore(Protocol):
    # conversation
    def history(self, conversation_id: str, limit: int = 20) -> list[dict[str, Any]]: ...
    def append(self, conversation_id: str, visitor_id: str, role: str, content: str,
               trace: list | None = None, model: str = "") -> None: ...
    def clear_conversation(self, conversation_id: str) -> None: ...
    # long-term notes
    def remember(self, visitor_id: str, text: str) -> dict[str, Any]: ...
    def recall(self, visitor_id: str, query: str = "", limit: int = 10) -> list[dict[str, Any]]: ...
    def forget(self, visitor_id: str, note_id: int | None = None) -> int: ...


def _sqlite():
    from .sqlite_memory import SQLiteMemory
    return SQLiteMemory(get_settings().data_dir / "memory.db")


BACKENDS = {"sqlite": _sqlite}
_mem: MemoryStore | None = None


def get_memory() -> MemoryStore:
    global _mem
    if _mem is None:
        _mem = BACKENDS[get_settings().memory_backend]()
    return _mem
