import json

import pytest
import requests

import agents
import config
import runstore


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


# --- Pipeline ------------------------------------------------------------


def _stub_outputs(monkeypatch, failing_agent=None):
    """Replace call_model with a deterministic stub. Returns the call log."""
    calls = []

    def fake_call_model(system, user, *, model, temperature, on_token=None, should_cancel=None):
        calls.append({"system": system, "user": user, "model": model})
        if failing_agent and failing_agent in system[:400]:
            raise agents.OllamaError("boom", "do the thing")
        if "## LINKEDIN" in system:
            body = "## LINKEDIN\npost body\n\n## SUBSTACK\narticle body\n\n## NOTION\nref body"
        else:
            body = f"output-{len(calls)}"
        if on_token:
            on_token(body)
        if should_cancel and should_cancel():
            raise agents.RunCancelled()
        return body

    monkeypatch.setattr(agents, "call_model", fake_call_model)
    monkeypatch.setattr(agents, "resolve_model", lambda preferred=None: ("stub-model", "local"))
    return calls


def test_run_pipeline_runs_four_agents_in_order(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    _stub_outputs(monkeypatch)
    events = []

    result = agents.run_pipeline(
        "vector databases", on_event=events.append, run_id="vd-20260809-1200"
    )

    starts = [event["agent"] for event in events if event["type"] == "agent_start"]
    assert starts == ["scout", "architect", "builder", "publisher"]
    assert [event["step"] for event in events if event["type"] == "agent_start"] == [1, 2, 3, 4]
    assert all(event["total"] == 4 for event in events if event["type"] == "agent_start")
    assert result["run_id"] == "vd-20260809-1200"


def test_run_pipeline_emits_tokens_before_completion(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    _stub_outputs(monkeypatch)
    events = []
    agents.run_pipeline("topic", on_event=events.append, run_id="t-20260809-1200")

    types = [event["type"] for event in events]
    assert types.index("agent_token") < types.index("agent_complete")
    assert types[-1] == "pipeline_complete"


def test_run_pipeline_feeds_prior_outputs_forward(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    calls = _stub_outputs(monkeypatch)
    agents.run_pipeline("topic", on_event=lambda event: None, run_id="t-20260809-1200")

    assert "RESEARCH BRIEF" not in calls[0]["user"]
    assert "RESEARCH BRIEF" in calls[1]["user"]
    assert "LEARNING PATH" in calls[2]["user"]
    assert all(
        label in calls[3]["user"]
        for label in ("RESEARCH BRIEF", "LEARNING PATH", "PROJECT SPEC")
    )


def test_run_pipeline_writes_seven_files_only_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    _stub_outputs(monkeypatch)
    result = agents.run_pipeline("topic", on_event=lambda e: None, run_id="t-20260809-1200")

    assert len(result["files"]) == 7
    directory = runstore.safe_run_dir("t-20260809-1200")
    assert (directory / "04-writer-combined.md").exists()
    assert (directory / "run.json").exists()


def test_run_pipeline_writes_nothing_when_an_agent_fails(monkeypatch, tmp_path):
    output_dir = tmp_path / "output"
    monkeypatch.setattr(config, "OUTPUT_DIR", output_dir)
    _stub_outputs(monkeypatch, failing_agent="capstone project")  # the Builder
    events = []

    with pytest.raises(agents.OllamaError):
        agents.run_pipeline("topic", on_event=events.append, run_id="t-20260809-1200")

    # Atomic: no folder at all, not even a partial one.
    assert not (output_dir / "t-20260809-1200").exists()
    assert list(output_dir.glob("*.partial")) == [] if output_dir.exists() else True

    error = [event for event in events if event["type"] == "error"][0]
    assert error["agent"] == "builder"
    assert error["hint"] == "do the thing"
    # Completed work is reported back so a retry can resume rather than restart.
    assert set(error["completed"]) == {"research", "learning"}


def test_run_pipeline_resumes_from_prior_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    calls = _stub_outputs(monkeypatch)

    agents.run_pipeline(
        "topic",
        on_event=lambda e: None,
        run_id="t-20260809-1200",
        prior={"research": "cached research", "learning": "cached path"},
    )

    # Only the Builder and Publisher should have been called.
    assert len(calls) == 2
    assert "cached research" in calls[0]["user"]


def test_run_pipeline_reports_missing_writer_sections(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")

    def fake_call_model(system, user, *, model, temperature, on_token=None, should_cancel=None):
        if "## LINKEDIN" in system:
            return "## LINKEDIN\nonly the post survived"
        return "fine"

    monkeypatch.setattr(agents, "call_model", fake_call_model)
    monkeypatch.setattr(agents, "resolve_model", lambda preferred=None: ("stub", "local"))
    events = []
    result = agents.run_pipeline("topic", on_event=events.append, run_id="t-20260809-1200")

    assert sorted(result["missing_sections"]) == ["notion", "substack"]
    # The combined backup is always kept, so nothing is ever lost.
    assert (runstore.safe_run_dir("t-20260809-1200") / "04-writer-combined.md").is_file()


def test_run_pipeline_cancel_writes_nothing_and_emits_cancelled(monkeypatch, tmp_path):
    output_dir = tmp_path / "output"
    monkeypatch.setattr(config, "OUTPUT_DIR", output_dir)
    _stub_outputs(monkeypatch)
    events = []

    with pytest.raises(agents.RunCancelled):
        agents.run_pipeline(
            "topic",
            on_event=events.append,
            run_id="t-20260809-1200",
            should_cancel=lambda: True,
        )

    assert not (output_dir / "t-20260809-1200").exists()
    assert [event for event in events if event["type"] == "cancelled"]
