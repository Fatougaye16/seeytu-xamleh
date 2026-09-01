"""Local sources the Scout reads before it relies on model recall.

Same principles as runstore: plain files on disk, no database, every
user-supplied identifier contained inside one directory.

Deliberately dependency-free. Markdown, text, pasted notes and fetched URLs
only — PDF, docx and epub need parsers that would take the runtime dependency
list from three to six, tracked separately.
"""

import ipaddress
import json
import re
import socket
import threading
import unicodedata
from contextlib import contextmanager
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

import config
from textutil import slugify, word_count

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".text"}
UNSUPPORTED_SUFFIXES = {".pdf", ".docx", ".epub", ".doc", ".rtf"}
MAX_BYTES = 5 * 1024 * 1024

DROPZONE_HINT = "Text and Markdown files, up to 5 MB each."

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


# Guards every read-modify-write of index.json, and the file write that goes
# with it. Without it two concurrent adds both read the same list, both append
# to their own copy, and the second write silently drops the first resource
# while leaving its markdown orphaned on disk.
_INDEX_LOCK = threading.RLock()


def _save_index(entries: list[dict]) -> None:
    """Write index.json atomically: a torn write would lose the whole library."""
    _root().mkdir(parents=True, exist_ok=True)
    target = _index_path()
    staging = target.with_name(target.name + ".tmp")
    staging.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        staging.replace(target)
    except OSError:
        staging.unlink(missing_ok=True)
        raise


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


MAX_REDIRECTS = 4
# Read granularity for the capped body read. Small enough that the cap is
# enforced promptly, large enough not to churn on a normal-sized article.
CHUNK_BYTES = 64 * 1024


def _read_capped(response) -> bytes:
    """Return the body, refusing anything over MAX_BYTES without buffering it.

    The size has to be enforced *during* the transfer. Reading `response.content`
    first and measuring afterwards means a 2 GB URL is a 2 GB allocation before
    the 5 MB limit is ever consulted — an out-of-memory kill triggered by a
    pasted link.
    """
    # A truthful Content-Length saves reading the body at all. A missing or
    # malformed one proves nothing, so it just falls through to the real read.
    declared = response.headers.get("Content-Length", "")
    if declared.strip().isdigit() and int(declared) > MAX_BYTES:
        raise ValueError("Page is larger than 5 MB.")

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=CHUNK_BYTES):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_BYTES:
            raise ValueError("Page is larger than 5 MB.")
        chunks.append(chunk)
    return b"".join(chunks)


def _assert_public_host(url: str) -> list | None:
    """Refuse URLs that resolve to anything but a public address.

    Returns the vetted getaddrinfo answer so the caller can pin the connection
    to it, or None when the check was skipped via ALLOW_PRIVATE_FETCH.

    A pasted link is untrusted input. Without this the server would happily
    fetch http://169.254.169.254/ (cloud metadata), http://localhost:11434
    (the Ollama daemon) or an intranet host, store the response as a resource,
    and hand it to the Scout — which in cloud mode forwards it to Ollama's
    servers. That is an exfiltration path that needs no malicious user, only a
    link they were given.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https links can be fetched.")
    host = parsed.hostname
    if not host:
        raise ValueError("That URL has no host.")
    if config.ALLOW_PRIVATE_FETCH:
        return None

    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve {host}.") from exc

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        blocked = (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
            or not address.is_global
        )
        if blocked:
            # Kept plain for the reader; the technical reason and the opt-in are
            # documented in the README rather than shouted in a toast.
            raise ValueError(
                f"That link points to a private address on your own network "
                f"({address}), so it wasn't opened."
            )
    return infos


# One fetch at a time. _pinned_dns swaps a module-level global, so overlapping
# fetches would restore each other's resolver. URL adds are rare and
# user-initiated, so serialising them costs nothing.
_FETCH_LOCK = threading.Lock()


@contextmanager
def _pinned_dns(host: str, infos: list | None):
    """Make the transport reuse the answer `_assert_public_host` already vetted.

    Without this the host is resolved twice — once by the check, once by the
    connection — and a DNS answer that changes in between passes the check and
    connects elsewhere. That is DNS rebinding, and it defeats the private-address
    refusal entirely.

    Interception happens at socket.getaddrinfo rather than by rewriting the URL
    to an IP, so the Host header, virtual hosting and TLS certificate matching
    all keep working on the real hostname. Only this one host is answered from
    the pin; everything else falls through to the real resolver.
    """
    if infos is None:
        yield
        return

    real = socket.getaddrinfo

    def pinned(hostname, port, *args, **kwargs):
        if hostname == host:
            return infos
        return real(hostname, port, *args, **kwargs)

    socket.getaddrinfo = pinned
    try:
        yield
    finally:
        socket.getaddrinfo = real


def _fetch_url(url: str) -> tuple[str, str]:
    """Return (title, markdown-ish text) for a page. Fetched once, then stored."""
    # Serialised: _pinned_dns swaps a module-level global for the duration.
    with _FETCH_LOCK:
        return _fetch_url_locked(url)


def _fetch_url_locked(url: str) -> tuple[str, str]:
    # Redirects are followed by hand so every hop is validated. Left to
    # requests, a public URL could redirect straight to a private one.
    current = url
    response = None
    try:
        for _ in range(MAX_REDIRECTS + 1):
            infos = _assert_public_host(current)
            with _pinned_dns(urlparse(current).hostname, infos):
                response = requests.get(
                    current,
                    timeout=(config.CONNECT_TIMEOUT, 30),
                    headers={"User-Agent": f"{config.APP_NAME}/1.0"},
                    allow_redirects=False,
                    # Streamed so the size cap can abort an oversized transfer
                    # instead of measuring it once it is already in memory.
                    stream=True,
                )
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                # Streamed responses hold their connection until closed, and
                # only the final hop's body is ever read.
                response.close()
                if not location:
                    raise ValueError("Redirect without a destination.")
                current = urljoin(current, location)
                continue
            try:
                response.raise_for_status()
            except requests.RequestException:
                response.close()
                raise
            break
        else:
            raise ValueError(f"Too many redirects (more than {MAX_REDIRECTS}).")
    except requests.RequestException as exc:
        raise ValueError(f"Could not fetch {url}: {exc}") from exc

    try:
        raw = _read_capped(response)
    except requests.RequestException as exc:
        raise ValueError(f"Could not fetch {url}: {exc}") from exc
    finally:
        response.close()

    # `response.text` is unavailable on a streamed body, so decode by hand from
    # the charset the server declared, falling back to UTF-8.
    html = raw.decode(response.encoding or "utf-8", errors="replace")

    extractor = _TextExtractor()
    extractor.feed(html)
    text = extractor.text()
    if not text:
        raise ValueError("Nothing readable found at that URL.")
    return extractor.title or url, text


def add(kind: str, name: str, content: str | None = None) -> dict:
    """Add a file, url or note. Returns the new index entry.

    The body is resolved first and the index touched second, so a URL fetch —
    up to 30 seconds — never holds the index lock and blocks the library.
    """
    now = datetime.now()

    if kind == "file":
        suffix = Path(name).suffix.lower()
        if suffix in UNSUPPORTED_SUFFIXES:
            raise UnsupportedResource(
                f"{suffix.lstrip('.').upper()} files aren't supported yet — "
                "text and Markdown files only for now."
            )
        if suffix and suffix not in TEXT_SUFFIXES:
            raise UnsupportedResource(
                f"{suffix} files aren't supported — text and Markdown files only."
            )
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

    words = word_count(body)
    # Built by hand rather than with %-d, which is not portable to Windows.
    added = f"{now:%b} {now.day}"

    # One writer at a time from here on: minting an id, writing the file and
    # appending to the index have to happen as a unit or ids collide and
    # entries go missing.
    with _INDEX_LOCK:
        entries = _load_index()
        resource_id = _mint_id(label or kind, {entry["id"] for entry in entries})
        path = safe_resource_path(resource_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

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
    with _INDEX_LOCK:
        entries = _load_index()
        for entry in entries:
            if entry["id"] == resource_id:
                entry["enabled"] = not entry["enabled"]
                _save_index(entries)
                return entry
    raise KeyError(resource_id)


def remove(resource_id: str) -> None:
    path = safe_resource_path(resource_id)
    with _INDEX_LOCK:
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
