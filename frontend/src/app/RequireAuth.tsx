import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/app/AuthProvider'

/** Shows its children only to a logged-in user. Anyone else goes to /login and comes back afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  // Wait until we know whether the session is live, or a logged-in user would bounce to /login
  if (loading) return <main aria-busy="true" style={{ minHeight: '100vh' }} />

  if (!user) return <Navigate to="/login" replace state={{ from: location }} />

  return <>{children}</>
}
