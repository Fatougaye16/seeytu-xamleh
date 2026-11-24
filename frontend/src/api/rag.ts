import { request } from './client'

/** One cited paper, as returned by rag/generator.py. `number` matches the [n] in the answer. */
export interface Source {
  number: number
  document_id: string
  title: string | null
  authors?: string | null
  published?: string | null
  doi?: string | null
  url?: string | null
  /** "full_text" | "abstract" — present once the backend includes it. */
  content_type?: string | null
  /** The passage the answer drew on, when the backend includes it. */
  passage?: string | null
}

export interface AskResponse {
  answer: string
  sources: Source[]
}

/** GET /api/websearch/ask — retrieves (fetching papers if needed) and generates a cited answer. */
export function ask(question: string, signal?: AbortSignal, topK = 5): Promise<AskResponse> {
  return request<AskResponse>('/api/websearch/ask', {
    query: { question, top_k: topK },
    signal,
  })
}
