import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import {
  fetchHistory,
  listSessions,
  streamNewSession,
  streamSend,
  uploadMarkdown,
  type SessionInfo,
} from '../api/chat'
import SessionList from '../components/SessionList'
import MessageList, { type DisplayMessage } from '../components/MessageList'
import ChatInput from '../components/ChatInput'
import { useAuth } from '../context/AuthContext'

function genId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export default function ChatPage() {
  const { username, logout } = useAuth()
  const navigate = useNavigate()

  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const toastTimerRef = useRef<number | null>(null)

  const showToast = useCallback((msg: string) => {
    setToast(msg)
    // Reset any in-flight timer so back-to-back toasts don't dismiss each
    // other early (e.g. a stream failure followed by a session-refresh
    // failure would otherwise clear the second toast after ~0ms).
    if (toastTimerRef.current !== null) {
      window.clearTimeout(toastTimerRef.current)
    }
    toastTimerRef.current = window.setTimeout(() => {
      setToast(null)
      toastTimerRef.current = null
    }, 3500)
  }, [])

  useEffect(() => {
    return () => {
      if (toastTimerRef.current !== null) {
        window.clearTimeout(toastTimerRef.current)
      }
    }
  }, [])

  const handleAuthError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && (err.code === 2006 || err.code === 2007)) {
        logout()
        navigate('/login', { replace: true })
        return true
      }
      return false
    },
    [logout, navigate],
  )

  const refreshSessions = useCallback(async () => {
    setSessionsLoading(true)
    try {
      const list = await listSessions()
      setSessions(list)
    } catch (err) {
      if (!handleAuthError(err)) {
        showToast(err instanceof ApiError ? err.message : '获取会话失败')
      }
    } finally {
      setSessionsLoading(false)
    }
  }, [handleAuthError, showToast])

  useEffect(() => {
    void refreshSessions()
  }, [refreshSessions])

  const selectSession = useCallback(
    async (id: string) => {
      if (streaming) return
      setCurrentId(id)
      setMessages([])
      setHistoryLoading(true)
      try {
        const history = await fetchHistory(id)
        setMessages(
          history.map((entry, idx) => ({
            id: `h-${id}-${idx}`,
            isUser: entry.is_user,
            content: entry.content,
          })),
        )
      } catch (err) {
        if (!handleAuthError(err)) {
          showToast(err instanceof ApiError ? err.message : '加载历史失败')
        }
      } finally {
        setHistoryLoading(false)
      }
    },
    [handleAuthError, showToast, streaming],
  )

  const startNew = useCallback(() => {
    if (streaming) return
    setCurrentId(null)
    setMessages([])
  }, [streaming])

  const handleSend = useCallback(
    async (text: string) => {
      if (streaming) return

      const userMsg: DisplayMessage = {
        id: genId('u'),
        isUser: true,
        content: text,
      }
      const assistantMsg: DisplayMessage = {
        id: genId('a'),
        isUser: false,
        content: '',
        pending: true,
      }
      setMessages((prev) => [...prev, userMsg, assistantMsg])
      setStreaming(true)

      const controller = new AbortController()
      abortRef.current = controller

      let createdSessionId: string | null = null
      const appendToken = (token: string) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id ? { ...m, content: m.content + token } : m,
          ),
        )
      }

      try {
        if (currentId) {
          await streamSend(
            currentId,
            text,
            { onToken: appendToken },
            controller.signal,
          )
        } else {
          await streamNewSession(
            text,
            {
              onToken: appendToken,
              onSessionId: (sid) => {
                createdSessionId = sid
                setCurrentId(sid)
              },
            },
            controller.signal,
          )
        }
      } catch (err) {
        if (!handleAuthError(err)) {
          showToast(err instanceof ApiError ? err.message : '发送失败')
        }
      } finally {
        setStreaming(false)
        abortRef.current = null
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantMsg.id ? { ...m, pending: false } : m)),
        )
        if (createdSessionId) {
          void refreshSessions()
        }
      }
    },
    [currentId, handleAuthError, refreshSessions, showToast, streaming],
  )

  const handleUpload = useCallback(
    async (file: File) => {
      setUploading(true)
      try {
        const res = await uploadMarkdown(file, currentId ?? undefined)
        showToast(
          `已导入：${file.name}（父块 ${res.inserted_parents ?? 0} / 子块 ${res.inserted_children ?? 0}）`,
        )
      } catch (err) {
        if (!handleAuthError(err)) {
          showToast(err instanceof ApiError ? err.message : '上传失败')
        }
      } finally {
        setUploading(false)
      }
    },
    [currentId, handleAuthError, showToast],
  )

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  return (
    <div className="chat-shell">
      <SessionList
        sessions={sessions}
        currentId={currentId}
        onSelect={selectSession}
        onNew={startNew}
        loading={sessionsLoading}
      />

      <main className="chat-main">
        <header className="chat-header">
          <div className="who">
            <span className="brand-small">AykAI</span>
            {username && <span className="muted"> · {username}</span>}
          </div>
          <div className="actions">
            <button
              className="ghost"
              onClick={() => {
                logout()
                navigate('/login', { replace: true })
              }}
            >
              登出
            </button>
          </div>
        </header>

        {historyLoading ? (
          <div className="messages"><div className="placeholder">加载历史中…</div></div>
        ) : (
          <MessageList messages={messages} />
        )}

        <ChatInput
          onSend={handleSend}
          onUpload={handleUpload}
          disabled={streaming}
          uploading={uploading}
        />
      </main>

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
