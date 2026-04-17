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

// Streaming callbacks used by both SSE endpoints.
export interface StreamHandlers {
  onSessionId?: (sessionId: string) => void
  onToken: (token: string) => void
  onDone?: () => void
  onError?: (err: unknown) => void
}

// The Go backend emits the session id as a JSON blob `{"sessionId":"..."}`
// at the start of a new-session stream. After that it emits raw text
// tokens. The stream is terminated by a literal `[DONE]` payload.
function wrapStream(handlers: StreamHandlers): (payload: string) => void {
  return (payload) => {
    if (payload === '[DONE]') {
      handlers.onDone?.()
      return
    }
    // Try to parse the first-event sessionId blob; fall back to treating
    // the payload as a plain text token otherwise.
    if (payload.startsWith('{') && payload.includes('sessionId')) {
      try {
        const parsed = JSON.parse(payload) as { sessionId?: string }
        if (parsed.sessionId) {
          handlers.onSessionId?.(parsed.sessionId)
          return
        }
      } catch {
        // fall through to plain token handling
      }
    }
    handlers.onToken(payload)
  }
}

export async function streamNewSession(
  question: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await apiStream(
      '/api/v1/AI/chat/send-stream-new-session',
      { question },
      wrapStream(handlers),
      signal,
    )
    handlers.onDone?.()
  } catch (err) {
    handlers.onError?.(err)
    throw err
  }
}

export async function streamSend(
  sessionId: string,
  question: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await apiStream(
      '/api/v1/AI/chat/send-stream',
      { sessionId, question },
      wrapStream(handlers),
      signal,
    )
    handlers.onDone?.()
  } catch (err) {
    handlers.onError?.(err)
    throw err
  }
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
