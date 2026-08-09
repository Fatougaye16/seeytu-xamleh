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
    # Shown to readers, so named for them rather than for the pipeline.
    "combined": "Writer's Full Draft",
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
