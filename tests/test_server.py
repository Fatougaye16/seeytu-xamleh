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
