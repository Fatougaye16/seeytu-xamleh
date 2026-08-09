"""Local sources the Scout reads before it relies on model recall.

Same principles as runstore: plain files on disk, no database, every
user-supplied identifier contained inside one directory.

Deliberately dependency-free. Markdown, text, pasted notes and fetched URLs
only — PDF, docx and epub need parsers that would take the runtime dependency
list from three to six, tracked separately.
"""

import json
import re
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import requests

import config
from textutil import slugify, word_count

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".text"}
UNSUPPORTED_SUFFIXES = {".pdf", ".docx", ".epub", ".doc", ".rtf"}
MAX_BYTES = 5 * 1024 * 1024

DROPZONE_HINT = "Markdown and text files. 5 MB per file."

_ID = re.compile(r"^[a-z0-9][a-z0-9\-]{0,119}$")


class UnsafeResource(ValueError):
    """Invalid resource id, or one that escapes the resources directory."""


class UnsupportedResource(ValueError):
    """A file type this build cannot read."""


def _root() -> Path:
    return Path(config.RESOURCES_DIR)


def _index_path() -> Path:
    return _root() / "index.json"


def safe_resource_path(resource_id: str) -> Path:
    """Resolve a resource's stored markdown, refusing anything outside the root."""
    if not isinstance(resource_id, str) or not _ID.match(resource_id):
        raise UnsafeResource(f"Invalid resource id: {resource_id!r}")
    root = _root().resolve()
    candidate = (root / f"{resource_id}.md").resolve()
    if candidate.parent != root:
        raise UnsafeResource(f"Resource id escapes the library: {resource_id!r}")
    return candidate


def _load_index() -> list[dict]:
    path = _index_path()
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _save_index(entries: list[dict]) -> None:
    _root().mkdir(parents=True, exist_ok=True)
    _index_path().write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _mint_id(name: str, existing: set[str]) -> str:
    base = slugify(name, max_len=48)
    candidate, suffix = base, 1
    while candidate in existing:
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


class _TextExtractor(HTMLParser):
    """Minimal HTML-to-text. Enough for an article, and needs no dependency."""

    SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer"}
    BLOCK = {"p", "div", "section", "article", "br", "li", "tr",
             "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skipping = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skipping += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag in {"h1", "h2", "h3"}:
            self.parts.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skipping:
            self._skipping -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()
        if self._skipping or not data.strip():
            return
        self.parts.append(data.strip() + " ")

    def text(self) -> str:
        joined = "".join(self.parts)
        joined = re.sub(r"[ \t]+", " ", joined)
        return re.sub(r"\n{3,}", "\n\n", joined).strip()


def _fetch_url(url: str) -> tuple[str, str]:
    """Return (title, markdown-ish text) for a page. Fetched once, then stored."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Only http and https links can be fetched.")
    try:
        response = requests.get(
            url,
            timeout=(config.CONNECT_TIMEOUT, 30),
            headers={"User-Agent": f"{config.APP_NAME}/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Could not fetch {url}: {exc}") from exc

    if len(response.content) > MAX_BYTES:
        raise ValueError("Page is larger than 5 MB.")

    extractor = _TextExtractor()
    extractor.feed(response.text)
    text = extractor.text()
    if not text:
        raise ValueError("Nothing readable found at that URL.")
    return extractor.title or url, text


def add(kind: str, name: str, content: str | None = None) -> dict:
    """Add a file, url or note. Returns the new index entry."""
    entries = _load_index()
    existing = {entry["id"] for entry in entries}
    now = datetime.now()

    if kind == "file":
        suffix = Path(name).suffix.lower()
        if suffix in UNSUPPORTED_SUFFIXES:
            raise UnsupportedResource(
                f"{suffix} files need a parser this build does not ship. "
                "Markdown and text only for now."
            )
        if suffix and suffix not in TEXT_SUFFIXES:
            raise UnsupportedResource(f"Unsupported file type: {suffix}")
        body = content or ""
        label = name
        badge = "md" if suffix in {".md", ".markdown"} else "txt"
    elif kind == "url":
        label, body = _fetch_url(name.strip())
        badge = "url"
    elif kind == "note":
        body = content or ""
        label = name
        badge = "txt"
    else:
        raise ValueError(f"Unknown resource kind: {kind!r}")

    body = unicodedata.normalize("NFC", body).strip()
    if not body:
        raise ValueError("Nothing to store — the content was empty.")
    if len(body.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Content is larger than 5 MB.")

    resource_id = _mint_id(label or kind, existing)
    safe_resource_path(resource_id).parent.mkdir(parents=True, exist_ok=True)
    safe_resource_path(resource_id).write_text(body, encoding="utf-8")

    words = word_count(body)
    # Built by hand rather than with %-d, which is not portable to Windows.
    added = f"{now:%b} {now.day}"
    entry = {
        "id": resource_id,
        "kind": badge,
        "name": label,
        "source": name if kind == "url" else None,
        "words": words,
        "added_at": now.isoformat(timespec="seconds"),
        "enabled": True,
        "meta": f"{words:,} words · added {added}",
    }
    entries.append(entry)
    _save_index(entries)
    return entry


def listing() -> list[dict]:
    return _load_index()


def toggle(resource_id: str) -> dict:
    safe_resource_path(resource_id)  # validate before touching the index
    entries = _load_index()
    for entry in entries:
        if entry["id"] == resource_id:
            entry["enabled"] = not entry["enabled"]
            _save_index(entries)
            return entry
    raise KeyError(resource_id)


def remove(resource_id: str) -> None:
    path = safe_resource_path(resource_id)
    entries = [entry for entry in _load_index() if entry["id"] != resource_id]
    _save_index(entries)
    if path.is_file():
        path.unlink()


def enabled_context(max_chars: int = 24_000) -> str:
    """Enabled sources, concatenated for injection into the Scout's prompt.

    Budgeted: the Scout's context also has to hold its own instructions, and a
    large library would otherwise silently push them out.
    """
    chunks: list[str] = []
    used = 0
    for entry in _load_index():
        if not entry.get("enabled"):
            continue
        try:
            body = safe_resource_path(entry["id"]).read_text(encoding="utf-8")
        except (OSError, UnsafeResource):
            continue
        header = f"--- SOURCE: {entry['name']} ---\n"
        room = max_chars - used - len(header)
        if room <= 200:
            break
        chunks.append(header + body[:room])
        used += len(header) + min(len(body), room)
    return "\n\n".join(chunks)
