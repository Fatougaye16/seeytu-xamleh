export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  query?: Record<string, string | number | boolean | undefined>
  body?: unknown
  token?: string | null
  signal?: AbortSignal
}

/** FastAPI errors come as {detail: string} or, for validation, {detail: [{msg, loc}]}. */
function messageFromBody(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
        .filter(Boolean)
        .join('. ')
    }
  }
  return `Request failed (${status})`
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const url = new URL(path, window.location.origin)
  for (const [key, value] of Object.entries(opts.query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value))
  }

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`

  let response: Response
  try {
    response = await fetch(url, {
      method: opts.method ?? 'GET',
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: opts.signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError('Can’t reach the server. Is the backend running?', 0)
  }

  const text = await response.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = text
  }

  if (!response.ok) {
    // The Vite proxy answers 502/504 itself when FastAPI is down.
    if ((response.status === 502 || response.status === 504) && !body) {
      throw new ApiError('Can’t reach the server. Is the backend running?', response.status)
    }
    throw new ApiError(messageFromBody(body, response.status), response.status)
  }
  return body as T
}
