// Low-level HTTP helpers for the AykAI Go backend.
//
// Every JSON response is wrapped as `{ status_code, status_msg, ...data }`
// where `status_code === 1000` signals success. We normalize that envelope
// into thrown errors so UI code can rely on regular promise semantics.

const SUCCESS_CODE = 1000
const TOKEN_KEY = 'aykai_token'

export class ApiError extends Error {
  readonly code: number
  constructor(code: number, message: string) {
    super(message)
    this.code = code
  }
}

interface BaseResponse {
  status_code: number
  status_msg?: string
}

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

function authHeaders(auth: boolean): Record<string, string> {
  if (!auth) return {}
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function unwrap<T extends BaseResponse>(payload: T): T {
  if (payload.status_code !== SUCCESS_CODE) {
    throw new ApiError(payload.status_code, payload.status_msg || '请求失败')
  }
  return payload
}

interface RequestOptions {
  auth?: boolean
}

export async function apiGet<T extends BaseResponse>(
  path: string,
  { auth = true }: RequestOptions = {},
): Promise<T> {
  const res = await fetch(path, {
    method: 'GET',
    headers: { ...authHeaders(auth) },
  })
  const data = (await res.json()) as T
  return unwrap(data)
}

export async function apiPost<T extends BaseResponse>(
  path: string,
  body: unknown,
  { auth = true }: RequestOptions = {},
): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(auth),
    },
    body: JSON.stringify(body),
  })
  const data = (await res.json()) as T
  return unwrap(data)
}

export async function apiUpload<T extends BaseResponse>(
  path: string,
  form: FormData,
): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { ...authHeaders(true) },
    body: form,
  })
  const data = (await res.json()) as T
  return unwrap(data)
}

// SSE streaming via fetch + ReadableStream. We cannot use EventSource
// because browsers do not allow setting custom headers (JWT) on it.
//
// The Go backend emits lines of the form `data: <payload>\n\n`. We call
// `onEvent` with each payload string. Returns a promise that resolves once
// the stream ends.
export async function apiStream(
  path: string,
  body: unknown,
  onEvent: (payload: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(true),
    },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) {
    throw new ApiError(res.status, `流式请求失败: ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)

      const dataLines = rawEvent
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).replace(/^\s/, ''))
      if (dataLines.length === 0) continue
      const payload = dataLines.join('\n')
      onEvent(payload)
    }
  }
}
