import json

import pytest
import requests

import agents
import config


class FakeResponse:
    """Stands in for a streaming requests.Response."""

    def __init__(self, chunks, status_code=200):
        self._chunks = chunks
        self.status_code = status_code

    def iter_lines(self):
        for chunk in self._chunks:
            yield json.dumps(chunk).encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return json.loads(json.dumps(self._chunks))

    def close(self):
        pass


def _token(text, done=False):
    return {"message": {"content": text}, "done": done}


def test_call_model_concatenates_streamed_tokens(monkeypatch):
    captured = {}

    def fake_post(url, json=None, stream=None, timeout=None, headers=None):
        captured["url"] = url
        captured["payload"] = json
        captured["timeout"] = timeout
        return FakeResponse([_token("Hello "), _token("world"), _token("", done=True)])

    monkeypatch.setattr(agents.requests, "post", fake_post)
    seen = []
    result = agents.call_model(
        "sys", "usr", model="m", temperature=0.5, on_token=seen.append
    )

    assert result == "Hello world"
    assert seen == ["Hello ", "world"]
    assert captured["url"].endswith("/api/chat")


def test_call_model_sets_num_ctx_and_num_predict(monkeypatch):
    captured = {}

    def fake_post(url, json=None, **kwargs):
        captured.update(json)
        return FakeResponse([_token("x", done=True)])

    monkeypatch.setattr(agents.requests, "post", fake_post)
    agents.call_model("sys", "usr", model="m", temperature=0.3)

    options = captured["options"]
    assert options["num_ctx"] == config.NUM_CTX, "num_ctx must be explicit or context truncates"
    assert options["num_predict"] == config.MAX_TOKENS
    assert options["temperature"] == 0.3
    assert captured["stream"] is True
    assert captured["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["messages"][1] == {"role": "user", "content": "usr"}


def test_call_model_uses_idle_read_timeout(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["timeout"] = timeout
        return FakeResponse([_token("x", done=True)])

    monkeypatch.setattr(agents.requests, "post", fake_post)
    agents.call_model("s", "u", model="m", temperature=0.7)

    connect, read = captured["timeout"]
    assert connect == config.CONNECT_TIMEOUT
    assert read == config.AGENT_IDLE_TIMEOUT


def test_call_model_sends_auth_header_only_when_key_is_set(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, **kwargs):
        captured["headers"] = headers or {}
        return FakeResponse([_token("x", done=True)])

    monkeypatch.setattr(agents.requests, "post", fake_post)

    monkeypatch.setattr(config, "OLLAMA_API_KEY", None)
    agents.call_model("s", "u", model="m", temperature=0.7)
    assert "Authorization" not in captured["headers"]

    monkeypatch.setattr(config, "OLLAMA_API_KEY", "secret-key")
    agents.call_model("s", "u", model="m", temperature=0.7)
    assert captured["headers"]["Authorization"] == "Bearer secret-key"


def test_call_model_omits_keep_alive_for_cloud_models(monkeypatch):
    captured = {}

    def fake_post(url, json=None, **kwargs):
        captured.update(json)
        return FakeResponse([_token("x", done=True)])

    monkeypatch.setattr(agents.requests, "post", fake_post)

    agents.call_model("s", "u", model="llama3.2:latest", temperature=0.7)
    assert captured["keep_alive"] == config.KEEP_ALIVE

    captured.clear()
    agents.call_model("s", "u", model="gpt-oss:120b-cloud", temperature=0.7)
    assert "keep_alive" not in captured


def test_call_model_raises_actionable_error_when_ollama_is_down(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(agents.requests, "post", fake_post)
    with pytest.raises(agents.OllamaError) as excinfo:
        agents.call_model("s", "u", model="m", temperature=0.7)
    assert "ollama serve" in excinfo.value.hint


def test_call_model_raises_actionable_error_on_missing_model(monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse([{"error": 'model "ghost" not found, try pulling it first'}])

    monkeypatch.setattr(agents.requests, "post", fake_post)
    with pytest.raises(agents.OllamaError) as excinfo:
        agents.call_model("s", "u", model="ghost", temperature=0.7)
    assert "ollama pull ghost" in excinfo.value.hint


def test_call_model_raises_actionable_error_on_cloud_auth_failure(monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse([{"error": "unauthorized"}])

    monkeypatch.setattr(agents.requests, "post", fake_post)
    with pytest.raises(agents.OllamaError) as excinfo:
        agents.call_model("s", "u", model="gpt-oss:120b-cloud", temperature=0.7)
    assert "ollama signin" in excinfo.value.hint


def test_call_model_raises_on_idle_timeout(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.ReadTimeout("no tokens")

    monkeypatch.setattr(agents.requests, "post", fake_post)
    with pytest.raises(agents.OllamaError) as excinfo:
        agents.call_model("s", "u", model="m", temperature=0.7)
    assert "stopped producing output" in str(excinfo.value)


def test_call_model_stops_promptly_when_cancelled(monkeypatch):
    emitted = []

    def fake_post(*args, **kwargs):
        return FakeResponse([_token("a"), _token("b"), _token("c", done=True)])

    monkeypatch.setattr(agents.requests, "post", fake_post)
    with pytest.raises(agents.RunCancelled):
        agents.call_model(
            "s", "u", model="m", temperature=0.7,
            on_token=emitted.append,
            should_cancel=lambda: len(emitted) >= 2,
        )
    assert len(emitted) == 2


def test_is_cloud_model_recognizes_both_forms():
    assert agents.is_cloud_model("gpt-oss:120b-cloud")
    assert agents.is_cloud_model("deepseek-v4-flash")
    assert not agents.is_cloud_model("llama3.2:latest")


def test_resolve_model_prefers_the_requested_model_when_present(monkeypatch):
    monkeypatch.setattr(agents, "list_local_models", lambda: ["llama3.2:latest"])
    assert agents.resolve_model("llama3.2:latest") == ("llama3.2:latest", "local")


def test_resolve_model_passes_cloud_names_through_untouched(monkeypatch):
    monkeypatch.setattr(agents, "list_local_models", lambda: [])
    assert agents.resolve_model("gpt-oss:120b-cloud") == ("gpt-oss:120b-cloud", "cloud")


def test_resolve_model_falls_back_to_an_installed_model(monkeypatch):
    monkeypatch.setattr(agents, "list_local_models", lambda: ["llama3.2:latest", "tinyllama"])
    monkeypatch.setattr(config, "FALLBACK_MODEL", "llama3.1:8b")
    model, mode = agents.resolve_model("llama3.1:8b")
    assert mode == "local"
    assert model in {"llama3.2:latest", "tinyllama"}


def test_resolve_model_raises_when_nothing_is_available(monkeypatch):
    monkeypatch.setattr(agents, "list_local_models", lambda: [])
    with pytest.raises(agents.OllamaError) as excinfo:
        agents.resolve_model("llama3.1:8b")
    assert "ollama pull" in excinfo.value.hint or "ollama signin" in excinfo.value.hint
