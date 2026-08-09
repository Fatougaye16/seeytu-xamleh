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
    # Apostrophes are dropped rather than becoming separators, so "Ollama's API"
    # slugifies to "ollamas-api" and not "ollama-s-api".
    ascii_only = re.sub(r"['’ʼ]", "", ascii_only)
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
