import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as auth from '@/lib/auth'
import type { AuthUser, SignUpInput } from '@/lib/auth'

interface AuthContextValue {
  user: AuthUser | null
  /** true until we know whether the browser already has a live session */
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (input: SignUpInput) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // A session cookie from an earlier visit may still be valid. If not, Django answers 403.
    auth
      .fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setUser(await auth.login(email, password))
  }, [])

  const register = useCallback(async (input: SignUpInput) => {
    setUser(await auth.register(input))
  }, [])

  const logout = useCallback(async () => {
    try {
      await auth.logout()
    } catch {
      // The session is already gone, or the server is down. Clear the UI either way.
    }
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')

  return context
}
