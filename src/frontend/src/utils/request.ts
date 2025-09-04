/**
 * Minimal fetch wrapper for JSON APIs
 */
export const API_BASE_URL: string = (import.meta as any).env?.VITE_API_BASE || 'http://127.0.0.1:8000'

export interface HttpOptions {
  method?: string
  headers?: Record<string, string>
  body?: any
  signal?: AbortSignal
}

async function handleResponse<T>(resp: Response): Promise<T> {
  const text = await resp.text()
  if (!resp.ok) {
    // try parse json detail
    try {
      const data = JSON.parse(text)
      throw new Error(typeof data === 'object' ? (data.detail || JSON.stringify(data)) : String(data))
    } catch {
      throw new Error(text || `HTTP ${resp.status}`)
    }
  }
  if (!text) return undefined as unknown as T
  try {
    return JSON.parse(text) as T
  } catch {
    return text as unknown as T
  }
}

export async function http<T>(path: string, options: HttpOptions = {}): Promise<T> {
  const { method = 'GET', headers, body, signal } = options
  const url = `${API_BASE_URL}${path}`
  const init: RequestInit = {
    method,
    headers,
    body,
    signal
  }
  const resp = await fetch(url, init)
  return handleResponse<T>(resp)
}

export async function postJson<T, B = unknown>(path: string, data: B, signal?: AbortSignal): Promise<T> {
  return http<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal
  })
}


