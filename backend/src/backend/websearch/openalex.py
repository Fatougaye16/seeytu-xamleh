"""OpenAlex client: search works and fetch open-access full text in memory (nothing persisted)."""

import asyncio
import io
import os

import httpx
from pypdf import PdfReader

OPENALEX_API_URL = "https://api.openalex.org/works"

# Optional: an API key raises your quota; an email puts you in OpenAlex's "polite pool".
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY")
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL")

# PDFs are hosted by many different publishers/repositories, so moderate concurrency is fine.
_PDF_CONCURRENCY = asyncio.Semaphore(4)

_SELECT_FIELDS = ",".join([
    "id", "doi", "display_name", "publication_date", "authorships",
    "abstract_inverted_index", "best_oa_location", "open_access",
])


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the plain text."""
    if not inverted_index:
        return ""
    positions = [(pos, word) for word, idxs in inverted_index.items() for pos in idxs]
    return " ".join(word for _, word in sorted(positions))


def _parse_work(work: dict) -> dict:
    best_oa = work.get("best_oa_location") or {}
    return {
        "id": work.get("id"),
        "doi": work.get("doi"),
        "title": work.get("display_name") or "",
        "summary": _reconstruct_abstract(work.get("abstract_inverted_index")),
        "published": work.get("publication_date"),
        "authors": [
            a["author"]["display_name"]
            for a in work.get("authorships") or []
            if a.get("author", {}).get("display_name")
        ],
        "pdf_url": best_oa.get("pdf_url"),
        "landing_page_url": best_oa.get("landing_page_url") or (work.get("open_access") or {}).get("oa_url"),
        "source": "openalex",
    }


async def search(
    client: httpx.AsyncClient, query: str, max_results: int, open_access_only: bool = True
) -> list[dict]:
    params = {
        "search": query,
        "per_page": max_results,
        "select": _SELECT_FIELDS,
    }
    if open_access_only:
        params["filter"] = "open_access.is_oa:true"
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    if OPENALEX_EMAIL:
        params["mailto"] = OPENALEX_EMAIL

    response = await client.get(OPENALEX_API_URL, params=params)
    response.raise_for_status()
    return [_parse_work(w) for w in response.json().get("results", [])]


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = (page.extract_text() or "" for page in reader.pages)
    return "\n\n".join(p.strip() for p in pages if p.strip())


async def fetch_full_text(client: httpx.AsyncClient, pdf_url: str) -> str:
    """Download the PDF into memory and return its raw extracted text."""
    async with _PDF_CONCURRENCY:
        response = await client.get(pdf_url)
    response.raise_for_status()
    # Some publishers answer a "pdf_url" with an HTML landing page or captcha.
    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"not a PDF (content-type: {response.headers.get('content-type')})")
    return await asyncio.to_thread(_extract_pdf_text, response.content)


async def search_with_content(query: str, max_results: int, open_access_only: bool = True) -> list[dict]:
    """Search OpenAlex, then fetch each work's full text; falls back to the abstract."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": "seeytu-xamleh-rag/0.1"},
    ) as client:
        works = await search(client, query, max_results, open_access_only)

        async def enrich(work: dict) -> dict:
            error = "no pdf link"
            if work["pdf_url"]:
                try:
                    text = await fetch_full_text(client, work["pdf_url"])
                    if text.strip():
                        return {**work, "content": text, "content_type": "full_text", "error": None}
                    error = "pdf had no extractable text"
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
            # Fall back to the abstract so the RAG still has something to work with.
            return {
                **work,
                "content": work["summary"] or None,
                "content_type": "abstract" if work["summary"] else None,
                "error": error,
            }

        return await asyncio.gather(*(enrich(w) for w in works))

    # save results to chromadb collection
def save_to_chromadb(works: list[dict]):
        from ..rag.store import collection
        from ..websearch.chunking import chunk_document

        # Works with no content (no PDF and no abstract) produce no chunks; skip them.
        chunks = [chunk for work in works for chunk in chunk_document(work)]
        if not chunks:
            return
        # upsert, not add: re-running the same query overwrites chunks instead of failing on existing ids.
        collection.upsert(
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[chunk["metadata"] for chunk in chunks],
            ids=[chunk["id"] for chunk in chunks],
        )
            

