import { createContext, useCallback, useContext, useMemo, useState } from 'react'

const TOKEN_KEY = 'aykai_token'
const USERNAME_KEY = 'aykai_username'

interface AuthContextValue {
  token: string | null
  username: string | null
  login: (token: string, username?: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [username, setUsername] = useState<string | null>(() => localStorage.getItem(USERNAME_KEY))

  const login = useCallback((nextToken: string, nextUsername?: string) => {
    localStorage.setItem(TOKEN_KEY, nextToken)
    setToken(nextToken)
    if (nextUsername) {
      localStorage.setItem(USERNAME_KEY, nextUsername)
      setUsername(nextUsername)
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USERNAME_KEY)
    setToken(null)
    setUsername(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ token, username, login, logout }),
    [token, username, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
