"""The agent engine.

`call_model()` is the ONLY function in this project that talks to Ollama. To
move to the Claude API or Gemini later, reimplement that one function and leave
everything else alone.
"""

import json
from collections.abc import Callable

import requests

import config

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
                "Sign in to use cloud models: ollama signin",
            )
        return OllamaError(
            f"Model '{model}' is not installed.", f"Download it with: ollama pull {model}"
        )
    if "unauthor" in lowered or "forbidden" in lowered or "401" in lowered:
        return OllamaError(
            "Ollama rejected the request as unauthenticated.",
            "Sign in with: ollama signin  (or set OLLAMA_API_KEY)",
        )
    if ("rate" in lowered and "limit" in lowered) or "429" in lowered or "quota" in lowered:
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
        raise OllamaError("Cannot reach Ollama.", "Start it with: ollama serve") from exc
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
