import { FormEvent, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { register, sendCaptcha } from '../api/user'
import { ApiError } from '../api/client'

export default function RegisterPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [captcha, setCaptcha] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [sendingCaptcha, setSendingCaptcha] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  // Hold the cooldown interval id so we can cancel it on unmount — otherwise
  // it keeps firing setState on an unmounted component for up to 60s if the
  // user navigates away mid-cooldown.
  const cooldownRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (cooldownRef.current !== null) {
        window.clearInterval(cooldownRef.current)
        cooldownRef.current = null
      }
    }
  }, [])

  function startCooldown() {
    setCooldown(60)
    if (cooldownRef.current !== null) {
      window.clearInterval(cooldownRef.current)
    }
    cooldownRef.current = window.setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          if (cooldownRef.current !== null) {
            window.clearInterval(cooldownRef.current)
            cooldownRef.current = null
          }
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  async function handleSendCaptcha() {
    if (!email) {
      setError('请先填写邮箱')
      return
    }
    setError(null)
    setInfo(null)
    setSendingCaptcha(true)
    try {
      await sendCaptcha(email.trim())
      setInfo('验证码已发送，请查收邮箱')
      startCooldown()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setSendingCaptcha(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setInfo(null)
    setLoading(true)
    try {
      await register(email.trim(), captcha.trim(), password)
      setInfo('注册成功，系统生成的登录用户名已通过邮件发送，请前往登录页使用')
      setTimeout(() => navigate('/login', { replace: true }), 1500)
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
        <p className="subtitle">创建新账号</p>

        <label className="field">
          <span>邮箱</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>

        <label className="field">
          <span>验证码</span>
          <div className="row">
            <input
              type="text"
              value={captcha}
              onChange={(e) => setCaptcha(e.target.value)}
              placeholder="6 位邮箱验证码"
              required
            />
            <button
              type="button"
              className="ghost"
              onClick={handleSendCaptcha}
              disabled={sendingCaptcha || cooldown > 0}
            >
              {cooldown > 0 ? `${cooldown}s 后重试` : sendingCaptcha ? '发送中…' : '发送验证码'}
            </button>
          </div>
        </label>

        <label className="field">
          <span>密码</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
            minLength={6}
          />
        </label>

        {error && <div className="alert">{error}</div>}
        {info && <div className="alert info">{info}</div>}

        <button className="primary" type="submit" disabled={loading}>
          {loading ? '注册中…' : '注册'}
        </button>

        <div className="muted-footer">
          已有账号？<Link to="/login">去登录</Link>
        </div>
      </form>
    </div>
  )
}
