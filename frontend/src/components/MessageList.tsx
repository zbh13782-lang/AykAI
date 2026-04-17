import { useEffect, useRef } from 'react'

export interface DisplayMessage {
  id: string
  isUser: boolean
  content: string
  pending?: boolean
}

export default function MessageList({ messages }: { messages: DisplayMessage[] }) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  return (
    <div className="messages" ref={scrollRef}>
      {messages.length === 0 ? (
        <div className="placeholder">
          <h2>向 AykAI 提问</h2>
          <p>先在下方输入问题开始新对话，或上传 Markdown 文档构建知识库。</p>
        </div>
      ) : (
        messages.map((m) => (
          <div key={m.id} className={`message ${m.isUser ? 'user' : 'assistant'}`}>
            <div className="avatar" aria-hidden>
              {m.isUser ? '我' : 'AI'}
            </div>
            <div className="bubble">
              {m.content || (m.pending ? <span className="caret">▌</span> : '')}
              {m.pending && m.content && <span className="caret">▌</span>}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
