import { FormEvent, KeyboardEvent, useState } from 'react'

interface Props {
  onSend: (text: string) => void
  onUpload: (file: File) => void
  disabled: boolean
  uploading: boolean
}

export default function ChatInput({ onSend, onUpload, disabled, uploading }: Props) {
  const [value, setValue] = useState('')

  function submit(e?: FormEvent) {
    e?.preventDefault()
    const text = value.trim()
    if (!text || disabled) return
    onSend(text)
    setValue('')
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) onUpload(file)
    e.target.value = ''
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKey}
        placeholder="输入问题… (Enter 发送，Shift+Enter 换行)"
        rows={2}
        disabled={disabled}
      />
      <div className="composer-actions">
        <label className={`ghost upload${uploading ? ' disabled' : ''}`}>
          {uploading ? '上传中…' : '上传 Markdown'}
          <input
            type="file"
            accept=".md,.markdown,text/markdown"
            onChange={handleFile}
            disabled={uploading}
            hidden
          />
        </label>
        <button type="submit" className="primary" disabled={disabled || !value.trim()}>
          发送
        </button>
      </div>
    </form>
  )
}
