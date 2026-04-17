import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login as loginApi } from '../api/user'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await loginApi(username.trim(), password)
      if (!res.token) throw new Error('服务端未返回 token')
      login(res.token, username.trim())
      navigate('/chat', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1 className="brand">AykAI</h1>
        <p className="subtitle">登录到你的 RAG 工作台</p>

        <label className="field">
          <span>用户名</span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="注册邮件里收到的 11 位数字"
            autoComplete="username"
            required
          />
        </label>

        <label className="field">
          <span>密码</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error && <div className="alert">{error}</div>}

        <button className="primary" type="submit" disabled={loading}>
          {loading ? '登录中…' : '登录'}
        </button>

        <div className="muted-footer">
          还没有账号？<Link to="/register">去注册</Link>
        </div>
      </form>
    </div>
  )
}
