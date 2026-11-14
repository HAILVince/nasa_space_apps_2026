"""The research store interface. Anything that implements ResearchStore can replace the
JSON version (Postgres, a vector DB, a remote API...) - register it in
blackfox/db/__init__.py and set BLACKFOX_DB_BACKEND."""

from __future__ import annotations

from typing import Any, Protocol

# what a record is; the collected sources use the first five
KINDS = ("report", "paper", "project", "dataset", "article",
         "experiment", "facility", "finding", "concept", "incident", "other")
# the only gravity environments the database covers
GRAVITIES = ("moon", "mars", "zero_g")


class ResearchStore(Protocol):
    def search(self, query: str, kind: str | None = None, limit: int = 8, gravity: str | None = None,
               topic: str | None = None, year_from: int | None = None, year_to: int | None = None) -> list[dict[str, Any]]: ...
    def get(self, slug: str) -> dict[str, Any] | None: ...
    def list(self, kind: str | None = None, gravity: str | None = None, topic: str | None = None,
             limit: int = 100, offset: int = 0) -> list[dict[str, Any]]: ...
    def read_text(self, slug: str, page: int = 1, find: str = "") -> dict[str, Any]: ...
    def add(self, record: dict[str, Any], created_by: str = "ai") -> dict[str, Any]: ...
    def add_fact(self, slug: str, name: str, value: float | None, unit: str, note: str,
                 created_by: str = "ai") -> dict[str, Any]: ...
    def stats(self) -> dict[str, Any]: ...
