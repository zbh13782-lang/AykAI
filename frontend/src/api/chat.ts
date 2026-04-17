import { apiGet, apiPost, apiStream, apiUpload } from './client'

export interface SessionInfo {
  sessionId: string
  name: string
}

export interface HistoryEntry {
  is_user: boolean
  content: string
}

interface SessionsResponse {
  status_code: number
  status_msg?: string
  sessions?: SessionInfo[]
}

interface HistoryResponse {
  status_code: number
  status_msg?: string
  history?: HistoryEntry[]
}

interface UploadResponse {
  status_code: number
  status_msg?: string
  inserted_parents?: number
  inserted_children?: number
}

export async function listSessions(): Promise<SessionInfo[]> {
  const res = await apiGet<SessionsResponse>('/api/v1/AI/chat/sessions')
  return res.sessions ?? []
}

export async function fetchHistory(sessionId: string): Promise<HistoryEntry[]> {
  const res = await apiPost<HistoryResponse>('/api/v1/AI/chat/history', { sessionId })
  return res.history ?? []
}

// A reference row returned by the RAG pipeline (Python service). Shape is
// intentionally loose — we only surface the fields the UI actually renders.
export interface StreamReference {
  parent_id?: string | number
  source?: string
  title?: string
  content?: string
  [key: string]: unknown
}

// Streaming callbacks used by both SSE endpoints.
export interface StreamHandlers {
  onSessionId?: (sessionId: string) => void
  onReferences?: (refs: StreamReference[]) => void
  onToken: (token: string) => void
  onDone?: () => void
  onError?: (err: unknown) => void
}

// The SSE wire format is a stack of wrappers (outer → inner):
//
//   1. Go gateway (`backend/service/session/session.go`) — for a brand-new
//      session, prepends **one** `data: {"sessionId":"<uuid>"}\n\n` event so
//      the UI can bind the new session before rendering tokens. It also
//      appends `data: [DONE]\n\n` once the upstream stream ends.
//
//   2. Python AI service (`AIserver/api/routes/query.py:51-64`) — emits the
//      **actual** token stream as JSON envelopes:
//        data: {"event":"references","data":[...]}\n\n
//        data: {"event":"token","data":"<text>"}\n\n   (one per token)
//        data: {"event":"done","data":{"answer":"...","references":[...]}}\n\n
//        data: {"event":"error","data":"<message>"}\n\n   (on failure)
//      The Go gateway forwards these verbatim to the browser.
//
// So `wrapStream` must parse the envelope and dispatch by `event`. Only
// `event:"token"` payloads become visible text in the chat bubble — the
// earlier revision leaked the raw JSON strings into the message body.
//
// We intentionally DO NOT invoke `onDone` on `[DONE]` or on `event:"done"`
// here — the caller fires it exactly once after `apiStream` resolves, so
// streams that end without either sentinel still terminate cleanly.
function wrapStream(handlers: StreamHandlers): (payload: string) => void {
  return (payload) => {
    if (payload === '[DONE]') {
      return
    }

    // Anything that isn't a JSON object is just raw text — pass it through.
    if (!payload.startsWith('{')) {
      handlers.onToken(payload)
      return
    }

    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(payload) as Record<string, unknown>
    } catch {
      // Malformed JSON — fall back to plain-text rendering so the user at
      // least sees *something* instead of silently losing the chunk.
      handlers.onToken(payload)
      return
    }

    // Session-binding event emitted by the Go gateway on new-session streams.
    if (typeof parsed.sessionId === 'string') {
      handlers.onSessionId?.(parsed.sessionId)
      return
    }

    // Python event envelope.
    switch (parsed.event) {
      case 'token': {
        const token = typeof parsed.data === 'string' ? parsed.data : ''
        if (token) handlers.onToken(token)
        return
      }
      case 'references': {
        const refs = Array.isArray(parsed.data)
          ? (parsed.data as StreamReference[])
          : []
        handlers.onReferences?.(refs)
        return
      }
      case 'done':
        // Final envelope from Python. `onDone` is fired once after
        // `apiStream` resolves, so we don't double-invoke it here.
        return
      case 'error': {
        const msg = typeof parsed.data === 'string' ? parsed.data : '流式请求失败'
        handlers.onError?.(new Error(msg))
        return
      }
    }

    // Go gateway error envelope emitted via Gin's `c.SSEvent("error",
    // gin.H{"message": "..."})` — e.g. session ownership check failure or
    // Python service unreachable (see backend/controller/session/session.go
    // :123, :135, :181). Our SSE parser drops the `event:` line, so all we
    // receive is `{"message":"..."}` with no `event` field. Surface it via
    // onError so the user gets a toast instead of a half-rendered bubble.
    if (typeof parsed.message === 'string') {
      handlers.onError?.(new Error(parsed.message))
      return
    }

    // Unknown JSON shape — ignore rather than leaking JSON into the bubble.
  }
}

// NOTE: `handlers.onError` is reserved for **in-stream** errors reported by
// the Python service (`event:"error"`), which `apiStream` cannot detect —
// the Go proxy forwards the envelope then resolves successfully. Thrown
// errors (network / auth / HTTP) propagate via `throw` so the caller's
// try/catch handles them; dispatching `onError` here too would double-fire
// the toast.
export async function streamNewSession(
  question: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  await apiStream(
    '/api/v1/AI/chat/send-stream-new-session',
    { question },
    wrapStream(handlers),
    signal,
  )
  handlers.onDone?.()
}

export async function streamSend(
  sessionId: string,
  question: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  await apiStream(
    '/api/v1/AI/chat/send-stream',
    { sessionId, question },
    wrapStream(handlers),
    signal,
  )
  handlers.onDone?.()
}

export async function uploadMarkdown(
  file: File,
  sessionId?: string,
): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('doc_id', file.name)
  form.append('source', 'web-upload')
  if (sessionId) form.append('sessionId', sessionId)
  return apiUpload<UploadResponse>('/api/v1/AI/chat/upload-md', form)
}
