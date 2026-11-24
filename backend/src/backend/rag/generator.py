"""Answer generation: turn retrieved chunks into a grounded, cited answer with the LLM."""

import os

from langchain.chat_models import init_chat_model

# "provider:model" string, e.g. "ollama:llama3.1" — override with the LLM_MODEL env var.
LLM_MODEL = os.getenv("LLM_MODEL", "ollama:north-mini-code-1.0")

SYSTEM_PROMPT = """You are a research assistant that answers questions using scientific papers.

Rules:
- Answer ONLY from the numbered context excerpts provided. Do not use outside knowledge.
- Cite the sources you use inline with their number in square brackets, e.g. [1] or [2][3].
- If the context does not contain enough information to answer, say so clearly instead of guessing.
- Be concise and precise. Answer in the same language as the question."""

_llm = None


def get_llm():
    """Create the chat model on first use, so importing this module never contacts the LLM server."""
    global _llm
    if _llm is None:
        _llm = init_chat_model(LLM_MODEL, temperature=0.2)
    return _llm


def _group_by_document(chunks: list[dict]) -> list[dict]:
    """Group chunks by paper so each source gets one citation number, in retrieval order."""
    sources: dict[str, dict] = {}
    for chunk in chunks:
        meta = chunk.get("metadata") or {}
        doc_id = meta.get("document_id") or chunk["id"].split("#")[0]
        if doc_id not in sources:
            sources[doc_id] = {
                "number": len(sources) + 1,
                "document_id": doc_id,
                "title": meta.get("title"),
                "authors": meta.get("authors"),
                "published": meta.get("published"),
                "doi": meta.get("doi"),
                "url": meta.get("landing_page_url") or meta.get("pdf_url"),
                "content_type": meta.get("content_type"),  # "full_text" | "abstract"
                "excerpts": [],
            }
        sources[doc_id]["excerpts"].append(chunk["text"])
    return list(sources.values())


def _build_context(sources: list[dict]) -> str:
    blocks = []
    for s in sources:
        header = f"[{s['number']}] {s['title'] or 'Untitled'}"
        if s["published"]:
            header += f" ({s['published'][:4]})"
        excerpts = "\n...\n".join(s["excerpts"])
        blocks.append(f"{header}\n{excerpts}")
    return "\n\n---\n\n".join(blocks)


async def generate_answer(question: str, chunks: list[dict]) -> dict:
    """
    Generate an answer to `question` grounded in the retrieved `chunks`.

    Returns {"answer": str, "sources": [...]}; the source numbers match the [n] citations in the answer.
    """
    if not chunks:
        return {
            "answer": "I couldn't find any relevant papers to answer this question.",
            "sources": [],
        }

    sources = _group_by_document(chunks)
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"Context:\n\n{_build_context(sources)}\n\nQuestion: {question}"),
    ]
    response = await get_llm().ainvoke(messages)

    return {
        "answer": response.content,
        # `passage`: the closest excerpt used for this source, so the UI can show where a claim came from.
        "sources": [
            {**{k: v for k, v in s.items() if k != "excerpts"}, "passage": s["excerpts"][0]}
            for s in sources
        ],
    }
