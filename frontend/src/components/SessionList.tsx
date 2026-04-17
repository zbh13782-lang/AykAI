import type { SessionInfo } from '../api/chat'

interface Props {
  sessions: SessionInfo[]
  currentId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  loading: boolean
}

export default function SessionList({ sessions, currentId, onSelect, onNew, loading }: Props) {
  return (
    <aside className="sidebar">
      <button className="primary full" onClick={onNew}>
        + 新对话
      </button>

      <div className="session-list">
        {loading && sessions.length === 0 && <div className="empty">加载中…</div>}
        {!loading && sessions.length === 0 && <div className="empty">暂无会话</div>}
        {sessions.map((s) => (
          <button
            key={s.sessionId}
            className={`session-item${currentId === s.sessionId ? ' active' : ''}`}
            onClick={() => onSelect(s.sessionId)}
            title={s.name}
          >
            {s.name || '未命名会话'}
          </button>
        ))}
      </div>
    </aside>
  )
}
