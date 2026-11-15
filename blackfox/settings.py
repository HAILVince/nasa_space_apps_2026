"""Every tunable of the Black Fox stack in one place, read from the environment
(/etc/blackfox.env on the VPS). Swapping an implementation = changing a value here,
not editing code:

  BLACKFOX_DATA_DIR          where the SQLite files live (default: systemd's $STATE_DIRECTORY, else ./data)
  BLACKFOX_DB_BACKEND        research store implementation   (json)
  BLACKFOX_KNOWLEDGE_DIR     the JSON research database      (default: blackfox/db/knowledge in the repo)
  BLACKFOX_FULLTEXT_DIR      optional full texts for it      (default: <data dir>/fulltext)
  BLACKFOX_MEMORY_BACKEND    model memory implementation     (sqlite)
  BLACKFOX_LLM_BACKEND       LLM provider                    (chain)
                               axioma -> the VPS AI API over HTTP (ai_api.service, Groq key pool)
                               agency -> import AI_agency.api_manager in-process (no AI API, no key)
                               auto   -> axioma when an AI API key is known, else agency if importable
                               gemini -> Google Gemini only (BLACKFOX_GEMINI_KEY)
                               chain  -> Gemini first, `auto` (Groq) as fallback; = auto without a Gemini key
  BLACKFOX_GEMINI_KEY        Gemini API key (env file only, never in git)
  BLACKFOX_GEMINI_MODELS     comma list, first tried first    (gemini-flash-latest)
  BLACKFOX_AI_BASE           AI API base URL                 (http://127.0.0.1:8084/v1)
  BLACKFOX_AI_KEY            AI API key (optional when the AI API is on this machine: see llm/axioma.py)
  BLACKFOX_AI_CONFIG         that config: config.json -> ai_api.keys (/home/debian/automation/config.json; "" = off)
  BLACKFOX_AGENCY_DIR        folder holding AI_agency.py for the agency backend (/home/debian/automation; "" = off)
  BLACKFOX_ENV_FILE          env file read when a variable is not set in the process (/etc/blackfox.env)
  BLACKFOX_ASKS_PER_MINUTE   AI chat messages allowed per minute per IP address (6)
  BLACKFOX_MODEL_PREFERENCE  comma list, best first; the first one with free capacity is used
  BLACKFOX_TOOL_TRANSPORT    how the harness reaches the MCP server:
                               http   -> BLACKFOX_MCP_URL (the blackfox-mcp service)
                               inproc -> builds the MCP server inside the web process (dev / fallback)
  BLACKFOX_MCP_URL           http://127.0.0.1:8087/mcp
  BLACKFOX_MCP_TOKEN         bearer token the MCP server requires
  BLACKFOX_TOOL_GROUPS       which tool groups exist (design,physics,memory,research,web)
  BLACKFOX_WEB_ALLOW         domains the search_web_page tool may fetch, comma list incl. subdomains
                             (ntrs.nasa.gov,psi.nasa.gov,nasa.gov,wikipedia.org); "*" = any public host
  BLACKFOX_WEB_PER_MINUTE    page fetches per minute per visitor (10)
  BLACKFOX_AGENT_MAX_STEPS   tool-call rounds per answer (8; opening a tool category costs one)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


_env_file: dict[str, str] | None = None


def _server_env() -> dict[str, str]:
    """BLACKFOX_* values from the server's env file. systemd gives them to the web service; a
    command typed in a shell on the server (python -m flame.ingest ..., blackfox.collect ...)
    does not get them, so they are read here. Missing or unreadable file = no values."""
    global _env_file
    if _env_file is None:
        _env_file = {}
        try:
            text = Path(os.environ.get("BLACKFOX_ENV_FILE", "/etc/blackfox.env")).read_text(encoding="utf-8")
        except OSError:
            text = ""
        for line in text.splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.startswith("BLACKFOX_"):
                _env_file[key] = value.strip().strip("'\"")
    return _env_file


def _env(name: str, default: str = "") -> str:
    if name in os.environ:          # an explicit value (even an empty one) always wins
        return os.environ[name].strip()
    return _server_env().get(name, default).strip()


AUTOMATION_DIR = "/home/debian/automation"
KEY_LABEL = "blackfoxhackathon"      # this site's entry in config.json -> ai_api.keys


def _ai_base() -> str:
    """BLACKFOX_AI_BASE, else the legacy BLACKFOX_AI_URL (a full .../v1/generate URL)."""
    base = _env("BLACKFOX_AI_BASE")
    if not base:
        base = _env("BLACKFOX_AI_URL").rstrip("/")
        for tail in ("/generate", "/chat/completions"):
            if base.endswith(tail):
                base = base[: -len(tail)]
    return (base or "http://127.0.0.1:8084/v1").rstrip("/")


def _ai_key() -> str:
    """BLACKFOX_AI_KEY, else the key the AI API itself accepts for this site: the
    loopback way on the VPS, no copying keys into env files."""
    key = _env("BLACKFOX_AI_KEY")
    if key:
        return key
    path = _env("BLACKFOX_AI_CONFIG", f"{AUTOMATION_DIR}/config.json")
    if not path:
        return ""
    try:
        import json
        entries = json.loads(Path(path).read_text(encoding="utf-8")).get("ai_api", {}).get("keys", []) or []
    except (OSError, ValueError, AttributeError):
        return ""
    named = [(str(e.get("key") or ""), str(e.get("name") or "")) if isinstance(e, dict) else (str(e or ""), "")
             for e in entries]
    named = [(k, n) for k, n in named if k]
    for k, n in named:
        if n == KEY_LABEL:
            return k
    return named[0][0] if named else ""


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in _env(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(
        _env("BLACKFOX_DATA_DIR") or _env("STATE_DIRECTORY").split(":")[0] or "data").resolve())
    vector_enabled: bool = field(default_factory=lambda: _env("BLACKFOX_VECTOR_ENABLED", "true").lower() in ("1", "true", "yes"))
    db_backend: str = field(default_factory=lambda: _env("BLACKFOX_DB_BACKEND", "json"))
    knowledge_dir_env: str = field(default_factory=lambda: _env("BLACKFOX_KNOWLEDGE_DIR"))
    fulltext_dir_env: str = field(default_factory=lambda: _env("BLACKFOX_FULLTEXT_DIR"))
    memory_backend: str = field(default_factory=lambda: _env("BLACKFOX_MEMORY_BACKEND", "sqlite"))

    llm_backend: str = field(default_factory=lambda: _env("BLACKFOX_LLM_BACKEND", "chain"))
    ai_base: str = field(default_factory=_ai_base)
    ai_key: str = field(default_factory=_ai_key, repr=False)
    agency_dir: str = field(default_factory=lambda: _env("BLACKFOX_AGENCY_DIR", AUTOMATION_DIR))
    model_preference: list[str] = field(default_factory=lambda: _list(
        "BLACKFOX_MODEL_PREFERENCE", "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b"))
    gemini_key: str = field(default_factory=lambda: _env("BLACKFOX_GEMINI_KEY"), repr=False)
    gemini_base: str = field(default_factory=lambda: _env(
        "BLACKFOX_GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/"))
    gemini_models: list[str] = field(default_factory=lambda: _list("BLACKFOX_GEMINI_MODELS", "gemini-flash-latest"))
    gemini_timeout: float = field(default_factory=lambda: float(_env("BLACKFOX_GEMINI_TIMEOUT", "40")))
    ai_timeout: float = field(default_factory=lambda: float(_env("BLACKFOX_AI_TIMEOUT", "90")))

    tool_transport: str = field(default_factory=lambda: _env("BLACKFOX_TOOL_TRANSPORT", "inproc"))
    mcp_url: str = field(default_factory=lambda: _env("BLACKFOX_MCP_URL", "http://127.0.0.1:8087/mcp"))
    mcp_token: str = field(default_factory=lambda: _env("BLACKFOX_MCP_TOKEN"))
    tool_groups: list[str] = field(default_factory=lambda: _list("BLACKFOX_TOOL_GROUPS", "design,physics,memory,research,web"))
    web_allow: list[str] = field(default_factory=lambda: [d.lower() for d in _list(
        "BLACKFOX_WEB_ALLOW", "ntrs.nasa.gov,psi.nasa.gov,nasa.gov,wikipedia.org")])
    web_per_minute: int = field(default_factory=lambda: int(_env("BLACKFOX_WEB_PER_MINUTE", "10")))

    asks_per_minute: int = field(default_factory=lambda: int(_env("BLACKFOX_ASKS_PER_MINUTE", "6")))
    agent_max_steps: int = field(default_factory=lambda: int(_env("BLACKFOX_AGENT_MAX_STEPS", "8")))
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
