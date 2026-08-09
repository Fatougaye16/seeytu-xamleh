# Seeytu-Xamleh

*Wolof: "explore and teach."* **Explore. Learn. Publish.**

Feed it a topic. Four agents run in sequence — 🔍 **The Scout** researches it, 📐 **The Architect**
designs a project-based learning path, 🔨 **The Builder** specifies a portfolio-worthy capstone,
✍️ **The Publisher** drafts a LinkedIn post, a Substack article, and a Notion reference doc.

Everything is markdown on disk. No database, no accounts, no agent framework, no build step.

## Quickstart

```bash
pip install -r requirements.txt
python run.py
```

That opens http://localhost:8000 — or the next free port, printed on startup. You need Ollama
running:

```bash
ollama serve
```

Then pick a model mode.

### Cloud (default, recommended)

```bash
ollama signin
```

Cloud models run on Ollama's GPUs and are served **through your local daemon**, so the app talks to
`http://localhost:11434` either way — only `MODEL_NAME` changes.

### Local (fully offline)

```bash
ollama pull llama3.1:8b
```

If the configured model isn't installed, startup falls back to the best local model you have and
prints the exact command to get the right one.

### Measured on a CPU-only laptop (15.5 GB RAM, no dedicated GPU)

| | Cloud (`gpt-oss:120b`) | Local (`llama3.2`, 3B) |
|---|---|---|
| Throughput | ~44 tokens/sec | ~3.5 tokens/sec |
| Full four-agent run | **~2.5 minutes** | ~78 minutes (projected) |
| Named the real vector DBs | Pinecone, Milvus, Weaviate, Qdrant | called Bigtable a vector database |

Local works and is genuinely private. Cloud is what makes this pleasant to use.

> **Cloud mode sends data off your machine.** Every agent call transmits the topic and the full
> contents of `profile.md` — your background, skills, and writing voice — to Ollama's servers.
> Local mode transmits nothing. Keep out of `profile.md` anything you would not send to a third
> party.

## CLI

```bash
python run.py --cli
python run.py --cli --agent research --topic "vector databases for AI"
```

Agent names: `research`, `curriculum`, `project`, `writer` (or `scout`, `architect`, `builder`,
`publisher`).

## Make it yours

Three files, in the order you'll want them:

- **`profile.md`** — who you are. Injected into every agent prompt. **Edit this first**; it is the
  single biggest lever on how much the output sounds like you.
- **`prompts.py`** — the four agent prompts. Edit these when output quality disappoints. They are
  the product; everything else is plumbing.
- **`config.py`** — model, temperature, context size, timeouts, concurrency. Every value can be
  overridden by an environment variable of the same name:

```bash
MODEL_NAME=llama3.2:latest MAX_TOKENS=2000 python run.py --cli --topic "..."
```

## Output

```
output/vector-databases-for-ai-20260809-1556/
├── 01-research-brief.md
├── 02-learning-path.md
├── 03-project-spec.md
├── 04-linkedin-post.md
├── 04-substack-article.md
├── 04-notion-reference.md
├── 04-writer-combined.md    # raw Publisher response, kept as a backup
└── run.json                 # topic, model, mode, timestamps
```

**Runs are atomic.** If any agent fails, nothing is written — `output/` never holds a half-finished
run. Completed agents are kept in memory, so a retry resumes at the agent that failed instead of
starting over.

**Re-running a topic creates a new timestamped folder**, so earlier output is never overwritten and
you can compare results across prompt revisions.

## Before you publish

Every draft ends with a **Verify before publishing** block listing the claims the model is least
sure about. This is not decoration. No model here has web access, so version numbers, URLs, and
company examples can be confidently wrong.

A real example from a test run — the model flagged these itself:

> - Verify Stripe "Payments 2.0" roadmap announced Kafka-based fraud scoring in 2023.
> - Verify sub-millisecond latency claim for Stripe's fraud pipeline.

Both look invented. That is the block doing its job. **Read it before anything goes out under your
name.**

## Keyboard

| Key | Action |
|---|---|
| `/` | focus the topic input |
| `Enter` | start the run |
| `Esc` | back to home |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Nothing in the suite needs Ollama or a network — `call_model` is stubbed throughout, which is what
keeps the fragile parts (writer splitting, slugification, path containment) cheap to verify.

## How it fits together

```
run.py       entry point: CLI mode, or serve the web UI on a free port
  agents.py    call_model() — the ONLY code that talks to Ollama — plus the 4-agent pipeline
    prompts.py   the four system prompts + profile injection
    runstore.py  atomic writes, path containment, run listing
    textutil.py  slugify, writer-output splitting, word counts
  server.py    FastAPI: 13 endpoints, run registry, progress WebSocket
    static/      vanilla HTML/CSS/JS, vendored marked + DOMPurify + highlight.js
```

`call_model()` is deliberately the single chokepoint. To move to the Claude API or Gemini, rewrite
that one function and leave everything else alone.
