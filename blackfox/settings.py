"""Every tunable of the Black Fox stack in one place, read from the environment
(/etc/blackfox.env on the VPS). Swapping an implementation = changing a value here,
not editing code:

  BLACKFOX_DATA_DIR          where the SQLite files live (default: systemd's $STATE_DIRECTORY, else ./data)
  BLACKFOX_DB_BACKEND        research store implementation   (json)
  BLACKFOX_KNOWLEDGE_DIR     the JSON research database      (default: blackfox/db/knowledge in the repo)
  BLACKFOX_FULLTEXT_DIR      optional full texts for it      (default: <data dir>/fulltext)
  BLACKFOX_MEMORY_BACKEND    model memory implementation     (sqlite)
  BLACKFOX_LLM_BACKEND       LLM provider                    (axioma = the VPS AI API)
  BLACKFOX_AI_BASE           AI API base URL                 (http://127.0.0.1:8084/v1)
  BLACKFOX_AI_KEY            AI API key
  BLACKFOX_MODEL_PREFERENCE  comma list, best first; the first one with free capacity is used
  BLACKFOX_TOOL_TRANSPORT    how the harness reaches the MCP server:
                               http   -> BLACKFOX_MCP_URL (the blackfox-mcp service)
                               inproc -> builds the MCP server inside the web process (dev / fallback)
  BLACKFOX_MCP_URL           http://127.0.0.1:8087/mcp
  BLACKFOX_MCP_TOKEN         bearer token the MCP server requires
  BLACKFOX_TOOL_GROUPS       which tool groups exist (design,physics,memory,research)
  BLACKFOX_AGENT_MAX_STEPS   tool-call rounds per answer (6)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in _env(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(
        _env("BLACKFOX_DATA_DIR") or _env("STATE_DIRECTORY").split(":")[0] or "data").resolve())
    db_backend: str = field(default_factory=lambda: _env("BLACKFOX_DB_BACKEND", "json"))
    knowledge_dir_env: str = field(default_factory=lambda: _env("BLACKFOX_KNOWLEDGE_DIR"))
    fulltext_dir_env: str = field(default_factory=lambda: _env("BLACKFOX_FULLTEXT_DIR"))
    memory_backend: str = field(default_factory=lambda: _env("BLACKFOX_MEMORY_BACKEND", "sqlite"))

    llm_backend: str = field(default_factory=lambda: _env("BLACKFOX_LLM_BACKEND", "axioma"))
    ai_base: str = field(default_factory=lambda: _env("BLACKFOX_AI_BASE", "http://127.0.0.1:8084/v1").rstrip("/"))
    ai_key: str = field(default_factory=lambda: _env("BLACKFOX_AI_KEY"))
    model_preference: list[str] = field(default_factory=lambda: _list(
        "BLACKFOX_MODEL_PREFERENCE", "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b"))
    ai_timeout: float = field(default_factory=lambda: float(_env("BLACKFOX_AI_TIMEOUT", "90")))

    tool_transport: str = field(default_factory=lambda: _env("BLACKFOX_TOOL_TRANSPORT", "inproc"))
    mcp_url: str = field(default_factory=lambda: _env("BLACKFOX_MCP_URL", "http://127.0.0.1:8087/mcp"))
    mcp_token: str = field(default_factory=lambda: _env("BLACKFOX_MCP_TOKEN"))
    tool_groups: list[str] = field(default_factory=lambda: _list("BLACKFOX_TOOL_GROUPS", "design,physics,memory,research"))

    agent_max_steps: int = field(default_factory=lambda: int(_env("BLACKFOX_AGENT_MAX_STEPS", "6")))
    agent_history_turns: int = field(default_factory=lambda: int(_env("BLACKFOX_AGENT_HISTORY", "10")))
    agent_max_tokens: int = field(default_factory=lambda: int(_env("BLACKFOX_AGENT_MAX_TOKENS", "1500")))
    agent_concurrency: int = field(default_factory=lambda: int(_env("BLACKFOX_AGENT_CONCURRENCY", "4")))

    @property
    def knowledge_dir(self) -> Path:
        return Path(self.knowledge_dir_env).resolve() if self.knowledge_dir_env else Path(__file__).parent / "db" / "knowledge"

    @property
    def fulltext_dir(self) -> Path:
        return Path(self.fulltext_dir_env).resolve() if self.fulltext_dir_env else self.data_dir / "fulltext"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.data_dir.mkdir(parents=True, exist_ok=True)
    return _settings
