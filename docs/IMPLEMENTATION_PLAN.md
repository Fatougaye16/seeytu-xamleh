# Seeytu-Xamleh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Task 0 comes first and is not optional.** It creates the private repo, two milestones, five
> labels, and one GitHub issue per task. Every task after it is worked from its issue on its own
> branch, and closed by its final commit. Task N of this document is the full spec for issue
> "Task N: ..." — the checkboxes map 1:1.

**Goal:** Build a local-first, four-agent (Scout → Architect → Builder → Publisher) learning and
content-publishing pipeline over Ollama that turns one topic into seven markdown artifacts, driven
from a web UI with live token streaming and a CLI.

**Architecture:** A single blocking `call_model()` is the only code that talks to Ollama; everything
else is model-agnostic. A synchronous pipeline in `agents.py` chains four agents, each receiving all
prior outputs, emitting events through an injected callback so the CLI and the WebSocket share one
implementation. FastAPI runs the pipeline in a worker thread, buffers every event per run for
replay, and serves a vanilla-JS SPA from `static/`. Markdown files on disk are the only persistence,
written atomically only after all four agents succeed.

**Tech Stack:** Python 3.13, FastAPI, uvicorn, requests, Ollama 0.32.1 (cloud + local), vanilla
HTML/CSS/JS with vendored `marked`, `highlight.js`, and `DOMPurify`. `pytest` for tests.

## Global Constraints

Every task's requirements implicitly include this section.

- **Name**: full name is `Seeytu-Xamleh`, short form `Seeytu` where space is tight (browser tab, CLI
  prompt). Tagline: `Explore. Learn. Publish.` Both appear in the web header, tab title, CLI banner,
  README, and terminal output.
- **Runtime deps — exactly three**: `fastapi`, `uvicorn`, `requests`. `python-multipart` is **not**
  required (no endpoint accepts form data or uploads). `pytest` is a dev-only dependency.
- **Forbidden**: LangChain, CrewAI, or any agent framework. No React/npm/Node build step. No
  database. No Docker. No authentication.
- **`call_model()` is the single Ollama chokepoint.** No other function may issue an Ollama request.
  It is the designated swap point for Claude or Gemini later.
- **Model**: cloud-first (`gpt-oss:120b-cloud` default), auto-detected local fallback. Cloud and
  local share one code path via `http://localhost:11434`.
- **`options.num_ctx` must be set explicitly on every call** (default 16384). Ollama's default
  context window is small regardless of model capability and would silently truncate the Publisher's
  input. `MAX_TOKENS` maps to `num_predict` (output length) — a different knob.
- **Timeout is idle-based**: measured as time since the last streamed token (600s default), never
  total wall-clock.
- **All file writes pass `encoding="utf-8"`.** On Windows the default is the ANSI code page and the
  first em-dash or emoji raises `UnicodeEncodeError`.
- **Atomic runs**: files are written only after all four agents succeed. `output/` never contains a
  partial run.
- **Bind to `127.0.0.1`** only. Validate every user-supplied path segment against `OUTPUT_DIR`.
- **Dark mode is the default theme**, light mode a class toggle via CSS custom properties.

### The 14 settled decisions

| # | Decision | Resolution |
|---|---|---|
| 1 | Model strategy | Ollama Cloud first, local auto-detect fallback |
| 2 | Profile storage | Separate `profile.md`; the server never rewrites `prompts.py` |
| 3 | Streaming | Token-level over the WebSocket |
| 4 | Sequencing | Phase 1 = pipeline + CLI + web + **history**; Phase 2 = settings, ZIP, polish |
| 5 | Failure semantics | Atomic — any agent fails, the run fails; no partial folders |
| 6 | Failure recovery | Completed output held in memory; retry resumes **at the failed agent** |
| 7 | Cancel | Yes, from the UI, mid-run |
| 8 | Concurrency | Allowed, capped by `MAX_CONCURRENT_RUNS` (default 2); excess **queues** |
| 9 | Re-run | New timestamped folder `<slug>-<YYYYMMDD-HHMM>` |
| 10 | Writer backup | Saved, in Download All, **and** shown as a 7th tab |
| 11 | Profile egress | Full profile sent on the cloud path; README says so |
| 12 | Word counts | Targets, not gates; actual count displayed per piece |
| 13 | Hallucination | No-hedging prose **plus** a "Verify before publishing" block per agent |
| 14 | Misc | Vendor JS libs, auto-select a free port, sanitize rendered markdown |

---

## File Structure

```
seeytu-xamleh/
├── README.md            # setup + usage, both model modes, egress note
├── config.py            # all tunables, env overrides, free-port helper
├── prompts.py           # 4 system prompts + profile injection + user-prompt assembly
├── profile.md           # the editable profile body (decision #2)
├── textutil.py          # slugify, writer-output splitter, word count, markdown stripper
├── runstore.py          # run-id minting, path containment, atomic write, list/read/delete
├── agents.py            # call_model() + model resolution + run_agent + run_pipeline
├── server.py            # FastAPI app, RunRegistry (queue/cancel/replay), WebSocket
├── run.py               # entry point: banner, port selection, browser launch, CLI mode
├── static/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── vendor/          # pinned marked, highlight.js, DOMPurify + a highlight theme
├── tests/
│   ├── test_textutil.py
│   ├── test_runstore.py
│   ├── test_agents.py
│   └── test_server.py
└── output/              # generated runs, one timestamped folder each
```

**Two additions to the spec's layout, both deliberate.** `textutil.py` and `runstore.py` hold the
pure logic that carries almost all of the test suite — slugification, writer splitting, path
containment, atomic writes. Keeping them out of `agents.py` and `server.py` leaves those two files
focused on the pipeline and the HTTP surface respectively, and lets every fragile behavior be tested
without Ollama or a network. `templates/` from the spec is not needed: the frontend is static files.

---

# Task 0: Repository and issue tracker

Done before any implementation. Every later task is worked from its GitHub issue, so this task
creates the repo, the two milestones, the labels, and all 16 issues — and copies this plan into the
repo so each issue can point at its own task spec.

**Files:**
- Create: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `docs/IMPLEMENTATION_PLAN.md`
- Remote: `github.com/Fatougaye16/seeytu-xamleh` (**private**)

- [ ] **Step 1: Initialize the repository and directories**

```bash
cd c:/Users/FatouGaye/codes/seeytu-xamleh
git init
mkdir static static/vendor tests output docs
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
output/
.venv/
```

`output/` is ignored deliberately: generated runs are personal content, not source.

- [ ] **Step 3: Write the dependency files**

`requirements.txt`:
```
fastapi
uvicorn
requests
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest
httpx
```

`httpx` is required by FastAPI's `TestClient`, used from Task 8 onward.

- [ ] **Step 4: Copy this plan into the repo**

Save the full contents of this plan to `docs/IMPLEMENTATION_PLAN.md`. Every issue references it by
task number, so it must live in the repo rather than only in the planning directory.

- [ ] **Step 5: First commit and repo creation**

```bash
git add .gitignore requirements.txt requirements-dev.txt docs/IMPLEMENTATION_PLAN.md
git commit -m "chore: repository scaffold and implementation plan"
gh repo create Fatougaye16/seeytu-xamleh --private --source=. --push \
  --description "Seeytu-Xamleh — explore and teach. A local four-agent learning and publishing engine."
```

Verify: `gh repo view Fatougaye16/seeytu-xamleh --json visibility,name` reports `PRIVATE`.

- [ ] **Step 6: Create the milestones**

`gh` has no `milestone` subcommand — milestones go through the API.

```powershell
gh api repos/Fatougaye16/seeytu-xamleh/milestones -f title="Phase 1" `
  -f description="Working pipeline, CLI, web UI, and history"
gh api repos/Fatougaye16/seeytu-xamleh/milestones -f title="Phase 2" `
  -f description="Settings, ZIP, and polish"
```

- [ ] **Step 7: Create the labels**

```powershell
$labels = @(
  @{ name="engine";   color="1d76db"; desc="Model layer and agent pipeline" },
  @{ name="backend";  color="0e8a16"; desc="FastAPI endpoints and WebSocket" },
  @{ name="frontend"; color="d93f0b"; desc="Static HTML/CSS/JS" },
  @{ name="setup";    color="5319e7"; desc="Scaffolding and configuration" },
  @{ name="docs";     color="fbca04"; desc="Documentation" }
)
foreach ($l in $labels) {
  gh label create $l.name --color $l.color --description $l.desc --force
}
```

- [ ] **Step 8: Create all 16 issues**

```powershell
$issues = @(
  @{ n=1;  title="Configuration module";                 labels="setup";            phase=1
     summary="All tunables in config.py with env-var overrides, plus a free-port helper (port 8000 is frequently occupied)."
     accept="- NUM_CTX defaults to at least 16384`n- find_free_port skips an occupied port`n- update() clamps temperature to 0.0-1.0`n- tests/test_config.py passes" },
  @{ n=2;  title="Text utilities: slugify, writer splitting, word count"; labels="engine"; phase=1
     summary="Pure logic with no I/O: topic slugification, splitting the Publisher's single response into three pieces, and prose word counting."
     accept="- Slugify handles accents, emoji, empty input, over-long topics, and Windows reserved names`n- Splitter tolerates six heading variants and reports missing sections instead of writing empty files`n- Word count excludes code blocks and markdown syntax" },
  @{ n=3;  title="Run storage: path containment and atomic writes"; labels="backend"; phase=1
     summary="runstore.py owns the only persistence layer. Timestamped run ids, containment of every user-supplied path segment, and staged writes renamed into place."
     accept="- Traversal attempts raise UnsafePath (decision: this guards an endpoint that deletes)`n- write_run produces 7 files plus run.json, all UTF-8`n- No .partial folder survives a failure`n- list_runs is newest-first" },
  @{ n=4;  title="Agent prompts and profile";            labels="engine";           phase=1
     summary="Four system prompts with personas, exact section structures, explicit prohibitions, profile injection, and the shared Verify-before-publishing block."
     accept="- Every prompt injects profile.md and bans hedging`n- Publisher prompt names ## LINKEDIN / ## SUBSTACK / ## NOTION verbatim and states both word-count targets`n- Architect requires a 'connecting the dots' phase`n- Each agent receives exactly the prior outputs it should" },
  @{ n=5;  title="call_model() and model resolution";    labels="engine";           phase=1
     summary="The single Ollama chokepoint: streaming, explicit num_ctx, idle-based timeout, cloud/local resolution through one code path, and errors that carry the exact fix."
     accept="- options.num_ctx is set on every call (otherwise the Publisher's context silently truncates)`n- Read timeout is idle-based, not wall-clock`n- keep_alive is sent for local models only`n- Ollama down / model missing / signed out each produce an actionable hint`n- Cancellation stops mid-stream" },
  @{ n=6;  title="Pipeline: events, atomicity, cancel, retry"; labels="engine";     phase=1
     summary="Chains the four agents, feeds all prior outputs forward, emits events through an injected callback, and writes only on full success."
     accept="- Agents run scout -> architect -> builder -> publisher`n- A failure writes nothing and reports completed agents so retry can resume there`n- Passing prior outputs skips those agents`n- Missing writer sections are reported and the combined backup is always kept" },
  @{ n=7;  title="CLI mode and entry point";             labels="setup";            phase=1
     summary="run.py: banner, free-port selection, browser launch after the server is up, and full CLI mode sharing the same pipeline and event contract."
     accept="- Banner shows both names, the tagline, and the resolved model plus mode`n- --cli --agent research --topic works`n- Errors print the hint`n- End-of-run summary lists files and next steps" },
  @{ n=8;  title="FastAPI server: endpoints, registry, WebSocket replay"; labels="backend"; phase=1
     summary="All 13 documented endpoints plus cancel/retry/state, a run registry with a concurrency semaphore and queue, and a replayable per-run event buffer."
     accept="- A WebSocket connecting AFTER the run started still receives every event`n- Path traversal rejected on both run-scoped endpoints`n- Blank topic returns 422`n- Third concurrent run queues (cap of 2)`n- Profile writes go to profile.md, never to prompts.py" },
  @{ n=9;  title="Frontend shell: vendored libs, theme tokens, page structure"; labels="frontend"; phase=1
     summary="index.html and style.css. Dark by default with light as a token override, and marked/DOMPurify/highlight.js vendored locally rather than loaded from CDN."
     accept="- Header reads Seeytu-Xamleh with the tagline; tab title reads Seeytu`n- All four vendor files serve locally with no external requests`n- Tablet width collapses the sidebar without overflow" },
  @{ n=10; title="Frontend logic: streaming, tabs, history"; labels="frontend";     phase=1
     summary="app.js: WebSocket handling with token streaming, the agent progress tracker, 7 result tabs with word counts, copy/download, and the history sidebar."
     accept="- Tokens appear while an agent is still generating`n- Mid-run refresh recovers full progress via buffer replay`n- 7 tabs, each showing a word count`n- Copy shows a Copied! toast`n- History shows real topic text, not the slug`n- Rendered markdown is sanitized" },
  @{ n=11; title="README";                               labels="docs";             phase=1
     summary="Quickstart under five minutes, both model modes side by side, and the cloud data-egress note."
     accept="- pip install then python run.py reaches a working page in under 5 minutes`n- Cloud vs local table with setup, speed, and trade-offs`n- Egress warning states that profile.md is transmitted in cloud mode`n- Explains atomic runs, retry, and the verify block" },
  @{ n=12; title="Settings panel";                       labels="frontend";         phase=2
     summary="Slide-over panel: model dropdown grouped cloud/local, temperature slider, profile editor, theme toggle."
     accept="- Changing the model is reflected in the next run's run.json`n- Profile edits change the next run's output`n- Panel names profile.md as the file being written" },
  @{ n=13; title="Download All as ZIP";                  labels="backend";          phase=2
     summary="GET /api/runs/{run_id}/archive streaming an in-memory ZIP of all 7 markdown files plus run.json, reusing safe_run_dir for containment."
     accept="- Archive contains 8 files including 04-writer-combined.md`n- No new path-validation logic" },
  @{ n=14; title="LinkedIn plain-text copy";             labels="frontend";         phase=2
     summary="A Copy-for-LinkedIn button on the LinkedIn tab that copies strip_markdown() output rather than raw markdown."
     accept="- Pasted output contains no #, **, or backticks`n- Reuses the tested strip_markdown from Task 2" },
  @{ n=15; title="Retry, queue, and cancel UI";          labels="frontend";         phase=2
     summary="Surface what the backend already supports: retry-from-failed-agent, a queued badge, and a re-run button per history entry."
     accept="- Stopping Ollama mid-run then retrying re-runs only the remaining agents`n- Re-run creates a new timestamped folder, leaving the original intact" },
  @{ n=16; title="Final polish";                         labels="frontend";         phase=2
     summary="Keyboard shortcuts, empty and error states, focus-visible outlines, aria-live on progress, print stylesheet, light-mode parity."
     accept="- Whole app is keyboard navigable`n- Both themes verified at 768px and 1440px" }
)

foreach ($i in $issues) {
  $body = @"
Implements **Task $($i.n)** of ``docs/IMPLEMENTATION_PLAN.md``.

$($i.summary)

## Acceptance criteria
$($i.accept)

## Where the details are
Task $($i.n) of ``docs/IMPLEMENTATION_PLAN.md`` carries the exact files, interfaces (consumed and
produced signatures), failing-test code, implementation code, and verification commands. Follow it
step by step — the checkboxes there map 1:1 to the work in this issue.
"@
  gh issue create --title "Task $($i.n): $($i.title)" --body $body `
    --label $i.labels --milestone "Phase $($i.phase)"
}
```

- [ ] **Step 9: Verify the tracker**

```bash
gh issue list --limit 20
gh api repos/Fatougaye16/seeytu-xamleh/milestones --jq '.[] | "\(.title): \(.open_issues) open"'
```

Expected: 16 issues, 11 on Phase 1 and 5 on Phase 2.

**From here on, work one issue at a time.** Start each task with
`gh issue develop <number> --checkout` (or a branch named `task-<n>-<slug>`), reference the issue in
each commit (`refs #<n>`), and close it with the final commit (`closes #<n>`).

---

# Phase 1 — Working pipeline, CLI, web UI, and history

## Task 1: Configuration

**Files:**
- Create: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (first implementation task; scaffolding comes from Task 0).
- Produces: `config.MODEL_NAME: str`, `config.FALLBACK_MODEL: str`, `config.OLLAMA_URL: str`,
  `config.OLLAMA_API_KEY: str | None`, `config.TEMPERATURE: float`, `config.MAX_TOKENS: int`,
  `config.NUM_CTX: int`, `config.AGENT_IDLE_TIMEOUT: int`, `config.CONNECT_TIMEOUT: int`,
  `config.KEEP_ALIVE: str`, `config.OUTPUT_DIR: pathlib.Path`, `config.PORT: int`,
  `config.MAX_CONCURRENT_RUNS: int`, `config.APP_NAME: str`, `config.APP_SHORT_NAME: str`,
  `config.TAGLINE: str`, `config.find_free_port(start: int) -> int`,
  `config.as_dict() -> dict`, `config.update(model: str | None, temperature: float | None) -> dict`.

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import socket
import config


def test_defaults_are_sane():
    assert config.APP_NAME == "Seeytu-Xamleh"
    assert config.APP_SHORT_NAME == "Seeytu"
    assert config.NUM_CTX >= 16384, "num_ctx must be large enough for the Publisher's input"
    assert config.MAX_TOKENS == 4096
    assert config.OLLAMA_URL == "http://localhost:11434"
    assert config.MAX_CONCURRENT_RUNS >= 1


def test_find_free_port_skips_occupied_port():
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        occupied = taken.getsockname()[1]
        found = config.find_free_port(occupied)
        assert found != occupied
        assert found > occupied


def test_update_clamps_temperature():
    original = config.TEMPERATURE
    try:
        assert config.update(None, 5.0)["temperature"] == 1.0
        assert config.update(None, -3.0)["temperature"] == 0.0
        assert config.update("some-model", 0.4) == {
            "model": "some-model",
            "temperature": 0.4,
        }
    finally:
        config.update(None, original)


def test_as_dict_reports_current_values():
    snapshot = config.as_dict()
    assert set(snapshot) >= {"model", "temperature", "num_ctx", "max_tokens", "output_dir"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Write `config.py`**

```python
"""All tunables for Seeytu-Xamleh, in one place.

Every value can be overridden by an environment variable of the same name, so
changing a port or a model never requires editing source.
"""

import os
import socket
from pathlib import Path

APP_NAME = "Seeytu-Xamleh"
APP_SHORT_NAME = "Seeytu"
TAGLINE = "Explore. Learn. Publish."

# --- Model ---------------------------------------------------------------
# Cloud-first. Cloud models are served through the *local* daemon, so the URL
# is the same in both modes and only the model name differs.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-oss:120b-cloud")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "llama3.1:8b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# Only needed when calling a cloud model without `ollama signin`.
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY") or None

TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
# Maps to Ollama's num_predict: the maximum *output* length.
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
# Maps to Ollama's num_ctx: the context window. MUST be set explicitly — the
# Ollama default is small regardless of what the model supports, and the
# Publisher's input (topic + three prior outputs) runs 6k-12k tokens. Left at
# the default, the earliest content is silently dropped with no error.
NUM_CTX = int(os.getenv("NUM_CTX", "16384"))

# Seconds of silence — time since the last streamed token — before giving up.
# Never a total wall-clock limit: a correct local generation can legitimately
# run for 20 minutes.
AGENT_IDLE_TIMEOUT = int(os.getenv("AGENT_IDLE_TIMEOUT", "600"))
CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "10"))
# Keeps a local model resident between agents so it is not reloaded four times.
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "15m")

# --- Storage and server --------------------------------------------------
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output")).resolve()
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "127.0.0.1")
MAX_CONCURRENT_RUNS = int(os.getenv("MAX_CONCURRENT_RUNS", "2"))


def find_free_port(start: int = PORT, attempts: int = 20) -> int:
    """Return the first bindable port at or after `start`.

    Port 8000 is frequently already taken; failing with a traceback for that
    would be a poor first-run experience.
    """
    for candidate in range(start, start + attempts):
        with socket.socket() as probe:
            try:
                probe.bind((HOST, candidate))
                return candidate
            except OSError:
                continue
    raise RuntimeError(f"No free port in range {start}-{start + attempts - 1}")


def as_dict() -> dict:
    """Current mutable config, for GET /api/config."""
    return {
        "model": MODEL_NAME,
        "temperature": TEMPERATURE,
        "num_ctx": NUM_CTX,
        "max_tokens": MAX_TOKENS,
        "output_dir": str(OUTPUT_DIR),
        "max_concurrent_runs": MAX_CONCURRENT_RUNS,
    }


def update(model: str | None = None, temperature: float | None = None) -> dict:
    """Mutate runtime config, for PUT /api/config. Process-lifetime only."""
    global MODEL_NAME, TEMPERATURE
    if model:
        MODEL_NAME = model
    if temperature is not None:
        TEMPERATURE = min(1.0, max(0.0, float(temperature)))
    return {"model": MODEL_NAME, "temperature": TEMPERATURE}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

Commits reference their issue; the last commit of a task closes it. Every later task follows this
pattern — only the message and paths change.

```bash
git add config.py tests/test_config.py
git commit -m "feat: configuration module with env overrides and free-port helper

closes #1"
```

---

## Task 2: Pure text utilities — slugify, writer splitting, word count

This task front-loads the most failure-prone logic in the project, and it is fully testable without
Ollama. The writer splitter in particular must survive whatever heading style a model emits.

**Files:**
- Create: `textutil.py`
- Test: `tests/test_textutil.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `textutil.slugify(topic: str, max_len: int = 60) -> str`,
  `textutil.split_writer_output(text: str) -> tuple[dict[str, str], list[str]]` returning
  `({"linkedin": str, "substack": str, "notion": str}, missing_keys)` where present keys map to
  content and `missing_keys` lists the ones that failed to parse,
  `textutil.word_count(markdown: str) -> int`,
  `textutil.strip_markdown(markdown: str) -> str`.

- [ ] **Step 1: Write the failing test**

`tests/test_textutil.py`:
```python
import pytest

from textutil import slugify, split_writer_output, strip_markdown, word_count


@pytest.mark.parametrize(
    "topic,expected",
    [
        ("Vector databases for AI applications", "vector-databases-for-ai-applications"),
        ("How Kafka powers real-time fintech!", "how-kafka-powers-real-time-fintech"),
        ("  spaced   out  ", "spaced-out"),
        ("Ollama's API — a deep dive", "ollamas-api-a-deep-dive"),
        ("Café résumé naïve", "cafe-resume-naive"),
        ("🚀 rockets 🚀", "rockets"),
        ("C++ vs C#", "c-vs-c"),
    ],
)
def test_slugify_normal_cases(topic, expected):
    assert slugify(topic) == expected


def test_slugify_handles_empty_and_symbol_only_input():
    assert slugify("") == "topic"
    assert slugify("!!!???") == "topic"
    assert slugify("   ") == "topic"


def test_slugify_avoids_windows_reserved_names():
    # CON, PRN, AUX, NUL and COM1-9 / LPT1-9 cannot be directory names on Windows.
    assert slugify("CON") == "topic-con"
    assert slugify("nul") == "topic-nul"
    assert slugify("com1") == "topic-com1"


def test_slugify_truncates_without_trailing_hyphen():
    slug = slugify("word " * 100, max_len=30)
    assert len(slug) <= 30
    assert not slug.endswith("-")


def test_split_writer_output_canonical_headers():
    text = """## LINKEDIN
Linked content here.

## SUBSTACK
Substack content here.

## NOTION
Notion content here.
"""
    sections, missing = split_writer_output(text)
    assert missing == []
    assert sections["linkedin"] == "Linked content here."
    assert sections["substack"] == "Substack content here."
    assert sections["notion"] == "Notion content here."


@pytest.mark.parametrize(
    "header",
    [
        "## LINKEDIN",
        "### LinkedIn Post",
        "# linkedin post",
        "**LINKEDIN**",
        "## LinkedIn ##",
        "## Linked In",
    ],
)
def test_split_writer_output_tolerates_heading_variants(header):
    text = f"{header}\nbody\n\n## SUBSTACK\ns\n\n## NOTION\nn\n"
    sections, missing = split_writer_output(text)
    assert missing == []
    assert sections["linkedin"] == "body"


def test_split_writer_output_ignores_preamble():
    text = "Sure! Here are your three pieces.\n\n## LINKEDIN\na\n\n## SUBSTACK\nb\n\n## NOTION\nc\n"
    sections, _ = split_writer_output(text)
    assert sections["linkedin"] == "a"


def test_split_writer_output_reports_missing_sections():
    sections, missing = split_writer_output("## LINKEDIN\nonly this one\n")
    assert sections["linkedin"] == "only this one"
    assert sorted(missing) == ["notion", "substack"]
    assert "substack" not in sections


def test_split_writer_output_on_garbage_reports_all_missing():
    sections, missing = split_writer_output("The model rambled and produced no headers at all.")
    assert sections == {}
    assert sorted(missing) == ["linkedin", "notion", "substack"]


def test_split_writer_output_keeps_inner_headings_with_their_section():
    text = "## NOTION\n# TL;DR\nquick\n## Core concepts\nmore\n"
    sections, missing = split_writer_output(text)
    assert missing == ["linkedin", "substack"]
    assert "# TL;DR" in sections["notion"]
    assert "## Core concepts" in sections["notion"]


def test_word_count_excludes_markup_and_code_blocks():
    md = """# Heading Here

Three real words.

```python
this = "code should not count"
```

- bullet one
"""
    # "Heading Here" (2) + "Three real words." (3) + "bullet one" (2)
    assert word_count(md) == 7


def test_strip_markdown_produces_plain_text():
    md = "## Title\n\n**Bold** and _italic_ and `code` and [link](http://x.dev).\n\n- item\n"
    plain = strip_markdown(md)
    assert "#" not in plain
    assert "**" not in plain
    assert "`" not in plain
    assert "Bold and italic and code and link." in plain
    assert "item" in plain
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_textutil.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'textutil'`

- [ ] **Step 3: Write `textutil.py`**

```python
"""Pure text helpers. No I/O, no network — every branch is unit-testable."""

import re
import unicodedata

# Directory names Windows refuses, regardless of extension.
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

# Section keys the Publisher must produce, with the aliases models actually emit.
_SECTION_ALIASES = {
    "linkedin": {"linkedin", "linkedinpost", "linkedin post", "linked in", "linkedinupdate"},
    "substack": {"substack", "substackarticle", "substack article", "substackpost", "newsletter"},
    "notion": {"notion", "notionreference", "notion reference", "notionreferencedoc",
               "notiondoc", "reference", "referencedoc"},
}

_ATX_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*(?P<text>.+?)\s*#*\s*$")
_BOLD_ONLY_LINE = re.compile(r"^\s{0,3}\*\*(?P<text>[^*]+)\*\*:?\s*$")
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")


def slugify(topic: str, max_len: int = 60) -> str:
    """Turn a topic into a filesystem-safe directory name.

    Handles accents, emoji, punctuation, over-long input, and the Windows
    reserved device names that cannot be directories.
    """
    decomposed = unicodedata.normalize("NFKD", topic)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    slug = re.sub(r"-{2,}", "-", slug)
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    if not slug:
        return "topic"
    if slug in _WINDOWS_RESERVED:
        return f"topic-{slug}"
    return slug


def _normalize_heading(text: str) -> str:
    """Reduce a heading to comparable form: lowercase alphanumerics and spaces."""
    cleaned = re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def _match_section(heading: str) -> str | None:
    normalized = _normalize_heading(heading)
    collapsed = normalized.replace(" ", "")
    for key, aliases in _SECTION_ALIASES.items():
        if normalized in aliases or collapsed in aliases:
            return key
    return None


def split_writer_output(text: str) -> tuple[dict[str, str], list[str]]:
    """Split the Publisher's single response into its three pieces.

    Returns (sections, missing). Only successfully parsed keys appear in
    `sections`; everything else is listed in `missing` so the caller can report
    the failure instead of silently writing empty files. Headings inside a
    section (a Notion doc's own "# TL;DR") stay with their section — only
    headings that name one of the three targets act as boundaries.
    """
    boundaries: list[tuple[int, str]] = []
    in_fence = False
    lines = text.splitlines()

    for index, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _ATX_HEADING.match(line) or _BOLD_ONLY_LINE.match(line)
        if not match:
            continue
        key = _match_section(match.group("text"))
        if key and key not in (existing for _, existing in boundaries):
            boundaries.append((index, key))

    sections: dict[str, str] = {}
    for position, (start, key) in enumerate(boundaries):
        end = boundaries[position + 1][0] if position + 1 < len(boundaries) else len(lines)
        body = "\n".join(lines[start + 1:end]).strip()
        if body:
            sections[key] = body

    missing = sorted(set(_SECTION_ALIASES) - set(sections))
    return sections, missing


def _visible_text(markdown: str) -> str:
    """Strip fenced code and markdown syntax, leaving prose."""
    without_code = re.sub(r"```.*?```|~~~.*?~~~", " ", markdown, flags=re.S)
    without_code = re.sub(r"`([^`]*)`", r"\1", without_code)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", without_code)   # links and images
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)        # heading markers
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.M)             # blockquotes
    text = re.sub(r"^\s{0,3}([-*+]|\d+\.)\s+", "", text, flags=re.M)  # list markers
    text = re.sub(r"(\*\*|__|\*|_|~~)", "", text)                    # emphasis
    return text


def word_count(markdown: str) -> int:
    """Count prose words, ignoring code blocks and markdown syntax."""
    return len(_visible_text(markdown).split())


def strip_markdown(markdown: str) -> str:
    """Plain text suitable for pasting straight into LinkedIn."""
    text = _visible_text(markdown)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_textutil.py -v`
Expected: all passed (25 cases including parametrized variants)

- [ ] **Step 5: Commit**

```bash
git add textutil.py tests/test_textutil.py
git commit -m "feat: slugify, writer-output splitting, and word counting"
```

---

## Task 3: Run storage — path containment and atomic writes

**Files:**
- Create: `runstore.py`
- Test: `tests/test_runstore.py`

**Interfaces:**
- Consumes: `config.OUTPUT_DIR`, `textutil.slugify`.
- Produces: `runstore.FILE_ORDER: list[tuple[str, str]]` as ordered `(key, filename)` pairs,
  `runstore.mint_run_id(topic: str, now: datetime) -> str`,
  `runstore.safe_run_dir(run_id: str) -> Path`,
  `runstore.safe_run_file(run_id: str, filename: str) -> Path`,
  `runstore.write_run(run_id: str, topic: str, outputs: dict[str, str], meta: dict) -> list[str]`,
  `runstore.list_runs() -> list[dict]`, `runstore.read_run(run_id: str) -> dict`,
  `runstore.delete_run(run_id: str) -> None`, and `runstore.UnsafePath(ValueError)`.

- [ ] **Step 1: Write the failing test**

`tests/test_runstore.py`:
```python
from datetime import datetime

import pytest

import config
import runstore


@pytest.fixture(autouse=True)
def isolated_output(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(runstore, "OUTPUT_DIR", tmp_path / "output", raising=False)
    yield


def _outputs():
    return {
        "research": "# Research\nbody",
        "learning": "# Learning\nbody",
        "project": "# Project\nbody",
        "linkedin": "post",
        "substack": "article",
        "notion": "reference",
        "combined": "raw writer response",
    }


def test_mint_run_id_is_slug_plus_timestamp():
    when = datetime(2026, 8, 9, 14, 5)
    assert runstore.mint_run_id("Vector databases for AI", when) == (
        "vector-databases-for-ai-20260809-1405"
    )


def test_mint_run_id_disambiguates_collisions():
    when = datetime(2026, 8, 9, 14, 5)
    first = runstore.mint_run_id("Same topic", when)
    runstore.write_run(first, "Same topic", _outputs(), {"model": "m"})
    second = runstore.mint_run_id("Same topic", when)
    assert second != first
    assert second.endswith("-2")


def test_write_run_creates_seven_files_and_metadata():
    written = runstore.write_run("demo-20260809-1405", "Demo", _outputs(), {"model": "m"})
    assert len(written) == 7
    directory = runstore.safe_run_dir("demo-20260809-1405")
    assert (directory / "01-research-brief.md").read_text(encoding="utf-8") == "# Research\nbody"
    assert (directory / "04-writer-combined.md").exists()
    assert (directory / "run.json").exists()


def test_write_run_survives_non_ascii_content():
    outputs = _outputs() | {"research": "em—dash, curly ’quote’, emoji 🚀"}
    runstore.write_run("uni-20260809-1405", "Unicode", outputs, {"model": "m"})
    body = (runstore.safe_run_dir("uni-20260809-1405") / "01-research-brief.md").read_text(
        encoding="utf-8"
    )
    assert "🚀" in body


def test_read_run_reports_topic_and_files():
    runstore.write_run("demo-20260809-1405", "Demo Topic", _outputs(), {"model": "m"})
    run = runstore.read_run("demo-20260809-1405")
    assert run["topic"] == "Demo Topic"
    assert run["model"] == "m"
    assert [entry["key"] for entry in run["files"]][0] == "research"
    assert run["files"][0]["word_count"] > 0


def test_list_runs_is_newest_first():
    for run_id in ("a-20260101-0900", "b-20260808-0900", "c-20260809-0900"):
        runstore.write_run(run_id, run_id, _outputs(), {"model": "m"})
    assert [run["run_id"] for run in runstore.list_runs()] == [
        "c-20260809-0900",
        "b-20260808-0900",
        "a-20260101-0900",
    ]


def test_delete_run_removes_the_folder():
    runstore.write_run("gone-20260809-1405", "Gone", _outputs(), {"model": "m"})
    runstore.delete_run("gone-20260809-1405")
    assert not runstore.safe_run_dir("gone-20260809-1405").exists()


@pytest.mark.parametrize(
    "run_id",
    ["../secrets", "..", "a/../../b", "C:/Windows", "sub/dir", "a\\b", ""],
)
def test_safe_run_dir_rejects_traversal(run_id):
    with pytest.raises(runstore.UnsafePath):
        runstore.safe_run_dir(run_id)


@pytest.mark.parametrize("filename", ["../../config.py", "..", "sub/file.md", "a\\b.md", ""])
def test_safe_run_file_rejects_traversal(filename):
    with pytest.raises(runstore.UnsafePath):
        runstore.safe_run_file("demo-20260809-1405", filename)


def test_safe_run_file_rejects_unknown_filenames():
    with pytest.raises(runstore.UnsafePath):
        runstore.safe_run_file("demo-20260809-1405", "arbitrary.md")


def test_delete_run_rejects_traversal():
    with pytest.raises(runstore.UnsafePath):
        runstore.delete_run("../..")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_runstore.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'runstore'`

- [ ] **Step 3: Write `runstore.py`**

```python
"""Markdown files on disk are the only persistence. This module owns that.

Two responsibilities that must not be gotten wrong: containing every
user-supplied path segment inside OUTPUT_DIR, and writing a run atomically so
`output/` never holds a partial run.
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import config
from textutil import slugify, word_count

# Ordered (key, filename). Order drives both the tab order in the UI and the
# `files` array in run.json. The combined writer response is a first-class
# artifact: saved, zipped, and shown as the 7th tab.
FILE_ORDER: list[tuple[str, str]] = [
    ("research", "01-research-brief.md"),
    ("learning", "02-learning-path.md"),
    ("project", "03-project-spec.md"),
    ("linkedin", "04-linkedin-post.md"),
    ("substack", "04-substack-article.md"),
    ("notion", "04-notion-reference.md"),
    ("combined", "04-writer-combined.md"),
]

FILENAME_BY_KEY = dict(FILE_ORDER)
KEY_BY_FILENAME = {filename: key for key, filename in FILE_ORDER}

TAB_LABELS = {
    "research": "Research Brief",
    "learning": "Learning Path",
    "project": "Project Spec",
    "linkedin": "LinkedIn Post",
    "substack": "Substack Article",
    "notion": "Notion Reference",
    "combined": "Raw Writer Output",
}

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9\-]{0,119}$")


class UnsafePath(ValueError):
    """Raised when a run id or filename escapes OUTPUT_DIR or is unrecognized."""


def _output_root() -> Path:
    return Path(config.OUTPUT_DIR)


def safe_run_dir(run_id: str) -> Path:
    """Resolve a run directory, refusing anything outside OUTPUT_DIR.

    Two independent gates: a strict pattern on the id, then a resolved-path
    containment check. Either alone would probably do; both is cheap, and this
    guards an endpoint that deletes.
    """
    if not isinstance(run_id, str) or not _RUN_ID.match(run_id):
        raise UnsafePath(f"Invalid run id: {run_id!r}")
    root = _output_root().resolve()
    candidate = (root / run_id).resolve()
    if candidate != root and root not in candidate.parents:
        raise UnsafePath(f"Run id escapes the output directory: {run_id!r}")
    return candidate


def safe_run_file(run_id: str, filename: str) -> Path:
    """Resolve one file inside a run. Only known filenames are permitted."""
    if filename not in KEY_BY_FILENAME and filename != "run.json":
        raise UnsafePath(f"Unknown output file: {filename!r}")
    directory = safe_run_dir(run_id)
    candidate = (directory / filename).resolve()
    if candidate.parent != directory:
        raise UnsafePath(f"Filename escapes the run directory: {filename!r}")
    return candidate


def mint_run_id(topic: str, now: datetime | None = None) -> str:
    """`<slug>-<YYYYMMDD-HHMM>`, suffixed if that directory already exists.

    Timestamped rather than date-only so re-running a topic preserves the
    previous output instead of overwriting it.
    """
    now = now or datetime.now()
    base = f"{slugify(topic)}-{now:%Y%m%d-%H%M}"
    candidate, suffix = base, 1
    while (_output_root() / candidate).exists():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def write_run(run_id: str, topic: str, outputs: dict[str, str], meta: dict) -> list[str]:
    """Write all seven artifacts plus run.json. Call only after every agent succeeded.

    Writes to a temporary sibling directory and renames it into place, so an
    interrupted write never leaves a half-populated run folder behind.
    """
    final = safe_run_dir(run_id)
    staging = final.with_name(final.name + ".partial")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    written: list[str] = []
    for key, filename in FILE_ORDER:
        content = outputs.get(key)
        if content is None:
            continue
        (staging / filename).write_text(content, encoding="utf-8")
        written.append(filename)

    record = {
        "run_id": run_id,
        "topic": topic,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "files": written,
        **meta,
    }
    (staging / "run.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if final.exists():
        shutil.rmtree(final)
    staging.rename(final)
    return written


def read_run(run_id: str) -> dict:
    """Full run detail: metadata plus every file's content and word count."""
    directory = safe_run_dir(run_id)
    if not directory.is_dir():
        raise FileNotFoundError(run_id)

    metadata = {}
    record = directory / "run.json"
    if record.is_file():
        metadata = json.loads(record.read_text(encoding="utf-8"))

    files = []
    for key, filename in FILE_ORDER:
        path = directory / filename
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        files.append({
            "key": key,
            "label": TAB_LABELS[key],
            "filename": filename,
            "content": content,
            "word_count": word_count(content),
        })

    return {
        "run_id": run_id,
        "topic": metadata.get("topic", run_id),
        "created_at": metadata.get("created_at"),
        "model": metadata.get("model"),
        "mode": metadata.get("mode"),
        "temperature": metadata.get("temperature"),
        "missing_sections": metadata.get("missing_sections", []),
        "files": files,
    }


def list_runs() -> list[dict]:
    """Every past run, newest first. Skips staging directories."""
    root = _output_root()
    if not root.is_dir():
        return []

    runs = []
    for directory in root.iterdir():
        if not directory.is_dir() or directory.name.endswith(".partial"):
            continue
        metadata = {}
        record = directory / "run.json"
        if record.is_file():
            try:
                metadata = json.loads(record.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                metadata = {}
        runs.append({
            "run_id": directory.name,
            "topic": metadata.get("topic", directory.name),
            "created_at": metadata.get("created_at"),
            "model": metadata.get("model"),
            "mode": metadata.get("mode"),
            "file_count": len(list(directory.glob("*.md"))),
        })

    runs.sort(key=lambda run: (run["created_at"] or "", run["run_id"]), reverse=True)
    return runs


def delete_run(run_id: str) -> None:
    directory = safe_run_dir(run_id)
    if directory == _output_root().resolve():
        raise UnsafePath("Refusing to delete the output root")
    if directory.is_dir():
        shutil.rmtree(directory)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_runstore.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add runstore.py tests/test_runstore.py
git commit -m "feat: run storage with path containment and atomic writes"
```

---

## Task 4: Profile and agent prompts

The prompts are the product. Each one states a persona, dictates exact structure, forbids
hand-waving, injects the profile, and — per decision #13 — ends with a "Verify before publishing"
block so the prose can stay confident while uncertainty stays visible.

**Files:**
- Create: `prompts.py`, `profile.md`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Consumes: nothing (reads its own `profile.md`).
- Produces: `prompts.AGENTS: list[str]` = `["scout", "architect", "builder", "publisher"]`,
  `prompts.AGENT_META: dict[str, dict]` with `emoji`, `name`, `activity`, `output_key`,
  `prompts.AGENT_ALIASES: dict[str, str]` mapping the CLI/API agent names to internal keys,
  `prompts.PROFILE_PATH: Path`, `prompts.load_profile() -> str`,
  `prompts.save_profile(text: str) -> None`, `prompts.system_prompt(agent: str) -> str`,
  `prompts.user_prompt(agent: str, topic: str, prior: dict[str, str]) -> str`.

`AGENT_ALIASES` lives here rather than in `run.py` on purpose: both `run.py` and `server.py` need it,
and `run.py` imports `server`, so putting it in `run.py` would make `server.py` import `run` right
back — which loads a second copy of the module when `run.py` executes as `__main__`.

- [ ] **Step 1: Write `profile.md`**

```markdown
<!-- EDIT THIS FILE. Every agent receives it verbatim, so the more specific you
     are, the more the output sounds like you and not like a generic AI.
     Cloud mode transmits this file to Ollama's servers on every agent call —
     keep out anything you would not send to a third party. -->

## Who I am

I work in technology and I am drawn to how tech intersects with other domains —
healthcare, finance, education, logistics. I care about how things work in the
real world, not just in theory.

## How I learn

Hands-on projects. Building something is what makes a concept stick. I want
real tools, real docs, and real commands, not summaries of summaries.

## Where I publish

- LinkedIn — short, punchy posts about what I am learning
- Substack — longer essays that connect ideas across domains
- Notion — structured reference notes I come back to months later

## My writing voice

Direct, clear, no fluff. Short paragraphs. Concrete over abstract. I like
connecting ideas across domains and I never open with "I just learned...".
```

- [ ] **Step 2: Write the failing test**

`tests/test_prompts.py`:
```python
import pytest

import prompts


def test_agents_are_in_pipeline_order():
    assert prompts.AGENTS == ["scout", "architect", "builder", "publisher"]


def test_agent_meta_is_complete():
    for agent in prompts.AGENTS:
        meta = prompts.AGENT_META[agent]
        assert meta["emoji"] and meta["name"] and meta["activity"]
    assert prompts.AGENT_META["scout"]["name"] == "The Scout"
    assert prompts.AGENT_META["publisher"]["name"] == "The Publisher"


def test_agent_aliases_cover_the_documented_cli_names():
    # The names the spec's CLI examples use, mapped to internal agent keys.
    assert prompts.AGENT_ALIASES["research"] == "scout"
    assert prompts.AGENT_ALIASES["curriculum"] == "architect"
    assert prompts.AGENT_ALIASES["project"] == "builder"
    assert prompts.AGENT_ALIASES["writer"] == "publisher"
    # Internal keys must also resolve to themselves.
    for agent in prompts.AGENTS:
        assert prompts.AGENT_ALIASES[agent] == agent


def test_every_system_prompt_injects_the_profile():
    marker = "How I learn"
    for agent in prompts.AGENTS:
        assert marker in prompts.system_prompt(agent)


def test_every_system_prompt_has_a_persona_and_bans_hedging():
    for agent in prompts.AGENTS:
        text = prompts.system_prompt(agent).lower()
        assert "you are" in text
        assert "do not" in text
        assert "verify before publishing" in text


def test_publisher_prompt_names_all_three_section_headers():
    text = prompts.system_prompt("publisher")
    assert "## LINKEDIN" in text
    assert "## SUBSTACK" in text
    assert "## NOTION" in text


def test_publisher_prompt_states_the_word_count_targets():
    text = prompts.system_prompt("publisher")
    assert "150" in text and "300" in text
    assert "800" in text and "1500" in text


def test_architect_prompt_requires_a_connecting_the_dots_phase():
    assert "connecting the dots" in prompts.system_prompt("architect").lower()


def test_scout_user_prompt_contains_only_the_topic():
    text = prompts.user_prompt("scout", "vector databases", {})
    assert "vector databases" in text
    assert "RESEARCH BRIEF" not in text


def test_later_agents_receive_all_prior_outputs():
    prior = {"research": "R-CONTENT", "learning": "L-CONTENT", "project": "P-CONTENT"}
    architect = prompts.user_prompt("architect", "topic", prior)
    assert "R-CONTENT" in architect
    assert "L-CONTENT" not in architect  # the Architect has not seen the path yet

    builder = prompts.user_prompt("builder", "topic", prior)
    assert "R-CONTENT" in builder and "L-CONTENT" in builder
    assert "P-CONTENT" not in builder

    publisher = prompts.user_prompt("publisher", "topic", prior)
    assert all(marker in publisher for marker in ("R-CONTENT", "L-CONTENT", "P-CONTENT"))


def test_user_prompt_rejects_unknown_agent():
    with pytest.raises(KeyError):
        prompts.user_prompt("nobody", "topic", {})


def test_profile_round_trips(tmp_path, monkeypatch):
    path = tmp_path / "profile.md"
    monkeypatch.setattr(prompts, "PROFILE_PATH", path)
    prompts.save_profile("## Who I am\nem—dash and emoji 🚀\n")
    assert "🚀" in prompts.load_profile()


def test_load_profile_falls_back_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(prompts, "PROFILE_PATH", tmp_path / "absent.md")
    assert prompts.load_profile().strip() != ""
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prompts'`

- [ ] **Step 4: Write `prompts.py`**

Note the shared `_VERIFY_BLOCK` — appended to all four system prompts so decision #13 cannot drift
between agents.

```python
"""Agent prompts. This is where output quality lives — tune here.

To change *who the agents write for*, edit profile.md instead; it is injected
into every prompt below.
"""

from pathlib import Path

PROFILE_PATH = Path(__file__).with_name("profile.md")

_PROFILE_FALLBACK = (
    "## Who I am\nA practical technologist who learns by building and writes "
    "about it.\n\n## How I learn\nHands-on projects with real tools.\n"
)

AGENTS = ["scout", "architect", "builder", "publisher"]

# The agent names the CLI and API accept, mapped to internal keys. Defined here
# rather than in run.py because server.py needs it too, and run.py imports
# server — the reverse import would load a second copy of run as __main__.
AGENT_ALIASES = {
    "research": "scout",
    "scout": "scout",
    "curriculum": "architect",
    "architect": "architect",
    "project": "builder",
    "builder": "builder",
    "writer": "publisher",
    "publisher": "publisher",
}

AGENT_META = {
    "scout": {
        "emoji": "🔍",
        "name": "The Scout",
        "activity": "Mapping the topic landscape",
        "output_key": "research",
    },
    "architect": {
        "emoji": "📐",
        "name": "The Architect",
        "activity": "Designing the learning path",
        "output_key": "learning",
    },
    "builder": {
        "emoji": "🔨",
        "name": "The Builder",
        "activity": "Specifying the capstone project",
        "output_key": "project",
    },
    "publisher": {
        "emoji": "✍️",
        "name": "The Publisher",
        "activity": "Drafting the content",
        "output_key": "combined",
    },
}

# Appended to every system prompt. The prose stays confident and unhedged; the
# uncertainty is quarantined in one block the reader checks and then deletes.
_VERIFY_BLOCK = """
End your response with this section, exactly once:

## Verify before publishing
- List the specific claims you are least certain about: version numbers,
  documentation URLs, company examples, dates, benchmark figures.
- One bullet per claim. Say what to check, not "verify everything".
- If you invented or approximated a specific, it belongs here.

This block is the only place uncertainty appears. Everywhere else, write with
conviction and no hedging.
"""

_SHARED_RULES = """
Rules that override any instinct to be agreeable:
- Name real companies, real tools, real versions, real documentation. Never
  "some companies" or "various tools".
- No hedging in the body: no "it depends", no "there are many approaches",
  no restating the question back.
- No filler openings. No "In today's fast-paced world". No "Great question".
- Prefer a concrete example over a general statement, every time.
- Use markdown headings exactly as specified below. Do not invent extra
  top-level sections.
"""

_SCOUT = """You are a research analyst who briefs sharp, busy practitioners. You
explain hard things in plain language without dumbing them down.

Produce a research brief on the topic with exactly these sections:

## What this actually is
Plain language, plus one analogy that a smart non-specialist would get.

## Why it matters right now
Specific companies, products, funding events, regulatory changes, or shifts
from the last few years. Name them. No "it's growing rapidly".

## Key concepts
Between 4 and 7 concepts. For each: what it is, and how it connects to the
others. Make the connections explicit.

## The mental model
How the pieces fit together as one system. Describe the flow end to end.

## Where this intersects other domains
At least three domains (healthcare, finance, education, logistics, and so on),
each with a specific real example, not a hypothetical.

## The current landscape
Key players, live debates, and an honest split of hype versus substance.

## What most people get wrong
Three to five concrete misconceptions and the correction for each.

## Rabbit holes worth exploring
Specific papers, repos, docs, or subtopics, with why each is worth the time.
"""

_ARCHITECT = """You are a curriculum designer who builds project-based learning
paths. You have seen too many courses that are all theory and no building, and
you refuse to produce another one.

Using the research brief, design a learning path with exactly these sections:

## Prerequisites
What the learner must already know, and a quick way to self-check each item.

## Time estimate
Total hours, and hours per phase.

## Phases
Between 4 and 6 phases that build on each other. Each phase gets:
### Phase N: <name> (<hours>)
- **Learn** — specific concepts, plus named resources: real docs, real books,
  real courses with their actual titles and URLs where you know them.
- **Build** — one small hands-on task that produces something runnable.
- **Checkpoint** — how the learner knows they understood it. A question they
  can answer or an output they can inspect, not "reflect on what you learned".

One phase must be titled with "Connecting the dots" and must link this topic to
a different domain from the research brief.

## Capstone
One paragraph describing where the path lands, to be specified in detail later.
"""

_BUILDER = """You are a staff engineer who writes project specs that junior
engineers can actually follow. You know exactly where people get stuck because
you have watched them get stuck there.

Design ONE capstone project, 8 to 15 hours, portfolio-worthy, with exactly
these sections:

## The scenario
A realistic setup, in second person. "You are a data engineer at a mid-size
logistics company and ..." Give it real constraints.

## Tech stack
Every tool with its version and its install command. Real package names.

## Architecture
The components and how data moves between them. Describe the flow explicitly.

## Build steps
Between 5 and 8 steps. Each step gets:
### Step N: <what you are doing>
- **Details** — the specific work, with real commands and real file names.
- **Teaches** — the concept this step makes concrete.
- **Where you will get stuck** — the actual failure mode, and the fix.

## Testing
How to verify the thing works. Specific commands and expected output.

## Stretch goals
Three, ordered by how much they teach.

## Writing angles
Three specific angles for writing about this project afterwards.
"""

_PUBLISHER = """You are a technical writer who ghostwrites for practitioners.
You match their voice exactly and you never pad.

Produce all three pieces below in one response. Use these three headings
verbatim, and nothing above the first one:

## LINKEDIN
150 to 300 words. First line is a hook that earns the click — never "I just
learned", never "Excited to share". One core insight, not three. Short
paragraphs, most one or two sentences. End with a genuine question.
No hashtags unless they are load-bearing.

## SUBSTACK
800 to 1500 words. Structure: a story-driven opening, then Context, then the
Core Insight, then How It Works, then Why It Matters, then What's Next. Use
those as section headings. Include at least one cross-domain connection drawn
from the research brief. Concrete examples throughout.

## NOTION
A reference document optimized for looking something up months from now, with
these sections: TL;DR (three bullets), Core concepts (term — definition), Key
relationships, Useful analogies, Best resources (with URLs where known), Open
questions, Connections to other topics.
"""

_SYSTEM_PROMPTS = {
    "scout": _SCOUT,
    "architect": _ARCHITECT,
    "builder": _BUILDER,
    "publisher": _PUBLISHER,
}

# Which prior outputs each agent receives, in order. The Scout gets the topic
# only; every later agent gets everything produced before it.
_CONTEXT_KEYS = {
    "scout": [],
    "architect": ["research"],
    "builder": ["research", "learning"],
    "publisher": ["research", "learning", "project"],
}

_CONTEXT_LABELS = {
    "research": "RESEARCH BRIEF",
    "learning": "LEARNING PATH",
    "project": "PROJECT SPEC",
}


def load_profile() -> str:
    """The profile body, or a minimal fallback if the file is missing."""
    try:
        text = PROFILE_PATH.read_text(encoding="utf-8")
    except OSError:
        return _PROFILE_FALLBACK
    return text.strip() or _PROFILE_FALLBACK


def save_profile(text: str) -> None:
    """Persist the profile. A plain file write — never a rewrite of this module."""
    PROFILE_PATH.write_text(text, encoding="utf-8")


def system_prompt(agent: str) -> str:
    body = _SYSTEM_PROMPTS[agent]
    return (
        f"{body}\n{_SHARED_RULES}\n"
        f"Everything you write is for this specific person:\n\n"
        f"{load_profile()}\n{_VERIFY_BLOCK}"
    )


def user_prompt(agent: str, topic: str, prior: dict[str, str]) -> str:
    if agent not in _CONTEXT_KEYS:
        raise KeyError(agent)
    parts = [f"TOPIC: {topic}"]
    for key in _CONTEXT_KEYS[agent]:
        content = prior.get(key)
        if content:
            parts.append(f"--- {_CONTEXT_LABELS[key]} ---\n{content}")
    parts.append("Produce your output now, using exactly the sections specified.")
    return "\n\n".join(parts)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add prompts.py profile.md tests/test_prompts.py
git commit -m "feat: agent prompts with profile injection and verify blocks"
```

---

## Task 5: `call_model()` and model resolution

The single Ollama chokepoint. Everything subtle about talking to a model lives here and nowhere
else: streaming, `num_ctx`, the idle timeout, cloud-versus-local resolution, and actionable errors.

**Files:**
- Create: `agents.py` (first half — the model layer)
- Test: `tests/test_agents.py` (first half)

**Interfaces:**
- Consumes: `config.*`.
- Produces: `agents.OllamaError(RuntimeError)` with a `.hint: str` attribute,
  `agents.RunCancelled(Exception)`, `agents.CLOUD_MODELS: list[str]`,
  `agents.is_cloud_model(name: str) -> bool`,
  `agents.list_local_models() -> list[str]`,
  `agents.resolve_model(preferred: str | None = None) -> tuple[str, str]` returning
  `(model_name, "cloud" | "local")`, `agents.preflight() -> dict`,
  `agents.call_model(system: str, user: str, *, model: str, temperature: float,
  on_token: Callable[[str], None] | None = None, should_cancel: Callable[[], bool] | None = None) -> str`.

- [ ] **Step 1: Write the failing test**

`tests/test_agents.py`:
```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_agents.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents'`

- [ ] **Step 3: Write the model layer in `agents.py`**

```python
"""The agent engine.

`call_model()` is the ONLY function in this project that talks to Ollama. To
move to the Claude API or Gemini later, reimplement that one function and leave
everything else alone.
"""

import json
from collections.abc import Callable
from datetime import datetime

import requests

import config
import prompts
import runstore
from textutil import split_writer_output

# Cloud model families, for mode detection and for the settings dropdown.
# /api/tags lists LOCAL models only, so cloud names cannot be discovered and
# must be listed. Verify against https://ollama.com/search?c=cloud.
CLOUD_MODELS = [
    "gpt-oss:120b-cloud",
    "gpt-oss:20b-cloud",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "qwen3.5:122b",
    "glm-5.2",
    "kimi-k2.6",
    "minimax-m2.7",
    "mistral-large-3",
    "nemotron-3-super",
    "gemma4:31b",
]

_CLOUD_NAMES = set(CLOUD_MODELS)


class OllamaError(RuntimeError):
    """A failure the user can act on. `hint` is the exact command to run."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


class RunCancelled(Exception):
    """Raised when the user cancels mid-generation."""


def is_cloud_model(name: str) -> bool:
    return name.endswith("-cloud") or name in _CLOUD_NAMES


def _headers() -> dict:
    """Auth is only needed when calling a cloud model without `ollama signin`."""
    if config.OLLAMA_API_KEY:
        return {"Authorization": f"Bearer {config.OLLAMA_API_KEY}"}
    return {}


def _classify(error_text: str, model: str) -> OllamaError:
    """Turn an Ollama error string into something with a fix attached."""
    lowered = error_text.lower()
    if "not found" in lowered or "no such model" in lowered:
        if is_cloud_model(model):
            return OllamaError(
                f"Model '{model}' is not available.",
                f"Sign in to use cloud models: ollama signin",
            )
        return OllamaError(
            f"Model '{model}' is not installed.", f"Download it with: ollama pull {model}"
        )
    if "unauthor" in lowered or "forbidden" in lowered or "401" in lowered:
        return OllamaError(
            "Ollama rejected the request as unauthenticated.",
            "Sign in with: ollama signin  (or set OLLAMA_API_KEY)",
        )
    if "rate" in lowered and "limit" in lowered or "429" in lowered or "quota" in lowered:
        return OllamaError(
            "Ollama Cloud is rate-limiting this account.",
            "Wait and retry, lower MAX_CONCURRENT_RUNS, or upgrade your plan at "
            "https://ollama.com/settings",
        )
    return OllamaError(f"Ollama returned an error: {error_text}", "")


def call_model(
    system: str,
    user: str,
    *,
    model: str,
    temperature: float,
    on_token: Callable[[str], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> str:
    """Send one chat request to Ollama and return the full response text.

    Streams so the caller can surface tokens live. The read timeout is per-read,
    which gives exactly the semantics wanted: the call aborts after
    AGENT_IDLE_TIMEOUT seconds *of silence*, not after a fixed wall-clock budget
    — a correct local generation can legitimately run for 20 minutes.

    Cloud and local models both go through the local daemon, so only the model
    name distinguishes them.
    """
    payload = {
        "model": model,
        "stream": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "temperature": temperature,
            # Explicit and non-negotiable: the default context window is small
            # regardless of model capability, and would silently drop the
            # earliest part of a long prompt.
            "num_ctx": config.NUM_CTX,
            "num_predict": config.MAX_TOKENS,
        },
    }
    if not is_cloud_model(model):
        # Irrelevant for cloud-hosted models; keeps a local model resident.
        payload["keep_alive"] = config.KEEP_ALIVE

    try:
        response = requests.post(
            f"{config.OLLAMA_URL}/api/chat",
            json=payload,
            stream=True,
            timeout=(config.CONNECT_TIMEOUT, config.AGENT_IDLE_TIMEOUT),
            headers=_headers(),
        )
    except requests.ConnectionError as exc:
        raise OllamaError(
            "Cannot reach Ollama.", "Start it with: ollama serve"
        ) from exc
    except requests.ReadTimeout as exc:
        raise OllamaError(
            f"The model stopped producing output for "
            f"{config.AGENT_IDLE_TIMEOUT}s and the request was abandoned.",
            "Try a smaller model, or raise AGENT_IDLE_TIMEOUT.",
        ) from exc

    pieces: list[str] = []
    try:
        for line in response.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            if chunk.get("error"):
                raise _classify(str(chunk["error"]), model)

            piece = chunk.get("message", {}).get("content", "")
            if piece:
                pieces.append(piece)
                if on_token:
                    on_token(piece)
            if should_cancel and should_cancel():
                raise RunCancelled()
            if chunk.get("done"):
                break
    except requests.ReadTimeout as exc:
        raise OllamaError(
            f"The model stopped producing output for "
            f"{config.AGENT_IDLE_TIMEOUT}s mid-response.",
            "Try a smaller model, or raise AGENT_IDLE_TIMEOUT.",
        ) from exc
    finally:
        response.close()

    text = "".join(pieces).strip()
    if not text:
        raise OllamaError(f"Model '{model}' returned an empty response.", "Try again.")
    return text


def list_local_models() -> list[str]:
    """Installed local models. Cloud models never appear here."""
    try:
        response = requests.get(
            f"{config.OLLAMA_URL}/api/tags",
            timeout=config.CONNECT_TIMEOUT,
            headers=_headers(),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError("Cannot reach Ollama.", "Start it with: ollama serve") from exc
    return [entry["name"] for entry in response.json().get("models", [])]


def resolve_model(preferred: str | None = None) -> tuple[str, str]:
    """Pick the model to use. Returns (model_name, "cloud" | "local").

    Cloud names pass through untouched — they cannot be verified locally, and a
    wrong guess surfaces as an actionable auth error at call time. Local names
    are checked against what is installed, falling back to the largest
    installed model rather than failing on a missing download.
    """
    wanted = preferred or config.MODEL_NAME
    if is_cloud_model(wanted):
        return wanted, "cloud"

    installed = list_local_models()
    if wanted in installed:
        return wanted, "local"
    if installed:
        # Longest name is a crude proxy for "most specific tag"; good enough,
        # and the chosen model is always reported to the user.
        return sorted(installed, key=len, reverse=True)[0], "local"

    raise OllamaError(
        f"No models are available and '{wanted}' is not installed.",
        f"Either: ollama pull {wanted}   or: ollama signin  (to use cloud models)",
    )


def preflight() -> dict:
    """Health snapshot for GET /api/health and for the CLI banner."""
    status = {"ollama": False, "models": [], "cloud_models": CLOUD_MODELS, "error": None}
    try:
        status["models"] = list_local_models()
        status["ollama"] = True
        model, mode = resolve_model(config.MODEL_NAME)
        status["model"], status["mode"] = model, mode
    except OllamaError as exc:
        status["error"] = str(exc)
        status["hint"] = exc.hint
    return status
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_agents.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add agents.py tests/test_agents.py
git commit -m "feat: call_model with streaming, explicit num_ctx, and actionable errors"
```

---

## Task 6: The pipeline — events, atomicity, cancel, retry

**Files:**
- Modify: `agents.py` (append the pipeline layer)
- Modify: `tests/test_agents.py` (append pipeline tests)

**Interfaces:**
- Consumes: `agents.call_model`, `agents.resolve_model`, `prompts.*`, `runstore.*`,
  `textutil.split_writer_output`.
- Produces: `agents.run_agent(agent: str, topic: str, prior: dict, *, model: str,
  temperature: float, on_token=None, should_cancel=None) -> str`, and
  `agents.run_pipeline(topic: str, *, on_event: Callable[[dict], None], run_id: str,
  prior: dict | None = None, model: str | None = None, temperature: float | None = None,
  should_cancel: Callable[[], bool] | None = None) -> dict`.
  `run_pipeline` emits these event shapes and no others:
  `{"type": "agent_start", "agent", "step", "total"}`,
  `{"type": "agent_token", "agent", "step", "delta"}`,
  `{"type": "agent_complete", "agent", "step", "output"}`,
  `{"type": "pipeline_complete", "run_id", "folder", "files", "missing_sections"}`,
  `{"type": "error", "message", "hint", "agent", "step", "completed"}`,
  `{"type": "cancelled", "agent", "step", "completed"}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agents.py`:
```python
def _stub_outputs(monkeypatch, failing_agent=None):
    """Replace call_model with a deterministic stub. Returns the call log."""
    calls = []

    def fake_call_model(system, user, *, model, temperature, on_token=None, should_cancel=None):
        agent = "publisher" if "## LINKEDIN" in system else user.split("\n")[0]
        calls.append({"system": system, "user": user, "model": model})
        if failing_agent and failing_agent in system[:400]:
            raise agents.OllamaError("boom", "do the thing")
        if "## LINKEDIN" in system:
            body = "## LINKEDIN\npost body\n\n## SUBSTACK\narticle body\n\n## NOTION\nref body"
        else:
            body = f"output-{len(calls)}"
        if on_token:
            on_token(body)
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
    assert all(label in calls[3]["user"] for label in ("RESEARCH BRIEF", "LEARNING PATH", "PROJECT SPEC"))


def test_run_pipeline_writes_seven_files_only_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    _stub_outputs(monkeypatch)
    result = agents.run_pipeline("topic", on_event=lambda e: None, run_id="t-20260809-1200")

    assert len(result["files"]) == 7
    directory = runstore.safe_run_dir("t-20260809-1200")
    assert (directory / "04-writer-combined.md").exists()
    assert (directory / "run.json").exists()


def test_run_pipeline_writes_nothing_when_an_agent_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    _stub_outputs(monkeypatch, failing_agent="capstone project")  # the Builder
    events = []

    with pytest.raises(agents.OllamaError):
        agents.run_pipeline("topic", on_event=events.append, run_id="t-20260809-1200")

    # Atomic: no folder at all, not even a partial one.
    assert not (tmp_path / "output" / "t-20260809-1200").exists()
    assert not list((tmp_path / "output").glob("*.partial")) if (tmp_path / "output").exists() else True

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
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    _stub_outputs(monkeypatch)
    events = []

    with pytest.raises(agents.RunCancelled):
        agents.run_pipeline(
            "topic",
            on_event=events.append,
            run_id="t-20260809-1200",
            should_cancel=lambda: True,
        )

    assert not (tmp_path / "output" / "t-20260809-1200").exists()
    assert [event for event in events if event["type"] == "cancelled"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_agents.py -k pipeline -v`
Expected: FAIL with `AttributeError: module 'agents' has no attribute 'run_pipeline'`

- [ ] **Step 3: Append the pipeline layer to `agents.py`**

```python
def run_agent(
    agent: str,
    topic: str,
    prior: dict[str, str],
    *,
    model: str,
    temperature: float,
    on_token: Callable[[str], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> str:
    """Run one agent. All prior outputs are passed as context in the user message."""
    return call_model(
        prompts.system_prompt(agent),
        prompts.user_prompt(agent, topic, prior),
        model=model,
        temperature=temperature,
        on_token=on_token,
        should_cancel=should_cancel,
    )


def run_pipeline(
    topic: str,
    *,
    on_event: Callable[[dict], None],
    run_id: str,
    prior: dict[str, str] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict:
    """Run the four agents in sequence and write the run atomically.

    Nothing touches disk until all four agents have succeeded, so `output/`
    never contains a partial run. Completed output is reported on the error
    event, which is what lets the caller retry from the failed agent instead of
    regenerating from scratch — pass it back in as `prior`.

    Events are pushed through `on_event`; this function knows nothing about
    WebSockets or terminals, so the CLI and the server share it unchanged.
    """
    resolved_model, mode = resolve_model(model)
    temp = config.TEMPERATURE if temperature is None else temperature
    outputs: dict[str, str] = dict(prior or {})
    total = len(prompts.AGENTS)

    for step, agent in enumerate(prompts.AGENTS, start=1):
        output_key = prompts.AGENT_META[agent]["output_key"]
        if output_key in outputs:
            continue  # resuming: this agent already succeeded on a prior attempt

        on_event({"type": "agent_start", "agent": agent, "step": step, "total": total})
        try:
            text = run_agent(
                agent,
                topic,
                outputs,
                model=resolved_model,
                temperature=temp,
                on_token=lambda delta, a=agent, s=step: on_event(
                    {"type": "agent_token", "agent": a, "step": s, "delta": delta}
                ),
                should_cancel=should_cancel,
            )
        except RunCancelled:
            on_event({
                "type": "cancelled", "agent": agent, "step": step,
                "completed": sorted(outputs),
            })
            raise
        except OllamaError as exc:
            on_event({
                "type": "error", "message": str(exc), "hint": exc.hint,
                "agent": agent, "step": step, "completed": sorted(outputs),
            })
            raise

        outputs[output_key] = text
        on_event({
            "type": "agent_complete", "agent": agent, "step": step, "output": text,
        })

    # The Publisher returns all three pieces in one response; split them, and
    # always keep the raw response so a parsing failure loses nothing.
    sections, missing = split_writer_output(outputs["combined"])
    outputs.update(sections)

    files = runstore.write_run(
        run_id,
        topic,
        outputs,
        {
            "model": resolved_model,
            "mode": mode,
            "temperature": temp,
            "missing_sections": missing,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    folder = str(runstore.safe_run_dir(run_id))
    result = {
        "type": "pipeline_complete",
        "run_id": run_id,
        "folder": folder,
        "files": files,
        "missing_sections": missing,
    }
    on_event(result)
    return result
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add agents.py tests/test_agents.py
git commit -m "feat: agent pipeline with atomic writes, cancel, and resume"
```

---

## Task 7: CLI mode and the entry point

Delivering the CLI before the web UI means the pipeline is usable and prompt quality can be tuned
with nothing else built.

**Files:**
- Create: `run.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `agents.*`, `prompts.*`, `config.*`, `runstore.mint_run_id`.
- Produces: `run.banner(model: str, mode: str) -> str`, `run.cli_event_printer() -> Callable`,
  `run.run_cli(topic: str | None, agent: str | None) -> int`, `run.main(argv=None) -> int`.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
import config
import run as entry


def test_banner_shows_both_names_and_the_model():
    text = entry.banner("gpt-oss:120b-cloud", "cloud")
    assert config.APP_NAME in text
    assert config.TAGLINE in text
    assert "gpt-oss:120b-cloud" in text
    assert "cloud" in text


def test_event_printer_reports_each_agent(capsys):
    printer = entry.cli_event_printer()
    printer({"type": "agent_start", "agent": "scout", "step": 1, "total": 4})
    printer({"type": "agent_complete", "agent": "scout", "step": 1, "output": "x" * 40})
    output = capsys.readouterr().out
    assert "The Scout" in output
    assert "1/4" in output


def test_event_printer_shows_the_hint_on_error(capsys):
    printer = entry.cli_event_printer()
    printer({
        "type": "error", "message": "Cannot reach Ollama.",
        "hint": "Start it with: ollama serve", "agent": "scout", "step": 1, "completed": [],
    })
    output = capsys.readouterr().out
    assert "ollama serve" in output


def test_argument_parsing_accepts_the_documented_flags():
    parsed = entry.parse_args(["--cli", "--agent", "research", "--topic", "vector databases"])
    assert parsed.cli is True
    assert parsed.agent == "research"
    assert parsed.topic == "vector databases"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'run'`

- [ ] **Step 3: Write `run.py`**

```python
"""Entry point. Starts the web server by default; --cli runs in the terminal."""

import argparse
import sys
import threading
import webbrowser

import agents
import config
import prompts
import runstore
from prompts import AGENT_ALIASES


def banner(model: str, mode: str) -> str:
    return (
        f"\n  {config.APP_NAME}  —  {config.TAGLINE}\n"
        f"  {'-' * 44}\n"
        f"  model: {model}  ({mode})\n"
    )


def cli_event_printer():
    """Terminal progress reporter with the same event contract as the WebSocket."""

    def printer(event: dict) -> None:
        kind = event.get("type")
        if kind == "agent_start":
            meta = prompts.AGENT_META[event["agent"]]
            print(
                f"\n{meta['emoji']}  Agent {event['step']}/{event['total']}: "
                f"{meta['name']} — {meta['activity']}..."
            )
        elif kind == "agent_token":
            # A visible pulse without flooding the terminal with the full text.
            print(".", end="", flush=True)
        elif kind == "agent_complete":
            meta = prompts.AGENT_META[event["agent"]]
            print(f"\n   done: {meta['name']} ({len(event['output'].split())} words)")
        elif kind == "pipeline_complete":
            print(f"\n✅  Saved to {event['folder']}")
            for filename in event["files"]:
                print(f"    - {filename}")
            if event["missing_sections"]:
                print(
                    "\n⚠️   The writer's output could not be split into: "
                    f"{', '.join(event['missing_sections'])}."
                    "\n    The full response is in 04-writer-combined.md."
                )
            print(
                "\nNext steps:"
                "\n  1. Read the research brief, then start Phase 1 of the learning path."
                "\n  2. Check the 'Verify before publishing' block in each file before posting."
            )
        elif kind == "cancelled":
            print("\n⛔  Cancelled. Nothing was written.")
        elif kind == "error":
            print(f"\n❌  {event['message']}")
            if event.get("hint"):
                print(f"    → {event['hint']}")

    return printer


def run_cli(topic: str | None, agent: str | None) -> int:
    try:
        model, mode = agents.resolve_model()
    except agents.OllamaError as exc:
        print(f"\n❌  {exc}\n    → {exc.hint}")
        return 1

    print(banner(model, mode))

    while True:
        current = topic or input(f"{config.APP_SHORT_NAME} › What do you want to learn about? ")
        current = current.strip()
        if not current:
            print("A topic is required.")
            if topic:
                return 1
            continue

        printer = cli_event_printer()
        run_id = runstore.mint_run_id(current)
        try:
            if agent:
                key = AGENT_ALIASES[agent]
                printer({"type": "agent_start", "agent": key, "step": 1, "total": 1})
                text = agents.run_agent(
                    key, current, {}, model=model, temperature=config.TEMPERATURE
                )
                printer({"type": "agent_complete", "agent": key, "step": 1, "output": text})
                print("\n" + text)
            else:
                agents.run_pipeline(current, on_event=printer, run_id=run_id)
        except agents.RunCancelled:
            return 130
        except agents.OllamaError:
            return 1

        if topic:
            return 0
        if input("\nExplore another topic? [y/N] ").strip().lower() != "y":
            return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="run.py", description=f"{config.APP_NAME} — {config.TAGLINE}"
    )
    parser.add_argument("--cli", action="store_true", help="run in the terminal")
    parser.add_argument("--topic", help="topic to explore (CLI mode)")
    parser.add_argument(
        "--agent", choices=sorted(AGENT_ALIASES), help="run a single agent (CLI mode)"
    )
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.cli:
        return run_cli(args.topic, args.agent)

    import uvicorn

    from server import app

    # Port 8000 is often already taken; pick the next free one rather than
    # failing with a bind traceback.
    port = config.find_free_port(args.port)
    url = f"http://{config.HOST}:{port}"
    if port != args.port:
        print(f"  port {args.port} is in use — using {port} instead")

    status = agents.preflight()
    print(banner(status.get("model", config.MODEL_NAME), status.get("mode", "unknown")))
    if not status["ollama"]:
        print(f"  ⚠️  {status['error']}\n      → {status.get('hint', '')}")
    print(f"  {config.APP_SHORT_NAME} is running at {url}\n")

    if not args.no_browser:
        # Open only once the server is actually accepting connections.
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()

    uvicorn.run(app, host=config.HOST, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: 4 passed

- [ ] **Step 5: First real end-to-end check**

```bash
ollama signin
python run.py --cli --agent research --topic "vector databases for AI applications"
```

Expected: the banner names the resolved model and mode, dots stream while the Scout works, and a
research brief prints with a "Verify before publishing" block at the end. **Read the output.** This
is the moment to judge whether prompt quality is good enough before any UI exists — iterate on
`prompts.py` here, not later.

- [ ] **Step 6: Commit**

```bash
git add run.py tests/test_cli.py
git commit -m "feat: CLI mode and entry point with free-port selection"
```

---

## Task 8: FastAPI server — endpoints, run registry, WebSocket replay

The subtlest task in the plan. Three things interact: a blocking pipeline running in a worker
thread, an event buffer that makes the WebSocket race-free, and a semaphore that queues runs beyond
the concurrency cap.

**Files:**
- Create: `server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `server.app: FastAPI`, `server.RunRegistry` with
  `create(topic, model, temperature) -> str`, `start(run_id) -> None`,
  `events(run_id) -> list[dict]`, `subscribe(run_id) -> asyncio.Queue`,
  `unsubscribe(run_id, queue) -> None`, `cancel(run_id) -> bool`,
  `retry(run_id) -> str`, `state(run_id) -> dict`; and module-level `registry: RunRegistry`.

- [ ] **Step 1: Write the failing test**

`tests/test_server.py`:
```python
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

    def fake_call_model(system, user, *, model, temperature, on_token=None, should_cancel=None):
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


def test_health_reports_ollama_status(client):
    body = client.get("/api/health").json()
    assert body["ollama"] is True
    assert "app" in body and body["app"] == config.APP_NAME


def test_models_lists_local_and_cloud(client):
    body = client.get("/api/models").json()
    assert "stub" in body["local"]
    assert any(name.endswith("-cloud") for name in body["cloud"])


def test_run_then_websocket_replays_missed_events(client):
    run_id = client.post("/api/run", json={"topic": "vector databases"}).json()["run_id"]

    # Connect *after* the run was started: every event must still arrive.
    received = []
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        while True:
            event = websocket.receive_json()
            received.append(event)
            if event["type"] in {"pipeline_complete", "error"}:
                break

    types = [event["type"] for event in received]
    assert types.count("agent_start") == 4
    assert types[-1] == "pipeline_complete"
    assert [event["agent"] for event in received if event["type"] == "agent_start"] == [
        "scout", "architect", "builder", "publisher"
    ]


def test_runs_lifecycle(client):
    run_id = client.post("/api/run", json={"topic": "kafka in fintech"}).json()["run_id"]
    with client.websocket_connect(f"/ws/pipeline/{run_id}") as websocket:
        while websocket.receive_json()["type"] != "pipeline_complete":
            pass

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


def test_run_single_agent_endpoint(client):
    body = client.post("/api/run/single", json={"topic": "topic", "agent": "research"}).json()
    assert body["agent"] == "scout"
    assert body["output"] == "generated body"


@pytest.mark.parametrize("run_id", ["../etc", "..", "a/b", "C:/Windows"])
def test_path_traversal_is_rejected(client, run_id):
    assert client.get(f"/api/runs/{run_id}").status_code in (400, 404)
    assert client.delete(f"/api/runs/{run_id}").status_code in (400, 404)


def test_arbitrary_file_read_is_rejected(client):
    response = client.get("/api/runs/whatever-20260809-1200/../../config.py")
    assert response.status_code in (400, 404)


def test_empty_topic_is_rejected(client):
    assert client.post("/api/run", json={"topic": "   "}).status_code == 422


def test_profile_round_trip(client, tmp_path, monkeypatch):
    import prompts

    monkeypatch.setattr(prompts, "PROFILE_PATH", tmp_path / "profile.md")
    assert client.put("/api/profile", json={"content": "## Who I am\nnew ✍️"}).status_code == 200
    assert "✍️" in client.get("/api/profile").json()["content"]


def test_config_round_trip(client):
    body = client.put("/api/config", json={"model": "stub", "temperature": 0.42}).json()
    assert body["temperature"] == 0.42
    assert client.get("/api/config").json()["model"] == "stub"


def test_cancel_marks_the_run_cancelled(client):
    run_id = client.post("/api/run", json={"topic": "slow topic"}).json()["run_id"]
    client.post(f"/api/run/{run_id}/cancel")
    assert client.get(f"/api/run/{run_id}/state").json()["status"] in {
        "cancelled", "cancelling", "complete"
    }


def test_index_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert config.APP_NAME in response.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Write `server.py`**

The threading detail matters: `requests` is blocking, so the pipeline runs via `asyncio.to_thread`,
and its `on_event` callback hops back onto the event loop with `call_soon_threadsafe`. Without that
hop, queue writes from the worker thread would race with the loop.

```python
"""FastAPI backend: REST endpoints, the run registry, and the progress WebSocket."""

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

import agents
import config
import prompts
import runstore

STATIC_DIR = Path(__file__).with_name("static")

app = FastAPI(title=config.APP_NAME, description=config.TAGLINE)


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
            # touching subscriber queues.
            loop.call_soon_threadsafe(self._publish, run, event)

        async with self._semaphore:
            if run["cancel"]:
                emit({"type": "cancelled", "agent": None, "step": 0, "completed": []})
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
                run["status"] = "failed"
            except Exception as exc:  # unexpected: still must reach the client
                emit({
                    "type": "error", "message": f"Unexpected failure: {exc}",
                    "hint": "", "agent": None, "step": 0, "completed": [],
                })
                run["status"] = "failed"

    async def retry(self, run_id: str) -> None:
        """Resume a failed run at the failed agent, reusing completed output."""
        run = self._require(run_id)
        if run["status"] not in {"failed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Run is not in a retryable state")
        run["cancel"] = False
        run["status"] = "queued"
        await self.start(run_id)


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
    await registry.retry(run_id)
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


@app.get("/api/runs/{run_id}/{filename}", response_class=PlainTextResponse)
def get_run_file(run_id: str, filename: str) -> str:
    try:
        path = runstore.safe_run_file(run_id, filename)
    except runstore.UnsafePath as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"No such file: {filename}")
    return path.read_text(encoding="utf-8")


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict:
    try:
        runstore.delete_run(run_id)
    except runstore.UnsafePath as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deleted": run_id}


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
        await websocket.send_json({"type": "error", "message": f"Unknown run: {run_id}", "hint": ""})
        await websocket.close()
        return

    queue = registry.subscribe(run_id)
    try:
        for event in history:
            await websocket.send_json(event)
            if event["type"] in {"pipeline_complete", "error", "cancelled"}:
                return
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event["type"] in {"pipeline_complete", "error", "cancelled"}:
                return
    except WebSocketDisconnect:
        pass
    finally:
        registry.unsubscribe(run_id, queue)


# --- Static frontend ----------------------------------------------------
# Mounted last so it never shadows an /api route.

@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
```

- [ ] **Step 4: Create a placeholder `static/index.html` so the mount and index test pass**

```html
<h1>Seeytu-Xamleh</h1>
<p>Explore. Learn. Publish.</p>
```

Task 9 replaces this with the real page.

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_server.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add server.py static/index.html tests/test_server.py
git commit -m "feat: FastAPI backend with run registry and WebSocket replay"
```

---

## Task 9: Frontend shell — vendored libraries, theme tokens, page structure

**Files:**
- Create: `static/index.html`, `static/style.css`
- Modify: `static/vendor/` (four downloaded files)

**Interfaces:**
- Consumes: `/api/*` and `/ws/pipeline/{run_id}` from Task 8.
- Produces: DOM contract for Task 10 — `#view-home`, `#view-progress`, `#view-results`,
  `#topic-input`, `#start-button`, `#example-chips`, `#agent-steps`, `#live-output`,
  `#cancel-button`, `#result-tabs`, `#result-panel`, `#history-list`, `#theme-toggle`,
  `#settings-button`, and `body.light` as the light-mode class.

- [ ] **Step 1: Vendor the three libraries and one theme**

```powershell
$vendor = "static/vendor"
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js" -OutFile "$vendor/marked.min.js"
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/dompurify@3.0.11/dist/purify.min.js" -OutFile "$vendor/purify.min.js"
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/highlight.min.js" -OutFile "$vendor/highlight.min.js"
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/styles/github-dark.min.css" -OutFile "$vendor/highlight-theme.css"
```

Pinned versions, served locally. Confirm each file is non-empty before continuing — this is the one
step that needs network access, and it keeps the app working offline afterwards.

- [ ] **Step 2: Write `static/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Seeytu — Explore. Learn. Publish.</title>
  <link rel="stylesheet" href="/static/vendor/highlight-theme.css">
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <aside id="sidebar">
    <div class="sidebar-head">
      <span class="brand-mark">S</span>
      <span class="sidebar-title">History</span>
    </div>
    <ul id="history-list" class="history-list"></ul>
  </aside>

  <main id="main">
    <header id="app-header">
      <div>
        <h1>Seeytu-Xamleh</h1>
        <p class="tagline">Explore. Learn. Publish. <span class="muted">— Wolof: "explore and teach"</span></p>
      </div>
      <div class="header-actions">
        <button id="theme-toggle" class="icon-button" title="Toggle theme" aria-label="Toggle theme">◐</button>
        <button id="settings-button" class="icon-button" title="Settings" aria-label="Settings">⚙</button>
      </div>
    </header>

    <section id="view-home" class="view is-active">
      <h2 class="prompt-label">What do you want to learn about?</h2>
      <div class="input-row">
        <input id="topic-input" type="text" autocomplete="off"
               placeholder="e.g. how vector databases actually work">
        <button id="start-button" class="primary">Start Learning</button>
      </div>
      <div id="example-chips" class="chips"></div>
      <p id="health-note" class="health-note"></p>
    </section>

    <section id="view-progress" class="view">
      <ol id="agent-steps" class="agent-steps"></ol>
      <div class="progress-actions">
        <span id="progress-status" class="muted"></span>
        <button id="cancel-button" class="ghost">Cancel run</button>
      </div>
      <article id="live-output" class="markdown"></article>
    </section>

    <section id="view-results" class="view">
      <div class="results-head">
        <h2 id="results-topic"></h2>
        <div class="results-actions">
          <button id="copy-button" class="ghost">Copy markdown</button>
          <button id="download-button" class="ghost">Download .md</button>
        </div>
      </div>
      <p id="results-warning" class="warning" hidden></p>
      <nav id="result-tabs" class="tabs" role="tablist"></nav>
      <article id="result-panel" class="markdown"></article>
    </section>
  </main>

  <script src="/static/vendor/marked.min.js"></script>
  <script src="/static/vendor/purify.min.js"></script>
  <script src="/static/vendor/highlight.min.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write `static/style.css`**

Dark by default; `body.light` overrides only the token values, so the whole theme is one class
toggle.

```css
:root {
  --bg: #0e0f13;
  --surface: #16181f;
  --surface-2: #1d2029;
  --border: #262a35;
  --text: #e6e8ee;
  --text-dim: #9aa1b1;
  --accent: #7c9cff;
  --ok: #4ade80;
  --warn: #fbbf24;
  --err: #f87171;
  --radius: 10px;
  --font: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --mono: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
}

body.light {
  --bg: #fbfbfd;
  --surface: #ffffff;
  --surface-2: #f3f4f8;
  --border: #e2e4ec;
  --text: #14161c;
  --text-dim: #5c6474;
  --accent: #3b5bdb;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  display: grid;
  grid-template-columns: 260px 1fr;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  line-height: 1.65;
}

/* --- Sidebar --- */
#sidebar {
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 1.25rem 1rem;
  overflow-y: auto;
}
.sidebar-head { display: flex; align-items: center; gap: .6rem; margin-bottom: 1rem; }
.brand-mark {
  display: grid; place-items: center;
  width: 26px; height: 26px; border-radius: 7px;
  background: var(--accent); color: #fff; font-weight: 700; font-size: .85rem;
}
.sidebar-title { color: var(--text-dim); font-size: .8rem; text-transform: uppercase; letter-spacing: .08em; }
.history-list { list-style: none; margin: 0; padding: 0; }
.history-item {
  padding: .55rem .6rem; border-radius: 8px; cursor: pointer;
  display: flex; justify-content: space-between; gap: .5rem; align-items: center;
}
.history-item:hover { background: var(--surface-2); }
.history-item.is-active { background: var(--surface-2); outline: 1px solid var(--border); }
.history-topic { font-size: .88rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-date { font-size: .72rem; color: var(--text-dim); }
.history-delete { opacity: 0; border: 0; background: none; color: var(--text-dim); cursor: pointer; }
.history-item:hover .history-delete { opacity: 1; }

/* --- Main --- */
#main { padding: 1.75rem 2.25rem 4rem; max-width: 60rem; }
#app-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2.5rem; }
#app-header h1 { margin: 0; font-size: 1.35rem; letter-spacing: -.01em; }
.tagline { margin: .2rem 0 0; color: var(--text-dim); font-size: .85rem; }
.muted { color: var(--text-dim); }
.header-actions { display: flex; gap: .4rem; }
.icon-button {
  background: var(--surface); border: 1px solid var(--border); color: var(--text);
  border-radius: 8px; width: 34px; height: 34px; cursor: pointer; font-size: 1rem;
}
.icon-button:hover { background: var(--surface-2); }

/* --- Views: only one visible, with a soft transition --- */
.view { display: none; animation: rise .22s ease both; }
.view.is-active { display: block; }
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

.prompt-label { font-size: 1.75rem; font-weight: 600; margin: 3rem 0 1.25rem; letter-spacing: -.02em; }
.input-row { display: flex; gap: .6rem; }
#topic-input {
  flex: 1; padding: .85rem 1rem; font-size: 1rem; font-family: inherit;
  background: var(--surface); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius);
}
#topic-input:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
button.primary {
  background: var(--accent); color: #fff; border: 0; border-radius: var(--radius);
  padding: .85rem 1.4rem; font-size: .95rem; font-weight: 600; cursor: pointer;
}
button.ghost {
  background: var(--surface); color: var(--text); border: 1px solid var(--border);
  border-radius: 8px; padding: .45rem .8rem; font-size: .85rem; cursor: pointer;
}
button.ghost:hover { background: var(--surface-2); }
.chips { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1.1rem; }
.chip {
  background: var(--surface); border: 1px solid var(--border); color: var(--text-dim);
  border-radius: 999px; padding: .4rem .85rem; font-size: .83rem; cursor: pointer;
}
.chip:hover { color: var(--text); border-color: var(--accent); }
.health-note { margin-top: 1.5rem; font-size: .85rem; color: var(--warn); }

/* --- Agent progress tracker: the centerpiece --- */
.agent-steps { list-style: none; margin: 0 0 1.5rem; padding: 0; display: grid; gap: .6rem; }
.agent-step {
  display: flex; align-items: center; gap: .85rem;
  padding: .8rem 1rem; border-radius: var(--radius);
  background: var(--surface); border: 1px solid var(--border);
  opacity: .55; transition: opacity .2s, border-color .2s;
}
.agent-step.is-running { opacity: 1; border-color: var(--accent); }
.agent-step.is-done { opacity: 1; }
.agent-emoji { font-size: 1.1rem; }
.agent-name { font-weight: 600; font-size: .92rem; }
.agent-activity { color: var(--text-dim); font-size: .82rem; }
.agent-state { margin-left: auto; font-size: .8rem; color: var(--text-dim); }
.agent-step.is-done .agent-state { color: var(--ok); }
.agent-step.is-running .agent-state::after {
  content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: var(--accent); margin-left: .4rem; animation: pulse 1.1s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: .25; } 50% { opacity: 1; } }
.progress-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }

/* --- Tabs and results --- */
.results-head { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.results-head h2 { font-size: 1.15rem; margin: 0; }
.results-actions { display: flex; gap: .5rem; }
.warning {
  background: color-mix(in srgb, var(--warn) 12%, transparent);
  border: 1px solid var(--warn); color: var(--warn);
  padding: .7rem .9rem; border-radius: 8px; font-size: .85rem;
}
.tabs { display: flex; flex-wrap: wrap; gap: .3rem; border-bottom: 1px solid var(--border); margin: 1.25rem 0 1.5rem; }
.tab {
  background: none; border: 0; border-bottom: 2px solid transparent;
  color: var(--text-dim); padding: .55rem .8rem; font-size: .88rem; cursor: pointer;
}
.tab:hover { color: var(--text); }
.tab.is-active { color: var(--text); border-bottom-color: var(--accent); }
.tab-count { color: var(--text-dim); font-size: .74rem; margin-left: .35rem; }

/* --- Rendered markdown: aim for Notion/GitHub quality --- */
.markdown { font-size: .97rem; }
.markdown h1, .markdown h2, .markdown h3 { line-height: 1.3; margin: 2rem 0 .75rem; letter-spacing: -.01em; }
.markdown h1 { font-size: 1.5rem; }
.markdown h2 { font-size: 1.2rem; padding-bottom: .3rem; border-bottom: 1px solid var(--border); }
.markdown h3 { font-size: 1.02rem; }
.markdown p, .markdown li { color: var(--text); }
.markdown a { color: var(--accent); }
.markdown code {
  font-family: var(--mono); font-size: .87em;
  background: var(--surface-2); padding: .12em .35em; border-radius: 4px;
}
.markdown pre {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1rem; overflow-x: auto;
}
.markdown pre code { background: none; padding: 0; }
.markdown blockquote {
  margin: 1rem 0; padding: .1rem 1rem; border-left: 3px solid var(--border); color: var(--text-dim);
}
.markdown table { border-collapse: collapse; width: 100%; display: block; overflow-x: auto; }
.markdown th, .markdown td { border: 1px solid var(--border); padding: .5rem .7rem; text-align: left; }
.markdown hr { border: 0; border-top: 1px solid var(--border); margin: 2rem 0; }

.toast {
  position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%);
  background: var(--surface-2); border: 1px solid var(--border); color: var(--text);
  padding: .55rem 1rem; border-radius: 999px; font-size: .85rem;
  animation: rise .18s ease both;
}

/* --- Responsive: tablet collapses the sidebar to the top --- */
@media (max-width: 900px) {
  body { grid-template-columns: 1fr; }
  #sidebar { border-right: 0; border-bottom: 1px solid var(--border); max-height: 11rem; }
  #main { padding: 1.25rem 1.1rem 3rem; }
  .prompt-label { font-size: 1.35rem; margin-top: 1.5rem; }
  .input-row { flex-direction: column; }
}
```

- [ ] **Step 4: Verify the shell renders**

Run: `python run.py --no-browser`, then open the printed URL.
Expected: dark layout, header reading "Seeytu-Xamleh" with the tagline, tab title "Seeytu — Explore.
Learn. Publish.", empty history sidebar, and the topic input centered. No console errors, and the
three vendor scripts return 200.

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/style.css static/vendor
git commit -m "feat: frontend shell with vendored libraries and theme tokens"
```

---

## Task 10: Frontend logic — streaming, tabs, history

**Files:**
- Create: `static/app.js`

**Interfaces:**
- Consumes: the DOM contract from Task 9 and every `/api` route from Task 8.
- Produces: the finished phase-1 UI. No exports.

- [ ] **Step 1: Write `static/app.js`**

```javascript
/* Seeytu-Xamleh frontend. Three views, one WebSocket, no build step. */

const AGENTS = [
  { key: "scout", emoji: "🔍", name: "The Scout", activity: "Mapping the topic landscape" },
  { key: "architect", emoji: "📐", name: "The Architect", activity: "Designing the learning path" },
  { key: "builder", emoji: "🔨", name: "The Builder", activity: "Specifying the capstone project" },
  { key: "publisher", emoji: "✍️", name: "The Publisher", activity: "Drafting the content" },
];

const EXAMPLES = [
  "How Kafka powers real-time fintech",
  "Vector databases for AI applications",
  "Platform engineering with Kubernetes",
  "Event sourcing in healthcare systems",
  "How payment rails actually settle",
  "Feature stores for ML in logistics",
];

const el = (id) => document.getElementById(id);
const state = { runId: null, socket: null, run: null, activeTab: null, streaming: "" };

/* --- Markdown rendering ------------------------------------------------ */

marked.setOptions({ breaks: false, gfm: true });

function renderMarkdown(target, markdown) {
  // Sanitize before inserting: the content is model-generated, and a stray
  // script tag costs one line to neutralize.
  target.innerHTML = DOMPurify.sanitize(marked.parse(markdown || ""));
  target.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
}

function toast(message) {
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = message;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 1600);
}

/* --- View switching ---------------------------------------------------- */

function showView(name) {
  ["home", "progress", "results"].forEach((view) => {
    el(`view-${view}`).classList.toggle("is-active", view === name);
  });
}

/* --- API -------------------------------------------------------------- */

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail?.message || detail.detail || response.statusText);
  }
  return response.status === 204 ? null : response.json();
}

/* --- Home view -------------------------------------------------------- */

function buildExamples() {
  el("example-chips").innerHTML = "";
  EXAMPLES.forEach((topic) => {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = topic;
    chip.onclick = () => {
      el("topic-input").value = topic;
      startRun();
    };
    el("example-chips").appendChild(chip);
  });
}

async function checkHealth() {
  try {
    const health = await api("/api/health");
    if (!health.ollama) {
      el("health-note").textContent = `${health.error} → ${health.hint || ""}`;
    } else {
      el("health-note").textContent = `Model: ${health.model} (${health.mode})`;
      el("health-note").style.color = "var(--text-dim)";
    }
  } catch (error) {
    el("health-note").textContent = `Backend unreachable: ${error.message}`;
  }
}

/* --- Progress view ---------------------------------------------------- */

function buildStepTracker() {
  el("agent-steps").innerHTML = "";
  AGENTS.forEach((agent) => {
    const item = document.createElement("li");
    item.className = "agent-step";
    item.id = `step-${agent.key}`;
    item.innerHTML = `
      <span class="agent-emoji">${agent.emoji}</span>
      <span>
        <span class="agent-name">${agent.name}</span><br>
        <span class="agent-activity">${agent.activity}</span>
      </span>
      <span class="agent-state">waiting</span>`;
    el("agent-steps").appendChild(item);
  });
}

function markStep(agentKey, status, label) {
  const node = el(`step-${agentKey}`);
  if (!node) return;
  node.classList.toggle("is-running", status === "running");
  node.classList.toggle("is-done", status === "done");
  node.querySelector(".agent-state").textContent = label;
}

async function startRun(topicOverride) {
  const topic = (topicOverride || el("topic-input").value).trim();
  if (!topic) {
    toast("Enter a topic first");
    return;
  }

  buildStepTracker();
  state.streaming = "";
  el("live-output").innerHTML = "";
  el("progress-status").textContent = "Starting...";
  showView("progress");

  try {
    const { run_id } = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({ topic }),
    });
    state.runId = run_id;
    connectSocket(run_id);
  } catch (error) {
    el("progress-status").textContent = `Could not start: ${error.message}`;
  }
}

function connectSocket(runId) {
  // The backend buffers every event and replays it on connect, so this cannot
  // miss anything emitted between POST /api/run and now — and reconnecting
  // after a refresh recovers the whole run.
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws/pipeline/${runId}`);
  state.socket = socket;

  socket.onmessage = (message) => handleEvent(JSON.parse(message.data));
  socket.onerror = () => { el("progress-status").textContent = "Connection lost."; };
}

function handleEvent(event) {
  switch (event.type) {
    case "agent_start":
      state.streaming = "";
      markStep(event.agent, "running", `running ${event.step}/${event.total}`);
      el("progress-status").textContent =
        `Agent ${event.step} of ${event.total} is working. Output appears as it is written.`;
      break;

    case "agent_token":
      // Token-level streaming: essential when one agent can run for minutes.
      state.streaming += event.delta;
      renderMarkdown(el("live-output"), state.streaming);
      break;

    case "agent_complete":
      markStep(event.agent, "done", "✓ done");
      state.streaming = event.output;
      renderMarkdown(el("live-output"), state.streaming);
      break;

    case "pipeline_complete":
      el("progress-status").textContent = "Complete.";
      loadRun(event.run_id);
      loadHistory();
      break;

    case "cancelled":
      el("progress-status").textContent = "Cancelled — nothing was written to disk.";
      break;

    case "error":
      el("progress-status").textContent =
        `${event.message}${event.hint ? ` → ${event.hint}` : ""}`;
      if (event.completed?.length) {
        el("progress-status").textContent +=
          `  (${event.completed.length} agent(s) finished; retry resumes there)`;
      }
      break;
  }
}

async function cancelRun() {
  if (!state.runId) return;
  await api(`/api/run/${state.runId}/cancel`, { method: "POST" });
  el("progress-status").textContent = "Cancelling...";
}

/* --- Results view ----------------------------------------------------- */

async function loadRun(runId) {
  state.run = await api(`/api/runs/${runId}`);
  state.activeTab = state.run.files[0]?.key || null;
  el("results-topic").textContent = state.run.topic;

  const warning = el("results-warning");
  if (state.run.missing_sections?.length) {
    warning.hidden = false;
    warning.textContent =
      `The writer's output could not be split into: ${state.run.missing_sections.join(", ")}. ` +
      `The full response is in the "Raw Writer Output" tab.`;
  } else {
    warning.hidden = true;
  }

  buildTabs();
  renderActiveTab();
  showView("results");
  markHistoryActive(runId);
}

function buildTabs() {
  el("result-tabs").innerHTML = "";
  state.run.files.forEach((file) => {
    const tab = document.createElement("button");
    tab.className = "tab" + (file.key === state.activeTab ? " is-active" : "");
    tab.setAttribute("role", "tab");
    // Word counts are shown, not enforced — you edit these before publishing.
    tab.innerHTML = `${file.label}<span class="tab-count">${file.word_count}w</span>`;
    tab.onclick = () => {
      state.activeTab = file.key;
      buildTabs();
      renderActiveTab();
    };
    el("result-tabs").appendChild(tab);
  });
}

function activeFile() {
  return state.run?.files.find((file) => file.key === state.activeTab);
}

function renderActiveTab() {
  const file = activeFile();
  renderMarkdown(el("result-panel"), file?.content || "");
}

async function copyActive() {
  const file = activeFile();
  if (!file) return;
  await navigator.clipboard.writeText(file.content);
  toast("Copied!");
}

function downloadActive() {
  const file = activeFile();
  if (!file) return;
  const blob = new Blob([file.content], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = file.filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

/* --- History ---------------------------------------------------------- */

async function loadHistory() {
  const runs = await api("/api/runs");
  const list = el("history-list");
  list.innerHTML = "";

  if (!runs.length) {
    list.innerHTML = `<li class="history-date">No runs yet.</li>`;
    return;
  }

  runs.forEach((run) => {
    const item = document.createElement("li");
    item.className = "history-item";
    item.dataset.runId = run.run_id;
    item.innerHTML = `
      <span>
        <span class="history-topic">${run.topic}</span><br>
        <span class="history-date">${(run.created_at || "").slice(0, 16).replace("T", " ")}</span>
      </span>
      <button class="history-delete" title="Delete">×</button>`;

    item.onclick = () => loadRun(run.run_id);
    item.querySelector(".history-delete").onclick = async (clickEvent) => {
      clickEvent.stopPropagation();
      if (!confirm(`Delete "${run.topic}"? This removes the folder from disk.`)) return;
      await api(`/api/runs/${run.run_id}`, { method: "DELETE" });
      if (state.run?.run_id === run.run_id) showView("home");
      loadHistory();
    };
    list.appendChild(item);
  });
}

function markHistoryActive(runId) {
  document.querySelectorAll(".history-item").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.runId === runId);
  });
}

/* --- Theme ------------------------------------------------------------ */

function applyTheme(theme) {
  document.body.classList.toggle("light", theme === "light");
  localStorage.setItem("seeytu-theme", theme);
}

/* --- Wiring ----------------------------------------------------------- */

el("start-button").onclick = () => startRun();
el("topic-input").onkeydown = (keyEvent) => {
  if (keyEvent.key === "Enter") startRun();
};
el("cancel-button").onclick = cancelRun;
el("copy-button").onclick = copyActive;
el("download-button").onclick = downloadActive;
el("theme-toggle").onclick = () =>
  applyTheme(document.body.classList.contains("light") ? "dark" : "light");
el("settings-button").onclick = () => toast("Settings arrive in phase 2");

applyTheme(localStorage.getItem("seeytu-theme") || "dark");
buildExamples();
buildStepTracker();
checkHealth();
loadHistory();
```

- [ ] **Step 2: Manual verification — the full phase-1 acceptance run**

```bash
python run.py
```

Walk this list, all of it:

1. Header reads "Seeytu-Xamleh" with the tagline; tab title reads "Seeytu — Explore. Learn.
   Publish."; the health line names the resolved model and mode.
2. Click an example chip → the progress view appears with four steps, the first pulsing.
3. Tokens accumulate in the live panel while the Scout works; step 1 turns green and step 2 begins.
4. **Refresh the page mid-run**, then re-open the run — the buffer replays and progress is intact.
5. On completion the results view appears with **7 tabs**, each showing a word count.
6. Copy shows a "Copied!" toast; Download saves the correct `.md`.
7. The history sidebar lists the run with its real topic text, not the slug.
8. Start a second run, then a third — the third reports as queued (cap of 2).
9. Cancel a run → status says nothing was written, and `output/` has no folder for it.
10. Toggle the theme; reload; the choice persists.
11. Narrow the window to tablet width — the sidebar moves to the top and nothing overflows.

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: all passed

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: frontend streaming, results tabs, and history"
```

---

## Task 11: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

It must cover, in this order: what Seeytu-Xamleh is and what the name means; the under-five-minutes
quickstart; both model modes; and the egress note.

````markdown
# Seeytu-Xamleh

*Wolof: "explore and teach."* **Explore. Learn. Publish.**

Feed it a topic. Four agents run in sequence — 🔍 The Scout researches it, 📐 The Architect designs a
project-based learning path, 🔨 The Builder specifies a portfolio-worthy capstone, ✍️ The Publisher
drafts a LinkedIn post, a Substack article, and a Notion reference doc.

Everything is markdown on disk. No database, no accounts, no agent framework.

## Quickstart

```bash
pip install -r requirements.txt
python run.py
```

That opens http://localhost:8000 (or the next free port). You need Ollama running:

```bash
ollama serve
```

**Then pick a model mode:**

| Mode | Setup | Speed | Notes |
|---|---|---|---|
| **Cloud** (default) | `ollama signin` | Minutes per run | Larger models, much better structure-following |
| **Local** | `ollama pull llama3.1:8b` | 40-90 min per run on CPU | Fully offline, nothing leaves the machine |

Cloud models are served through your local Ollama daemon, so the app talks to
`http://localhost:11434` either way. Only `MODEL_NAME` in `config.py` changes.

> **Cloud mode sends data off your machine.** Every agent call transmits the topic and the full
> contents of `profile.md` — your background, skills, and writing voice — to Ollama's servers. Local
> mode transmits nothing. Keep out of `profile.md` anything you would not send to a third party.

## CLI

```bash
python run.py --cli
python run.py --cli --agent research --topic "vector databases for AI"
```

## Make it yours

- **`profile.md`** — who you are. Injected into every agent prompt. Edit this first.
- **`prompts.py`** — the four agent prompts. Edit these when output quality disappoints.
- **`config.py`** — model, temperature, context size, timeouts, concurrency. Every value can be
  overridden by an environment variable of the same name.

## Output

```
output/vector-databases-for-ai-20260809-1405/
├── 01-research-brief.md
├── 02-learning-path.md
├── 03-project-spec.md
├── 04-linkedin-post.md
├── 04-substack-article.md
├── 04-notion-reference.md
├── 04-writer-combined.md    # raw Publisher response, kept as a backup
└── run.json                 # topic, model, timestamps
```

Runs are atomic: if any agent fails, nothing is written, and a retry resumes at the failed agent
rather than starting over. Re-running a topic creates a new timestamped folder, so earlier output is
never overwritten.

## Before you publish

Every file ends with a **Verify before publishing** block listing the claims the model is least sure
about. No model here has web access, so version numbers, URLs, and company examples can be
confidently wrong. Check that block before anything goes out under your name.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```
````

- [ ] **Step 2: Verify the quickstart from scratch**

In a fresh shell: `pip install -r requirements.txt` then `python run.py`. Time it — reaching a
usable browser page must take under five minutes.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README with quickstart, both model modes, and egress note"
```

---

# Phase 2 — Settings, ZIP, and polish

Deliberately coarser: phase 1 will teach you things about real latency and real output quality that
should shape these. Each task still ends with something testable.

## Task 12: Settings panel

Slide-over panel opened by `#settings-button`. Model dropdown grouped into "Cloud" and "Installed
locally" from `GET /api/models`, with the current model marked. Temperature slider (0.0–1.0, step
0.05) writing through `PUT /api/config`. Profile editor — a textarea loaded from `GET /api/profile`,
saved via `PUT /api/profile`, with a save confirmation and a visible note naming `profile.md` as the
file being written. Theme toggle moves in here alongside the header button.
**Verify:** change the model, run a topic, and confirm `run.json` records the new model; edit the
profile and confirm the next run's output reflects the change.

## Task 13: Download All as ZIP

New endpoint `GET /api/runs/{run_id}/archive` streaming an in-memory ZIP via `zipfile` and
`io.BytesIO` — all seven markdown files plus `run.json`, named `<run_id>.zip`. Reuse
`runstore.safe_run_dir` for containment; no new path logic.
**Verify:** download, extract, confirm eight files and that `04-writer-combined.md` is present per
decision #10.

## Task 14: LinkedIn plain-text copy

A "Copy for LinkedIn" button, shown only on the LinkedIn tab, that copies
`textutil.strip_markdown()` output rather than raw markdown — no `#`, no `**`, ready to paste.
`strip_markdown` already exists and is tested from Task 2; expose it through
`GET /api/runs/{run_id}/04-linkedin-post.md?plain=1` or strip client-side, whichever reads cleaner.
**Verify:** paste into a LinkedIn composer and confirm no stray markdown survives.

## Task 15: Retry, queue, and cancel UI

Surface what the backend already supports: a "Retry from failed agent" button on the error state
calling `POST /api/run/{run_id}/retry`; a queued badge when a run waits on the concurrency
semaphore; a "Re-run" button on each history entry that starts a fresh run with the same topic.
**Verify:** force a failure (stop Ollama mid-run), retry, and confirm only the remaining agents run.

## Task 16: Final polish

Keyboard shortcuts (`/` focuses the topic input, `Esc` returns home). Empty and error states for
every view. Focus-visible outlines and `aria-live` on the progress status. A print stylesheet for the
Notion reference. Verify light mode has genuine parity, not just working contrast.
**Verify:** tab through the whole app with the keyboard; check both themes at 768px and 1440px.

---

## Verification (whole project)

**Automated:**

```bash
python -m pytest tests/ -v
```

Covers: slugification against hostile input, writer splitting against six heading variants and
outright garbage, path-traversal rejection on every run-scoped endpoint, atomic-write behavior,
`num_ctx` being set on every model call, idle-timeout semantics, cloud-versus-local resolution,
pipeline ordering and context forwarding, cancel, resume-from-prior-outputs, and the full HTTP
surface with `call_model` stubbed. No test requires Ollama or a network.

**Manual, against real Ollama:**

1. `ollama signin`, then
   `curl http://localhost:11434/api/chat -d '{"model":"gpt-oss:120b-cloud","messages":[{"role":"user","content":"hi"}],"stream":false}'`
   — proves the cloud path independently of the app.
2. `python run.py --cli --agent research --topic "vector databases for AI"` — judge prompt quality
   and measure real latency. Iterate `prompts.py` here.
3. `python run.py` and walk the 11-point acceptance list in Task 10, Step 2.
4. Failure paths: stop Ollama mid-run; request an uninstalled model; sign out and request a cloud
   model; cancel a run; start three runs at once. Each must produce an actionable message, and
   `output/` must contain no partial or `.partial` folders afterward.

**Acceptance criteria:**

- A topic produces 7 markdown files plus `run.json` in one timestamped folder.
- Token output is visible in the browser while an agent is still generating.
- A mid-run refresh recovers full progress.
- A failed run writes nothing and can be retried from the failed agent.
- Every past run is reachable, re-openable, and deletable from the sidebar.
- `pip install -r requirements.txt && python run.py` reaches a working page in under five minutes.

---

## Appendix — analysis carried forward

Condensed from the requirements analysis this plan replaces.

**Top risk — hallucinated specifics under your byline.** The prompts demand real companies,
versions, and doc links while forbidding hedging; no model here has web access, so it fabricates
confidently, and a larger cloud model fabricates less while sounding more authoritative. Decision
#13 (the verify block) is the mitigation, not a fix.

**Latency.** Cloud: single-digit minutes per run. Local on this machine (15.5 GB RAM, Intel iGPU, no
dGPU): 8–23 minutes *per agent* at 3–8 tokens/sec, so 40–90 minutes for a full 8B pipeline — which
is why the timeout is idle-based rather than wall-clock.

**Silent-truncation trap.** Ollama's default context window is small regardless of model capability.
The Publisher's input runs 6k–12k tokens, so without an explicit `num_ctx` the earliest content is
dropped with no error and the Publisher writes about a spec it never saw. `MAX_TOKENS` is
`num_predict` — output length — and is a different knob.

**Security.** Path traversal on `GET /api/runs/{run_id}/{file}` and `DELETE /api/runs/{run_id}` is
the highest-severity item, since one of them deletes; bind to loopback so the unauthenticated API
isn't network-reachable.

**Windows specifics.** `open(path, "w")` uses the ANSI code page, so an em-dash or emoji raises
`UnicodeEncodeError` — every write passes `encoding="utf-8"`. Directory names must avoid `con`,
`prn`, `aux`, `nul`, `com1`–`com9`, `lpt1`–`lpt9`.

**Unverified.** Ollama Cloud pricing and rate limits are absent from the official docs; the
$0 / $20-per-month figures come from third-party sources that disagree above Pro. Confirm at
ollama.com/cloud before relying on the Free tier for a four-agent pipeline.
