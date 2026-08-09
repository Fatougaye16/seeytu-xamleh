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
