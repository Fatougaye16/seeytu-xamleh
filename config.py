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
#
# Reasoning models (gpt-oss among them) spend part of this budget on chain of
# thought before the answer begins, so the ceiling must cover thinking *and*
# answer. At 4096 a long prompt can burn the whole budget reasoning and return
# nothing at all.
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8192"))
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
# Local sources the Scout reads before relying on model recall.
RESOURCES_DIR = Path(os.getenv("RESOURCES_DIR", "resources_data")).resolve()
# URL fetching refuses private, loopback and link-local addresses by default:
# a pasted link is untrusted input, and fetched pages end up in the Scout's
# prompt and therefore, in cloud mode, at a third party. Set to 1 only if you
# deliberately want to index an intranet or a local dev server.
ALLOW_PRIVATE_FETCH = os.getenv("ALLOW_PRIVATE_FETCH", "").strip() in {"1", "true", "yes"}
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
