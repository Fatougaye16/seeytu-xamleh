import asyncio

from backend.rag.generator import LLM_MODEL, generate_answer
from backend.rag.retriever import retrieve_info_from_chromadb
import httpx
from fastapi import APIRouter, HTTPException, Query

from . import arxiv, openalex

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


@router.get("/openalex")
async def get_openalex_data(
    query: str = Query(..., min_length=1),
    max_results: int = Query(5, ge=1, le=25),
    full_text: bool = Query(True, description="Download open-access PDFs and extract their text (in memory only)"),
    open_access_only: bool = Query(True, description="Only return works with an open-access version"),
):
    """
    Searches OpenAlex and, by default, fetches each work's open-access full text (raw, unchunked).
    Falls back to the abstract when no PDF is reachable. Nothing is written to disk or the database.
    """
    try:
        if full_text:
            response = await openalex.search_with_content(query, max_results, open_access_only)
            # Embedding is CPU-heavy; keep it off the event loop.
            await asyncio.to_thread(openalex.save_to_chromadb, response)
            return response
        # Metadata only: nothing to embed, just return the search results.
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            return await openalex.search(client, query, max_results, open_access_only)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAlex request failed: {exc}") from exc

@router.get("/ask")
async def ask_question(question: str = Query(..., min_length=1), top_k: int = Query(5, ge=1, le=20)):
    """
    Ask a question and retrieve relevant chunks. If chroma has nothing yet (empty, or wiped by a
    restart), fetch papers from OpenAlex for the question, embed them, then retrieve.
    """
    chunks = await asyncio.to_thread(retrieve_info_from_chromadb, question, top_k)
    if not chunks:
        try:
            docs = await openalex.search_with_content(question, max_results=5)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"OpenAlex request failed: {exc}") from exc
        await asyncio.to_thread(openalex.save_to_chromadb, docs)
        chunks = await asyncio.to_thread(retrieve_info_from_chromadb, question, top_k)

    try:
        return await generate_answer(question, chunks)
    except Exception as exc:  # LLM server down, model not pulled, etc.
        raise HTTPException(status_code=503, detail=f"LLM generation failed ({LLM_MODEL}): {exc}") from exc