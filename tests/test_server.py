import pytest
from fastapi.testclient import TestClient

import agents
import config
import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(agents, "resolve_model", lambda preferred=None: ("stub", "local"))
    monkeypatch.setattr(agents, "list_local_models", lambda: ["stub"])

    def fake_call_model(
        system, user, *, model, temperature,
        on_token=None, on_thinking=None, should_cancel=None,
    ):
        text = (
            "## LINKEDIN\npost\n\n## SUBSTACK\narticle\n\n## NOTION\nreference"
            if "## LINKEDIN" in system
            else "generated body"
        )
        if on_token:
            on_token(text)
        return text

    monkeypatch.setattr(agents, "call_model", fake_call_model)
    server.registry = server.RunRegistry()
    with TestClient(server.app) as test_client:
        yield test_client


def _drain(websocket):
    """Read events until the run reaches a terminal state."""
    received = []
    while True:
        event = websocket.receive_json()
        received.append(event)
        if event["type"] in {"pipeline_complete", "error", "cancelled"}:
            return received


def test_health_reports_ollama_status(client):
    body = client.get("/api/health").json()
    assert body["ollama"] is True
    assert body["app"] == config.APP_NAME


def test_models_lists_local_and_cloud(client):
    body = client.get("/api/models").json()
    assert "stub" in body["local"]
    assert any(name.endswith("-cloud") for name in body["cloud"])


def test_run_then_websocket_replays_missed_events(client):
    run_id = client.post("/api/run", json={"topic": "vector databases"}).json()["run_id"]

    # Connect *after* the run was started: every event must still arrive.
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        received = _drain(websocket)

    types = [event["type"] for event in received]
    assert types.count("agent_start") == 4
    assert types[-1] == "pipeline_complete"
    assert [event["agent"] for event in received if event["type"] == "agent_start"] == [
        "scout", "architect", "builder", "publisher"
    ]


def test_runs_lifecycle(client):
    run_id = client.post("/api/run", json={"topic": "kafka in fintech"}).json()["run_id"]
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        _drain(websocket)

    listing = client.get("/api/runs").json()
    assert [entry["run_id"] for entry in listing] == [run_id]
    assert listing[0]["topic"] == "kafka in fintech"

    detail = client.get(f"/api/runs/{run_id}").json()
    assert len(detail["files"]) == 7
    assert detail["files"][0]["word_count"] > 0

    single = client.get(f"/api/runs/{run_id}/01-research-brief.md")
    assert single.status_code == 200
    assert "generated body" in single.text

    assert client.delete(f"/api/runs/{run_id}").status_code == 200
    assert client.get("/api/runs").json() == []


def test_archive_contains_every_file_plus_metadata(client):
    import io
    import zipfile

    run_id = client.post("/api/run", json={"topic": "zip me"}).json()["run_id"]
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        _drain(websocket)

    response = client.get(f"/api/runs/{run_id}/archive")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert run_id in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = sorted(archive.namelist())
        assert len(names) == 8, names
        assert "run.json" in names
        # Decision #10: the raw writer response ships with the archive.
        assert "04-writer-combined.md" in names
        assert archive.read("01-research-brief.md").decode("utf-8") == "generated body"


def test_archive_route_is_not_shadowed_by_the_file_route(client):
    """`archive` must not be treated as a filename and rejected by the whitelist."""
    run_id = client.post("/api/run", json={"topic": "ordering"}).json()["run_id"]
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        _drain(websocket)
    assert client.get(f"/api/runs/{run_id}/archive").status_code == 200


def test_archive_of_unknown_run_is_404(client):
    assert client.get("/api/runs/no-such-run-20260101-0000/archive").status_code == 404


def test_archive_rejects_traversal(client):
    assert client.get("/api/runs/..%2F..%2Fetc/archive").status_code in (400, 404)


def test_plain_query_strips_markdown_and_the_verify_block(client, monkeypatch):
    """The LinkedIn copy button pastes straight into LinkedIn."""

    def fake_call_model(
        system, user, *, model, temperature,
        on_token=None, on_thinking=None, should_cancel=None,
    ):
        if "## LINKEDIN" in system:
            return (
                "## LINKEDIN\n**Bold** hook with `code` and [a link](http://x.dev).\n\n"
                "## Verify before publishing\n- Verify the invented statistic.\n\n"
                "## SUBSTACK\narticle\n\n## NOTION\nreference"
            )
        return "body"

    monkeypatch.setattr(agents, "call_model", fake_call_model)
    run_id = client.post("/api/run", json={"topic": "plain text"}).json()["run_id"]
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        _drain(websocket)

    raw = client.get(f"/api/runs/{run_id}/04-linkedin-post.md").text
    assert "**Bold**" in raw and "Verify before publishing" in raw

    plain = client.get(f"/api/runs/{run_id}/04-linkedin-post.md?plain=1").text
    assert "**" not in plain
    assert "`" not in plain
    assert "](" not in plain
    assert "Bold hook with code and a link." in plain
    assert "Verify before publishing" not in plain
    assert "invented statistic" not in plain


def test_run_single_agent_endpoint(client):
    body = client.post("/api/run/single", json={"topic": "topic", "agent": "research"}).json()
    assert body["agent"] == "scout"
    assert body["output"] == "generated body"


def test_run_single_rejects_unknown_agent(client):
    assert client.post(
        "/api/run/single", json={"topic": "t", "agent": "nobody"}
    ).status_code == 422


@pytest.mark.parametrize("run_id", ["../etc", "..", "a/b", "C:/Windows"])
def test_path_traversal_is_rejected(client, run_id):
    """Any 4xx is a valid rejection.

    A run id containing a slash makes the URL match the two-segment file route,
    which has no DELETE handler, so those arrive as 405 rather than 400. What
    matters is that nothing is read or deleted and the response is an error.
    """
    assert 400 <= client.get(f"/api/runs/{run_id}").status_code < 500
    assert 400 <= client.delete(f"/api/runs/{run_id}").status_code < 500


def test_arbitrary_file_read_is_rejected(client):
    response = client.get("/api/runs/whatever-20260809-1200/../../config.py")
    assert response.status_code in (400, 404)


def test_unknown_output_filename_is_rejected(client):
    response = client.get("/api/runs/whatever-20260809-1200/arbitrary.md")
    assert response.status_code == 400


def test_empty_topic_is_rejected(client):
    assert client.post("/api/run", json={"topic": "   "}).status_code == 422


def test_profile_round_trip(client, tmp_path, monkeypatch):
    import prompts

    monkeypatch.setattr(prompts, "PROFILE_PATH", tmp_path / "profile.md")
    assert client.put("/api/profile", json={"content": "## Who I am\nnew ✍️"}).status_code == 200
    assert "✍️" in client.get("/api/profile").json()["content"]


def test_config_round_trip(client):
    original = config.MODEL_NAME
    try:
        body = client.put("/api/config", json={"model": "stub", "temperature": 0.42}).json()
        assert body["temperature"] == 0.42
        assert client.get("/api/config").json()["model"] == "stub"
    finally:
        config.update(original, 0.7)


def test_cancel_marks_the_run_cancelled(client):
    run_id = client.post("/api/run", json={"topic": "slow topic"}).json()["run_id"]
    client.post(f"/api/run/{run_id}/cancel")
    assert client.get(f"/api/run/{run_id}/state").json()["status"] in {
        "cancelled", "cancelling", "complete"
    }


def test_retry_returns_immediately_rather_than_awaiting_the_pipeline(client, monkeypatch):
    """A retry that blocks the HTTP request would hang the browser for minutes."""
    calls = {"count": 0}

    def failing_call_model(
        system, user, *, model, temperature,
        on_token=None, on_thinking=None, should_cancel=None,
    ):
        calls["count"] += 1
        # Fail the Builder on the first attempt only.
        if "capstone project" in system[:400] and calls["count"] < 4:
            raise agents.OllamaError("builder exploded", "fix it")
        if "## LINKEDIN" in system:
            return "## LINKEDIN\np\n\n## SUBSTACK\ns\n\n## NOTION\nn"
        return "body"

    monkeypatch.setattr(agents, "call_model", failing_call_model)

    run_id = client.post("/api/run", json={"topic": "retry me"}).json()["run_id"]
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        events = _drain(websocket)
    assert events[-1]["type"] == "error"
    assert client.get(f"/api/run/{run_id}/state").json()["status"] == "failed"
    # Scout and Architect succeeded; their output is retained for the retry.
    assert client.get(f"/api/run/{run_id}/state").json()["completed"] == ["learning", "research"]

    response = client.post(f"/api/run/{run_id}/retry")
    assert response.status_code == 200
    assert response.json()["status"] in {"queued", "running", "complete"}

    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        _drain(websocket)
    assert client.get(f"/api/run/{run_id}/state").json()["status"] == "complete"


def test_retry_resumes_rather_than_rerunning_completed_agents(client, monkeypatch):
    seen = []

    def failing_call_model(
        system, user, *, model, temperature,
        on_token=None, on_thinking=None, should_cancel=None,
    ):
        if "research analyst" in system[:120]:
            seen.append("scout")
        if "capstone project" in system[:400] and len(seen) < 2:
            seen.append("builder-fail")
            raise agents.OllamaError("boom", "hint")
        if "## LINKEDIN" in system:
            return "## LINKEDIN\np\n\n## SUBSTACK\ns\n\n## NOTION\nn"
        return "body"

    monkeypatch.setattr(agents, "call_model", failing_call_model)
    run_id = client.post("/api/run", json={"topic": "resume me"}).json()["run_id"]
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        _drain(websocket)

    client.post(f"/api/run/{run_id}/retry")
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        _drain(websocket)

    # The Scout ran once, on the first attempt only.
    assert seen.count("scout") == 1


def test_retry_of_a_complete_run_is_rejected(client):
    run_id = client.post("/api/run", json={"topic": "already done"}).json()["run_id"]
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        _drain(websocket)
    assert client.post(f"/api/run/{run_id}/retry").status_code == 409


def test_a_run_beyond_the_cap_reports_queued(tmp_path, monkeypatch):
    """Driven directly against the registry.

    Going through TestClient here would mean racing its portal loop to observe a
    transient state; asserting on the registry is both clearer and instant.
    """
    import asyncio

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "MAX_CONCURRENT_RUNS", 1)
    monkeypatch.setattr(agents, "resolve_model", lambda preferred=None: ("stub", "local"))

    async def scenario():
        registry = server.RunRegistry()
        first = registry.create("first", None, None)
        second = registry.create("second", None, None)

        release = asyncio.Event()

        async def fake_pipeline(run_id):
            """Stand in for start()'s body: hold the semaphore until released."""
            async with registry._semaphore:
                await release.wait()

        # Occupy the only slot.
        holder = asyncio.create_task(fake_pipeline(first))
        await asyncio.sleep(0)  # let it acquire

        def blocking_pipeline(*args, **kwargs):
            return {"type": "pipeline_complete", "run_id": second, "folder": "",
                    "files": [], "missing_sections": []}

        monkeypatch.setattr(agents, "run_pipeline", blocking_pipeline)
        queued_task = asyncio.create_task(registry.start(second))
        await asyncio.sleep(0.05)

        kinds = [event["type"] for event in registry.events(second)]
        assert kinds == ["queued"], kinds
        assert registry.state(second)["status"] == "queued"

        release.set()
        await holder
        await queued_task
        assert registry.state(second)["status"] == "complete"

    asyncio.run(scenario())


def test_state_of_unknown_run_is_404(client):
    assert client.get("/api/run/no-such-run-20260101-0000/state").status_code == 404


def test_websocket_on_unknown_run_reports_an_error(client):
    with client.websocket_connect("/ws/pipeline/no-such-run-20260101-0000") as websocket:
        event = websocket.receive_json()
    assert event["type"] == "error"


def test_index_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert config.APP_NAME in response.text
