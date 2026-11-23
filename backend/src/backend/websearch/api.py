import httpx
from fastapi import APIRouter, HTTPException, Query

from . import arxiv

router = APIRouter()


@router.get("/arxiv")
async def get_arxiv_data(
    query: str = Query(..., min_length=1),
    max_results: int = Query(5, ge=1, le=20),
    full_text: bool = Query(True, description="Download each PDF and extract its text (in memory only)"),
):
    """
    Searches arXiv and, by default, fetches each paper's full text for the RAG pipeline.
    Nothing is written to disk or the database; PDFs are parsed in memory and discarded.
    """
    try:
        if full_text:
            return await arxiv.search_with_content(query, max_results)
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            return await arxiv.search(client, query, max_results)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"arXiv request failed: {exc}") from exc
