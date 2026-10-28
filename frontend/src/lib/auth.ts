// Client for the Django accounts API (backend/motionboxpro/apps/accounts).
// Login is a Django session kept in an HttpOnly cookie. credentials: 'include' sends that cookie
// with every request, and POSTs also send Django's CSRF token (from the csrftoken cookie).
// Django runs on port 8000 by default; set VITE_DJANGO_URL to point somewhere else.

import { DJANGO_URL, csrfHeaderFor } from '@/lib/django'

export interface AuthUser {
  id: number
  email: string
  first_name: string
  last_name: string
}

/** Full name for labels, e.g. "Noah Smith". Falls back to the email when no name was given. */
export function displayName(user: AuthUser): string {
  return [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email
}

export interface SignUpInput {
  email: string
  password: string
  first_name: string
  last_name: string
}

/** A failed auth call. status is undefined when the server could not be reached at all. */
export class AuthError extends Error {
  status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'AuthError'
    this.status = status
  }
}

/** Field errors look like { email: ["..."] }, other errors like { detail: "..." }. */
function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const data = body as Record<string, unknown>
    if (typeof data.detail === 'string') return data.detail

    const messages = Object.values(data)
      .flat()
      .filter((m): m is string => typeof m === 'string')
    if (messages.length > 0) return messages.join(' ')
  }

  return `The server answered with HTTP ${status}`
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }

  let response: Response
  try {
    Object.assign(headers, await csrfHeaderFor(method))
    response = await fetch(`${DJANGO_URL}/api/v1/auth${path}`, { ...init, headers, credentials: 'include' })
  } catch {
    throw new AuthError(`Can't reach the server at ${DJANGO_URL}. Is Django running?`)
  }

  if (response.status === 204) return undefined as T

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new AuthError(errorMessage(body, response.status), response.status)

  return body as T
}

export function login(email: string, password: string): Promise<AuthUser> {
  return request<AuthUser>('/login/', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export function register(input: SignUpInput): Promise<AuthUser> {
  return request<AuthUser>('/register/', { method: 'POST', body: JSON.stringify(input) })
}

export function logout(): Promise<void> {
  return request<void>('/logout/', { method: 'POST' })
}

/** The signed-in user. Rejects with a 403 AuthError when nobody is logged in. */
export function fetchMe(): Promise<AuthUser> {
  return request<AuthUser>('/me/')
}

/** Asks Django to email a reset link. Returns the same message whether or not the email has an account. */
export async function requestPasswordReset(email: string): Promise<string> {
  const body = await request<{ detail: string }>('/password/reset/', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })

  return body.detail
}

export async function confirmPasswordReset(uid: string, token: string, newPassword: string): Promise<string> {
  const body = await request<{ detail: string }>('/password/reset/confirm/', {
    method: 'POST',
    body: JSON.stringify({ uid, token, new_password: newPassword }),
  })

  return body.detail
}
