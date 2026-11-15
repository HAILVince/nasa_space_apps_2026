"""The SI API client: the key is optional over loopback, a rejected key falls back to a
keyless local call, a remote API always needs the key, and every failure names its reason.
The SI API is faked with an httpx mock transport - no network."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from blackfox import settings as settings_module
from blackfox.llm import LLMError
from blackfox.llm import axioma

MESSAGES = [{"role": "user", "content": "hi"}]
REAL_CLIENT = httpx.AsyncClient


def make(monkeypatch, base, key, handler):
    """An AxiomaLLM whose HTTP calls go to handler(request) -> httpx.Response; returns (llm, seen requests)."""
    seen = []

    def record(request):
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(axioma.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(record), **kw))
    s = SimpleNamespace(ai_base=base, ai_key=key, model_preference=["big", "small"], ai_timeout=5)
    return axioma.AxiomaLLM(s), seen


def api(needs_key=None):
    """A fake key manager. needs_key: the bearer token it wants, or None to accept everybody."""
    def handler(request):
        auth = request.headers.get("authorization")
        if needs_key and auth is not None and auth != f"Bearer {needs_key}":
            return httpx.Response(401, json={"error": "bad key"})
        if needs_key and auth is None and needs_key != "local-ok":
            return httpx.Response(401, json={"error": "key required"})
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "big"}, {"id": "small"}]})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"pool": {}})
        model = json.loads(request.content)["model"]
        return httpx.Response(200, json={"model": model, "choices": [{"message": {"role": "assistant", "content": "ok"}}]})
    return handler


def chat(llm):
    return asyncio.run(llm.chat(MESSAGES))


def test_loopback_works_without_a_key(monkeypatch):
    llm, seen = make(monkeypatch, "http://127.0.0.1:8084/v1", "", api())
    assert chat(llm).message["content"] == "ok"
    assert all("authorization" not in r.headers for r in seen)


def test_loopback_falls_back_to_keyless_when_the_key_is_rejected(monkeypatch):
    llm, seen = make(monkeypatch, "http://localhost:8084/v1", "old-key", api(needs_key="local-ok"))
    assert chat(llm).model == "big"
    assert seen[0].headers["authorization"] == "Bearer old-key" and "authorization" not in seen[1].headers
    before = len(seen)
    chat(llm)                                             # remembered: no more calls with the rejected key
    assert all("authorization" not in r.headers for r in seen[before:])
    assert asyncio.run(llm.status()) == {"loopback": True, "key_set": True, "reachable": True, "authorized": True,
                                         "keyless": True, "model": "big", "problem": ""}


def test_a_good_key_is_sent_and_never_dropped(monkeypatch):
    llm, seen = make(monkeypatch, "http://127.0.0.1:8084/v1", "good", api(needs_key="good"))
    assert chat(llm).message["content"] == "ok"
    assert all(r.headers["authorization"] == "Bearer good" for r in seen)
    assert asyncio.run(llm.status())["keyless"] is False


def test_loopback_reports_auth_when_the_api_wants_a_key_we_do_not_have(monkeypatch):
    llm, _ = make(monkeypatch, "http://127.0.0.1:8084/v1", "wrong", api(needs_key="right"))
    with pytest.raises(LLMError) as e:
        chat(llm)
    assert e.value.reason == "auth" and asyncio.run(llm.status())["problem"] == "auth"
    llm, _ = make(monkeypatch, "http://127.0.0.1:8084/v1", "", api(needs_key="right"))
    with pytest.raises(LLMError) as e:
        chat(llm)
    assert e.value.reason == "no_key"


def test_a_remote_api_always_needs_the_key(monkeypatch):
    llm, seen = make(monkeypatch, "https://ai.example.com/v1", "", api())
    with pytest.raises(LLMError) as e:
        chat(llm)
    assert e.value.reason == "no_key" and seen == []      # nothing is sent without a key
    assert asyncio.run(llm.status())["problem"] == "no_key"
    llm, seen = make(monkeypatch, "https://ai.example.com/v1", "wrong", api(needs_key="local-ok"))
    with pytest.raises(LLMError) as e:
        chat(llm)
    assert e.value.reason == "auth" and all("authorization" in r.headers for r in seen)   # no keyless retry off-machine


def test_unreachable_and_busy_are_told_apart(monkeypatch):
    def down(request):
        raise httpx.ConnectError("connection refused", request=request)
    llm, seen = make(monkeypatch, "http://127.0.0.1:8084/v1", "k", down)
    with pytest.raises(LLMError) as e:
        chat(llm)
    assert e.value.reason == "unreachable" and "127.0.0.1:8084" in str(e.value)
    assert asyncio.run(llm.status())["problem"] == "unreachable"

    def limited(request):
        return httpx.Response(429, json={"error": "all keys parked"})
    llm, seen = make(monkeypatch, "http://127.0.0.1:8084/v1", "k", limited)
    with pytest.raises(LLMError) as e:
        chat(llm)
    posts = [r for r in seen if r.method == "POST"]
    assert e.value.reason == "busy" and len(posts) == 2      # every preferred model was tried


def test_settings_fall_back_to_the_server_env_file(monkeypatch, tmp_path):
    env = tmp_path / "blackfox.env"
    env.write_text("# server settings\nBLACKFOX_AI_KEY='from-file'\nBLACKFOX_AI_BASE=http://127.0.0.1:9000/v1\nOTHER=x\n")
    monkeypatch.setenv("BLACKFOX_ENV_FILE", str(env))
    monkeypatch.setattr(settings_module, "_env_file", None)
    monkeypatch.delenv("BLACKFOX_AI_KEY", raising=False)
    monkeypatch.delenv("BLACKFOX_AI_BASE", raising=False)
    s = settings_module.Settings()
    assert s.ai_key == "from-file" and s.ai_base == "http://127.0.0.1:9000/v1"
    monkeypatch.setenv("BLACKFOX_AI_KEY", "")                 # an explicit value wins, even an empty one
    assert settings_module.Settings().ai_key == ""
    monkeypatch.setenv("BLACKFOX_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.setattr(settings_module, "_env_file", None)
    monkeypatch.delenv("BLACKFOX_AI_KEY", raising=False)
    assert settings_module.Settings().ai_key == ""
