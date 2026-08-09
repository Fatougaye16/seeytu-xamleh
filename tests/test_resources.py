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
        assert "parser" in str(excinfo.value) or "Unsupported" in str(excinfo.value)


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


def test_url_extraction_turns_html_into_readable_text(monkeypatch):
    html = """
    <html><head><title>Hybrid search</title><style>.a{color:red}</style></head>
    <body><nav>skip me</nav><h1>Hybrid search</h1>
    <p>BM25 plus dense retrieval beats either alone.</p>
    <script>alert('no')</script>
    <p>Rerankers recover most of the loss.</p></body></html>
    """

    class FakeResponse:
        content = html.encode("utf-8")
        text = html

        def raise_for_status(self):
            pass

    monkeypatch.setattr(resources.requests, "get", lambda *a, **k: FakeResponse())
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
