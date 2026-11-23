"""arXiv client: search metadata and fetch full paper text in memory (nothing persisted)."""

import asyncio
import io
import re
from xml.etree import ElementTree as ET

import httpx
from pypdf import PdfReader

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"

# arXiv asks clients to be gentle; cap concurrent PDF downloads.
_PDF_CONCURRENCY = asyncio.Semaphore(3)

_FIELD_PREFIX = re.compile(r"^(ti|au|abs|co|jr|cat|rn|id|all):", re.IGNORECASE)


def _build_search_query(query: str) -> str:
    # A bare query like "graph neural networks" should search all fields.
    return query if _FIELD_PREFIX.match(query.strip()) else f"all:{query}"


def _parse_entry(entry: ET.Element) -> dict:
    pdf_url = None
    for link in entry.findall(f"{ATOM}link"):
        if link.get("title") == "pdf" or link.get("type") == "application/pdf":
            pdf_url = link.get("href")
            break

    entry_id = entry.findtext(f"{ATOM}id", "")
    if pdf_url is None and entry_id:
        pdf_url = entry_id.replace("/abs/", "/pdf/")

    return {
        "id": entry_id,
        "title": " ".join(entry.findtext(f"{ATOM}title", "").split()),
        "summary": " ".join(entry.findtext(f"{ATOM}summary", "").split()),
        "published": entry.findtext(f"{ATOM}published"),
        "authors": [a.findtext(f"{ATOM}name") for a in entry.findall(f"{ATOM}author")],
        "pdf_url": pdf_url,
    }


async def search(client: httpx.AsyncClient, query: str, max_results: int) -> list[dict]:
    params = {
        "search_query": _build_search_query(query),
        "start": 0,
        "max_results": max_results,
    }
    response = await client.get(ARXIV_API_URL, params=params)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    return [_parse_entry(e) for e in root.findall(f"{ATOM}entry")]


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = (page.extract_text() or "" for page in reader.pages)
    return "\n\n".join(p.strip() for p in pages if p.strip())


async def fetch_full_text(client: httpx.AsyncClient, pdf_url: str) -> str:
    # content should not be saved to disk or memory we only need the text for RAG pipeline
    async with _PDF_CONCURRENCY:
        response = await client.get(pdf_url)
        response.raise_for_status()
        return _preprocess_content(_extract_pdf_text(response.content))


async def search_with_content(query: str, max_results: int) -> list[dict]:
    """Search arXiv, then fetch each paper's full text. Results live only in chromadb."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": "seeytu-xamleh-rag/0.1"},
    ) as client:
        papers = await search(client, query, max_results)

        async def enrich(paper: dict) -> dict:
            if not paper["pdf_url"]:
                return {**paper, "content": None, "error": "no pdf link"}
            try:
                return {**paper, "content": await fetch_full_text(client, paper["pdf_url"]), "error": None}
            except Exception as exc:  # one bad paper shouldn't fail the whole request
                return {**paper, "content": None, "error": f"{type(exc).__name__}: {exc}"}

        return await asyncio.gather(*(enrich(p) for p in papers))

def _preprocess_content(content: str) -> str:
    """Preprocess the extracted text to remove unwanted characters and whitespace."""
    # Remove non-printable characters
    content = re.sub(r"[^\x20-\x7E]", " ", content)
    # Normalize whitespace
    content = re.sub(r"\s+", " ", content).strip()
    # remove page numbers and headers/footers (common in PDFs)
    content = re.sub(r"(\n|^)\s*\d+\s*(\n|$)", "\n", content)
    content = re.sub(r"(?i)(\n|^)(abstract|introduction|conclusion|references|acknowledgments)\s*(\n|$)", "\n", content)
    return content