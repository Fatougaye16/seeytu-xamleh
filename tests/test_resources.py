import pytest

import config
import prompts
import resources


@pytest.fixture(autouse=True)
def isolated_library(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESOURCES_DIR", tmp_path / "resources_data")
    yield


def test_add_markdown_file_is_indexed_and_enabled():
    entry = resources.add("file", "notes/retrieval.md", "# Notes\nchunking matters a lot")
    assert entry["kind"] == "md"
    assert entry["enabled"] is True
    assert entry["words"] > 0
    assert resources.safe_resource_path(entry["id"]).is_file()
    assert [item["id"] for item in resources.listing()] == [entry["id"]]


def test_add_text_file_gets_the_txt_badge():
    assert resources.add("file", "transcript.txt", "hello there")["kind"] == "txt"


def test_add_note_stores_pasted_text():
    entry = resources.add("note", "Team sync", "We agreed to ship the retriever first.")
    assert entry["kind"] == "txt"
    assert "retriever" in resources.safe_resource_path(entry["id"]).read_text(
        encoding="utf-8"
    )


def test_unsupported_binary_types_are_refused_clearly():
    for name in ("paper.pdf", "spec.docx", "book.epub"):
        with pytest.raises(resources.UnsupportedResource) as excinfo:
            resources.add("file", name, "irrelevant")
        message = str(excinfo.value).lower()
        # Names the format and says what does work, without naming a library.
        assert "supported" in message
        assert name.split(".")[-1] in message
        assert resources.listing() == []


def test_empty_content_is_refused():
    with pytest.raises(ValueError):
        resources.add("note", "Empty", "   ")


def test_oversized_content_is_refused():
    with pytest.raises(ValueError):
        resources.add("note", "Huge", "x" * (resources.MAX_BYTES + 1))


def test_non_ascii_content_round_trips():
    entry = resources.add("note", "Unicode", "em—dash, ’quote’, emoji 🚀")
    body = resources.safe_resource_path(entry["id"]).read_text(encoding="utf-8")
    assert "🚀" in body


def test_ids_disambiguate_when_names_collide():
    first = resources.add("note", "Same name", "one")
    second = resources.add("note", "Same name", "two")
    assert first["id"] != second["id"]
    assert second["id"].endswith("-2")


def test_toggle_flips_enabled():
    entry = resources.add("note", "Toggle me", "content")
    assert resources.toggle(entry["id"])["enabled"] is False
    assert resources.toggle(entry["id"])["enabled"] is True


def test_toggle_unknown_id_raises_keyerror():
    with pytest.raises(KeyError):
        resources.toggle("nope-not-here")


def test_remove_deletes_the_stored_file():
    entry = resources.add("note", "Delete me", "content")
    path = resources.safe_resource_path(entry["id"])
    resources.remove(entry["id"])
    assert not path.exists()
    assert resources.listing() == []


@pytest.mark.parametrize(
    "resource_id",
    ["../secrets", "..", "a/b", "C:/Windows", "", "a\\b"],
)
def test_path_traversal_is_rejected(resource_id):
    with pytest.raises(resources.UnsafeResource):
        resources.safe_resource_path(resource_id)


def test_hostile_name_slugifies_to_a_safe_id():
    entry = resources.add("note", '<img src=x onerror=alert(1)> "q"', "body")
    assert "<" not in entry["id"] and '"' not in entry["id"] and "/" not in entry["id"]


def test_enabled_context_includes_only_enabled_sources():
    keep = resources.add("note", "Keep", "KEEP-MARKER text")
    drop = resources.add("note", "Drop", "DROP-MARKER text")
    resources.toggle(drop["id"])

    context = resources.enabled_context()
    assert "KEEP-MARKER" in context
    assert "DROP-MARKER" not in context
    assert "SOURCE: Keep" in context
    assert keep["name"] in context


def test_enabled_context_is_empty_with_nothing_enabled():
    entry = resources.add("note", "Only one", "text")
    resources.toggle(entry["id"])
    assert resources.enabled_context() == ""


def test_enabled_context_respects_its_character_budget():
    resources.add("note", "Big one", "y" * 5000)
    resources.add("note", "Big two", "z" * 5000)
    context = resources.enabled_context(max_chars=2000)
    assert len(context) <= 2000


def _public_dns(monkeypatch, address="93.184.216.34"):
    """Pretend every hostname resolves to a public address."""
    monkeypatch.setattr(
        resources.socket, "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", (address, 443))],
    )


def _resolving_to(monkeypatch, mapping):
    """Resolve specific hostnames to specific addresses."""
    def fake(host, *args, **kwargs):
        return [(2, 1, 6, "", (mapping[host], 443))]
    monkeypatch.setattr(resources.socket, "getaddrinfo", fake)


@pytest.mark.parametrize(
    "address,label",
    [
        ("127.0.0.1", "loopback"),
        ("169.254.169.254", "cloud metadata / link-local"),
        ("10.0.0.5", "RFC1918"),
        ("192.168.1.10", "RFC1918"),
        ("172.16.4.4", "RFC1918"),
        ("0.0.0.0", "unspecified"),
        ("224.0.0.1", "multicast"),
        ("::1", "IPv6 loopback"),
        ("fd00::1", "IPv6 unique-local"),
    ],
)
def test_fetch_refuses_non_public_addresses(monkeypatch, address, label):
    """SSRF guard: a pasted link must not reach the metadata service or intranet.

    Asserts the security property — refused, and nothing stored — rather than the
    wording, so rewriting user-facing copy cannot quietly gut a security test.
    """
    _public_dns(monkeypatch, address)
    monkeypatch.setattr(config, "ALLOW_PRIVATE_FETCH", False)

    def must_not_be_called(*args, **kwargs):
        raise AssertionError(f"a request was made to a {label} address")

    monkeypatch.setattr(resources.requests, "get", must_not_be_called)

    with pytest.raises(ValueError) as excinfo:
        resources.add("url", "https://looks-harmless.example/page")
    assert "private address" in str(excinfo.value).lower(), label
    assert resources.listing() == [], f"{label} response must not be stored"


def test_fetch_allows_private_addresses_only_when_explicitly_enabled(monkeypatch):
    _public_dns(monkeypatch, "127.0.0.1")
    monkeypatch.setattr(config, "ALLOW_PRIVATE_FETCH", True)

    html = b"<html><title>Local</title><body><p>intranet doc</p></body></html>"
    monkeypatch.setattr(
        resources.requests, "get", lambda *a, **k: _StreamedResponse([html])
    )
    entry = resources.add("url", "http://localhost:8080/doc")
    assert entry["name"] == "Local"


def test_a_redirect_to_a_private_address_is_refused(monkeypatch):
    """The teeth of the issue: the first hop is public, the second is not."""
    _resolving_to(monkeypatch, {
        "public.example": "93.184.216.34",
        "metadata.evil": "169.254.169.254",
    })
    monkeypatch.setattr(config, "ALLOW_PRIVATE_FETCH", False)

    def redirect_to_metadata(*args, **kwargs):
        hop = _StreamedResponse(
            [b""], headers={"Location": "http://metadata.evil/latest/meta-data/"}
        )
        hop.is_redirect = True
        return hop

    monkeypatch.setattr(resources.requests, "get", redirect_to_metadata)
    with pytest.raises(ValueError) as excinfo:
        resources.add("url", "https://public.example/start")
    assert "private address" in str(excinfo.value).lower()
    assert resources.listing() == [], "the redirected response must not be stored"


def test_redirects_are_not_followed_by_requests_itself(monkeypatch):
    """allow_redirects must be False, or requests would bypass the per-hop check."""
    _public_dns(monkeypatch)
    seen = {}

    html = b"<html><title>T</title><body><p>body text</p></body></html>"

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return _StreamedResponse([html])

    monkeypatch.setattr(resources.requests, "get", fake_get)
    resources.add("url", "https://example.dev/page")
    assert seen["allow_redirects"] is False


def test_a_redirect_loop_is_capped(monkeypatch):
    _public_dns(monkeypatch)

    def redirect_forever(*args, **kwargs):
        hop = _StreamedResponse([b""], headers={"Location": "https://example.dev/again"})
        hop.is_redirect = True
        return hop

    monkeypatch.setattr(resources.requests, "get", redirect_forever)
    with pytest.raises(ValueError) as excinfo:
        resources.add("url", "https://example.dev/start")
    assert "Too many redirects" in str(excinfo.value)


def test_unresolvable_host_is_reported_clearly(monkeypatch):
    def boom(*args, **kwargs):
        raise resources.socket.gaierror("nodename nor servname provided")

    monkeypatch.setattr(resources.socket, "getaddrinfo", boom)
    with pytest.raises(ValueError) as excinfo:
        resources.add("url", "https://does-not-exist.invalid/x")
    assert "Could not resolve" in str(excinfo.value)


def test_url_extraction_turns_html_into_readable_text(monkeypatch):
    html = """
    <html><head><title>Hybrid search</title><style>.a{color:red}</style></head>
    <body><nav>skip me</nav><h1>Hybrid search</h1>
    <p>BM25 plus dense retrieval beats either alone.</p>
    <script>alert('no')</script>
    <p>Rerankers recover most of the loss.</p></body></html>
    """

    _public_dns(monkeypatch)
    monkeypatch.setattr(
        resources.requests,
        "get",
        lambda *a, **k: _StreamedResponse([html.encode("utf-8")]),
    )
    entry = resources.add("url", "https://example.dev/hybrid")

    body = resources.safe_resource_path(entry["id"]).read_text(encoding="utf-8")
    assert entry["kind"] == "url"
    assert entry["name"] == "Hybrid search"
    assert "BM25 plus dense" in body
    assert "alert" not in body, "script contents must not survive extraction"
    assert "color:red" not in body, "style contents must not survive extraction"
    assert "skip me" not in body, "nav is chrome, not content"


def test_non_http_urls_are_refused():
    with pytest.raises(ValueError):
        resources.add("url", "file:///etc/passwd")


def test_scout_prompt_carries_sources_and_other_agents_do_not():
    sources = "--- SOURCE: My notes ---\nchunking matters"
    scout = prompts.user_prompt("scout", "rag", {}, sources)
    assert "chunking matters" in scout
    assert "prefer them over recall" in scout

    # Later agents inherit the library through the Scout's brief, not directly.
    architect = prompts.user_prompt("architect", "rag", {"research": "brief"}, sources)
    assert "chunking matters" not in architect


def test_scout_prompt_unchanged_when_there_are_no_sources():
    assert "THE USER'S OWN SOURCES" not in prompts.user_prompt("scout", "rag", {}, "")


# --- Fetch size cap ------------------------------------------------------

class _StreamedResponse:
    """A response that hands its body over in chunks, like requests does."""

    is_redirect = False
    is_permanent_redirect = False
    encoding = "utf-8"

    def __init__(self, chunks, headers=None, on_pull=None):
        self._chunks = chunks
        self.headers = headers or {}
        self._on_pull = on_pull
        self.closed = False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=None):
        for chunk in self._chunks:
            if self._on_pull:
                self._on_pull(chunk)
            yield chunk

    def close(self):
        self.closed = True


def test_an_oversized_page_is_refused_without_buffering_all_of_it(monkeypatch):
    """The cap must stop the transfer, not measure it after it landed in RAM.

    Checking len(response.content) only works once the whole body is already
    in memory, so a 50 MB URL is a 50 MB allocation before the 5 MB limit is
    ever consulted.
    """
    _public_dns(monkeypatch)
    pulled = []
    body = [b"x" * (1024 * 1024) for _ in range(50)]
    response = _StreamedResponse(body, on_pull=pulled.append)
    monkeypatch.setattr(resources.requests, "get", lambda *a, **k: response)

    with pytest.raises(ValueError, match="larger than 5 MB"):
        resources.add("url", "https://example.dev/huge")

    assert len(pulled) <= 6, (
        f"read {len(pulled)} MB before giving up; the cap is 5 MB"
    )


def test_a_declared_oversize_content_length_is_refused_before_the_body_is_read(monkeypatch):
    _public_dns(monkeypatch)

    def must_not_be_read(chunk):
        raise AssertionError("body was read despite an oversize Content-Length")

    response = _StreamedResponse(
        [b"x"],
        headers={"Content-Length": str(6 * 1024 * 1024)},
        on_pull=must_not_be_read,
    )
    monkeypatch.setattr(resources.requests, "get", lambda *a, **k: response)

    with pytest.raises(ValueError, match="larger than 5 MB"):
        resources.add("url", "https://example.dev/declared-huge")


def test_the_body_is_requested_as_a_stream(monkeypatch):
    _public_dns(monkeypatch)
    captured = {}
    html = b"<html><title>Streamed</title><body><p>hello there</p></body></html>"

    def fake_get(url, **kwargs):
        captured.update(kwargs)
        return _StreamedResponse([html])

    monkeypatch.setattr(resources.requests, "get", fake_get)
    entry = resources.add("url", "https://example.dev/page")

    assert captured["stream"] is True
    assert entry["name"] == "Streamed"


def test_a_page_under_the_cap_still_reads_normally(monkeypatch):
    _public_dns(monkeypatch)
    html = b"<html><title>Small</title><body><p>BM25 plus dense retrieval.</p></body></html>"
    monkeypatch.setattr(
        resources.requests, "get", lambda *a, **k: _StreamedResponse([html])
    )

    entry = resources.add("url", "https://example.dev/small")
    body = resources.safe_resource_path(entry["id"]).read_text(encoding="utf-8")
    assert "BM25 plus dense retrieval." in body


def test_a_redirect_response_is_closed_before_the_next_hop(monkeypatch):
    """A streamed response holds its connection open until it is closed.

    Only the final hop's body is read, so every redirect on the way would sit
    on a connection until the garbage collector happened to reclaim it.
    """
    _public_dns(monkeypatch)
    hop = _StreamedResponse([b""], headers={"Location": "https://example.dev/final"})
    hop.is_redirect = True
    final = _StreamedResponse(
        [b"<html><title>Final</title><body><p>arrived at last</p></body></html>"]
    )
    queue = [hop, final]
    monkeypatch.setattr(resources.requests, "get", lambda *a, **k: queue.pop(0))

    entry = resources.add("url", "https://example.dev/start")

    assert entry["name"] == "Final"
    assert hop.closed, "the redirect hop must be closed before the next request"
    assert final.closed, "the final response must be closed once read"


def test_a_failed_status_still_releases_the_connection(monkeypatch):
    _public_dns(monkeypatch)

    class Failing(_StreamedResponse):
        def raise_for_status(self):
            raise resources.requests.HTTPError("404 Not Found")

    response = Failing([b""])
    monkeypatch.setattr(resources.requests, "get", lambda *a, **k: response)

    with pytest.raises(ValueError, match="Could not fetch"):
        resources.add("url", "https://example.dev/missing")
    assert response.closed, "a non-2xx response must be closed too"
