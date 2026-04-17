import { apiPost } from './client'

interface LoginResponse {
  status_code: number
  status_msg?: string
  token?: string
}

interface RegisterResponse {
  status_code: number
  status_msg?: string
  token?: string
}

interface CaptchaResponse {
  status_code: number
  status_msg?: string
}

export function login(username: string, password: string) {
  return apiPost<LoginResponse>(
    '/api/v1/user/login',
    { username, password },
    { auth: false },
  )
}

export function register(email: string, captcha: string, password: string) {
  return apiPost<RegisterResponse>(
    '/api/v1/user/register',
    { email, captcha, password },
    { auth: false },
  )
}

export function sendCaptcha(email: string) {
  return apiPost<CaptchaResponse>(
    '/api/v1/user/captcha',
    { email },
    { auth: false },
  )
}
