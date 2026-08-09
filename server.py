"""FastAPI backend: REST endpoints, the run registry, and the progress WebSocket."""

import asyncio
import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

import agents
import config
import prompts
import resources
import runstore
from textutil import drop_verify_block, strip_markdown

STATIC_DIR = Path(__file__).with_name("static")

app = FastAPI(title=config.APP_NAME, description=config.TAGLINE)

# Event types that end a run, and therefore end a WebSocket subscription.
TERMINAL_EVENTS = {"pipeline_complete", "error", "cancelled"}


# --- Request models ------------------------------------------------------

class RunRequest(BaseModel):
    topic: str
    model: str | None = None
    temperature: float | None = None

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("topic must not be empty")
        return cleaned


class SingleAgentRequest(RunRequest):
    agent: str


class ProfileRequest(BaseModel):
    content: str


class ResourceRequest(BaseModel):
    kind: str
    name: str
    content: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned


class ConfigRequest(BaseModel):
    model: str | None = None
    temperature: float | None = None


# --- Run registry -------------------------------------------------------

class RunRegistry:
    """Tracks every run: its event history, subscribers, and cancel flag.

    The event buffer is the load-bearing piece. POST /api/run returns
    immediately and the browser connects a moment later; without a replayable
    buffer, every event in that gap — possibly the Scout's entire output —
    would be lost. The same buffer gives page-refresh recovery, mid-run
    re-attachment, and the completed-output snapshot that retry needs.
    """

    def __init__(self) -> None:
        self._runs: dict[str, dict] = {}
        self._semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_RUNS)

    def create(self, topic: str, model: str | None, temperature: float | None) -> str:
        run_id = runstore.mint_run_id(topic)
        self._runs[run_id] = {
            "run_id": run_id,
            "topic": topic,
            "model": model,
            "temperature": temperature,
            "status": "queued",
            "events": [],
            "subscribers": set(),
            "cancel": False,
            "completed": {},
        }
        return run_id

    def _require(self, run_id: str) -> dict:
        run = self._runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
        return run

    def events(self, run_id: str) -> list[dict]:
        return list(self._require(run_id)["events"])

    def state(self, run_id: str) -> dict:
        run = self._require(run_id)
        return {
            "run_id": run_id,
            "topic": run["topic"],
            "status": run["status"],
            "completed": sorted(run["completed"]),
        }

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._require(run_id)["subscribers"].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        run = self._runs.get(run_id)
        if run:
            run["subscribers"].discard(queue)

    def cancel(self, run_id: str) -> bool:
        run = self._require(run_id)
        run["cancel"] = True
        if run["status"] in {"queued", "running"}:
            run["status"] = "cancelling"
        return True

    def _publish(self, run: dict, event: dict) -> None:
        """Record an event and fan it out. Runs on the event loop thread."""
        run["events"].append(event)
        if event["type"] == "agent_complete":
            key = prompts.AGENT_META[event["agent"]]["output_key"]
            run["completed"][key] = event["output"]
        for queue in list(run["subscribers"]):
            queue.put_nowait(event)

    async def start(self, run_id: str) -> None:
        """Run the pipeline in a worker thread, bounded by the concurrency cap."""
        run = self._require(run_id)
        loop = asyncio.get_running_loop()

        def emit(event: dict) -> None:
            # Called from the worker thread — hop back to the loop before
            # touching subscriber queues, which are not thread-safe.
            loop.call_soon_threadsafe(self._publish, run, event)

        if self._semaphore.locked():
            # Tell the client it is waiting on the concurrency cap rather than
            # leaving it staring at a tracker where nothing ever starts.
            self._publish(run, {
                "type": "queued", "run_id": run_id,
                "message": f"Waiting — {config.MAX_CONCURRENT_RUNS} run"
                           f"{'s' if config.MAX_CONCURRENT_RUNS > 1 else ''} already in progress.",
            })

        async with self._semaphore:
            if run["cancel"]:
                self._publish(run, {
                    "type": "cancelled", "agent": None, "step": 0, "completed": [],
                })
                run["status"] = "cancelled"
                return
            run["status"] = "running"
            try:
                await asyncio.to_thread(
                    agents.run_pipeline,
                    run["topic"],
                    on_event=emit,
                    run_id=run_id,
                    prior=dict(run["completed"]),
                    model=run["model"],
                    temperature=run["temperature"],
                    should_cancel=lambda: run["cancel"],
                )
                run["status"] = "complete"
            except agents.RunCancelled:
                run["status"] = "cancelled"
            except agents.OllamaError:
                # run_pipeline already emitted the error event with its hint.
                run["status"] = "failed"
            except Exception as exc:  # unexpected: the client must still hear about it
                self._publish(run, {
                    "type": "error", "message": f"Unexpected failure: {exc}",
                    "hint": "", "agent": None, "step": 0, "completed": [],
                })
                run["status"] = "failed"

    def prepare_retry(self, run_id: str) -> None:
        """Validate and reset a failed run so start() can resume it.

        Deliberately synchronous and separate from start(): awaiting the
        pipeline inside the HTTP handler would hold the request open for the
        entire run — minutes — and the browser would appear to hang.
        """
        run = self._require(run_id)
        if run["status"] not in {"failed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Run is not in a retryable state")
        run["cancel"] = False
        run["status"] = "queued"
        # Drop the previous terminal event so a reconnecting client does not
        # replay the old failure and immediately close again.
        run["events"] = [
            event for event in run["events"] if event["type"] not in TERMINAL_EVENTS
        ]


registry = RunRegistry()


# --- Endpoints ----------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    status = agents.preflight()
    return {"app": config.APP_NAME, "tagline": config.TAGLINE, **status}


@app.get("/api/models")
def models() -> dict:
    """Local models come from /api/tags; cloud models cannot be discovered there."""
    try:
        local = agents.list_local_models()
    except agents.OllamaError:
        local = []
    return {"local": local, "cloud": agents.CLOUD_MODELS, "current": config.MODEL_NAME}


@app.post("/api/run")
async def start_run(request: RunRequest) -> dict:
    run_id = registry.create(request.topic, request.model, request.temperature)
    # Fire and forget: the client connects to the WebSocket next, and the event
    # buffer guarantees nothing emitted in the meantime is lost.
    asyncio.create_task(registry.start(run_id))
    return {"run_id": run_id, "topic": request.topic}


@app.post("/api/run/single")
async def run_single(request: SingleAgentRequest) -> dict:
    agent = prompts.AGENT_ALIASES.get(request.agent)
    if not agent:
        raise HTTPException(status_code=422, detail=f"Unknown agent: {request.agent}")
    model, _ = agents.resolve_model(request.model)
    try:
        output = await asyncio.to_thread(
            agents.run_agent,
            agent,
            request.topic,
            {},
            model=model,
            temperature=(
                config.TEMPERATURE if request.temperature is None else request.temperature
            ),
        )
    except agents.OllamaError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc), "hint": exc.hint})
    return {"agent": agent, "output": output}


@app.post("/api/run/{run_id}/cancel")
def cancel_run(run_id: str) -> dict:
    registry.cancel(run_id)
    return registry.state(run_id)


@app.post("/api/run/{run_id}/retry")
async def retry_run(run_id: str) -> dict:
    """Resume a failed run at the agent that failed, reusing completed output."""
    registry.prepare_retry(run_id)
    asyncio.create_task(registry.start(run_id))
    return registry.state(run_id)


@app.get("/api/run/{run_id}/state")
def run_state(run_id: str) -> dict:
    return registry.state(run_id)


@app.get("/api/runs")
def list_runs() -> list[dict]:
    return runstore.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    try:
        return runstore.read_run(run_id)
    except runstore.UnsafePath as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No such run: {run_id}")


@app.get("/api/runs/{run_id}/archive")
def get_run_archive(run_id: str) -> Response:
    """Every markdown file plus run.json, zipped in memory.

    Declared BEFORE the {filename} route: otherwise "archive" is captured as a
    filename and rejected by the whitelist. Containment reuses safe_run_dir, so
    no new path logic is introduced.
    """
    try:
        directory = runstore.safe_run_dir(run_id)
    except runstore.UnsafePath as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail=f"No such run: {run_id}")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix in {".md", ".json"}:
                archive.write(path, arcname=path.name)

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.zip"'},
    )


@app.get("/api/runs/{run_id}/{filename}", response_class=PlainTextResponse)
def get_run_file(run_id: str, filename: str, plain: bool = False) -> str:
    """One output file. `?plain=1` returns it ready to paste into LinkedIn.

    Stripping happens here rather than in the browser so it reuses the tested
    textutil functions instead of a second markdown stripper in JavaScript.
    """
    try:
        path = runstore.safe_run_file(run_id, filename)
    except runstore.UnsafePath as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"No such file: {filename}")

    content = path.read_text(encoding="utf-8")
    if plain:
        return strip_markdown(drop_verify_block(content))
    return content


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict:
    try:
        runstore.delete_run(run_id)
    except runstore.UnsafePath as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deleted": run_id}


@app.get("/api/resources")
def list_resources() -> dict:
    return {"resources": resources.listing(), "hint": resources.DROPZONE_HINT}


@app.post("/api/resources")
def add_resource(request: ResourceRequest) -> dict:
    try:
        return resources.add(request.kind, request.name, request.content)
    except resources.UnsupportedResource as exc:
        # 415: the request was well-formed, the format simply is not supported.
        raise HTTPException(status_code=415, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/resources/{resource_id}/toggle")
def toggle_resource(resource_id: str) -> dict:
    try:
        return resources.toggle(resource_id)
    except resources.UnsafeResource as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No such resource: {resource_id}")


@app.delete("/api/resources/{resource_id}")
def delete_resource(resource_id: str) -> dict:
    try:
        resources.remove(resource_id)
    except resources.UnsafeResource as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deleted": resource_id}


@app.get("/api/profile")
def get_profile() -> dict:
    return {"content": prompts.load_profile(), "path": str(prompts.PROFILE_PATH)}


@app.put("/api/profile")
def put_profile(request: ProfileRequest) -> dict:
    # A plain file write to profile.md. This endpoint never edits prompts.py:
    # a server that rewrites its own source can corrupt the module on an
    # escaping bug and take the whole app down with it.
    prompts.save_profile(request.content)
    return {"saved": True, "path": str(prompts.PROFILE_PATH)}


@app.get("/api/config")
def get_config() -> dict:
    return config.as_dict()


@app.put("/api/config")
def put_config(request: ConfigRequest) -> dict:
    return config.update(request.model, request.temperature)


@app.websocket("/ws/pipeline/{run_id}")
async def pipeline_socket(websocket: WebSocket, run_id: str) -> None:
    """Live progress. Replays the buffer first, so a late connection misses nothing."""
    await websocket.accept()
    try:
        history = registry.events(run_id)
    except HTTPException:
        await websocket.send_json(
            {"type": "error", "message": f"Unknown run: {run_id}", "hint": ""}
        )
        await websocket.close()
        return

    queue = registry.subscribe(run_id)
    try:
        for event in history:
            await websocket.send_json(event)
            if event["type"] in TERMINAL_EVENTS:
                return
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event["type"] in TERMINAL_EVENTS:
                return
    except WebSocketDisconnect:
        pass
    finally:
        registry.unsubscribe(run_id, queue)


# --- Static frontend ----------------------------------------------------
# Declared last so it never shadows an /api route.

@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
