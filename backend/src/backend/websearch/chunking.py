"""Text cleaning and chunking for the RAG pipeline. Source-agnostic: works on any fetched document."""

import re

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 200

# Fields copied from a document onto each chunk's metadata (chromadb accepts only scalar values).
_METADATA_FIELDS = ("title", "published", "doi", "source", "content_type", "pdf_url", "landing_page_url")


def clean_text(text: str) -> str:
    """Normalize extracted text without destroying non-ASCII content (accents, Greek, math)."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f�]", " ", text)
    # Re-join words hyphenated across line breaks ("retrie-\nval" -> "retrieval").
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
    """Split text into overlapping fixed-size character chunks."""
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    if not text:
        return []
    step = chunk_size - overlap
    return [text[i : i + chunk_size] for i in range(0, len(text), step)]


def chunk_document(
    document: dict, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP
) -> list[dict]:
    """
    Turn one fetched document (from any source) into chunks ready for embedding.

    Returns [{"id", "text", "metadata"}], where the id is stable per document + position
    so re-ingesting the same paper overwrites rather than duplicates.
    """
    text = clean_text(document.get("content") or "")
    metadata = {k: document[k] for k in _METADATA_FIELDS if document.get(k) is not None}
    if document.get("authors"):
        metadata["authors"] = ", ".join(document["authors"])

    return [
        {
            "id": f"{document['id']}#{i}",
            "text": chunk,
            "metadata": {**metadata, "document_id": document["id"], "chunk_index": i},
        }
        for i, chunk in enumerate(chunk_text(text, chunk_size, overlap))
    ]
