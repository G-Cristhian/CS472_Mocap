// Shared by the Django API clients (auth, recordings, performers). Django runs on port 8000 by default;
// set VITE_DJANGO_URL to point somewhere else.

export const DJANGO_URL = (import.meta.env.VITE_DJANGO_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

const SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS']

function csrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)

  return match ? decodeURIComponent(match[1]) : null
}

/** Django sets the csrftoken cookie on a GET. Fetch one if the browser doesn't have it yet. */
async function csrfToken(): Promise<string | null> {
  if (!csrfCookie()) {
    await fetch(`${DJANGO_URL}/api/v1/auth/csrf/`, { credentials: 'include' })
  }

  return csrfCookie()
}

/** The CSRF header Django needs for a request with this method. Empty for safe methods. */
export async function csrfHeaderFor(method: string): Promise<Record<string, string>> {
  if (SAFE_METHODS.includes(method.toUpperCase())) return {}

  const token = await csrfToken()

  return token ? { 'X-CSRFToken': token } : {}
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

/**
 * Calls a Django JSON endpoint with the login cookie and, for unsafe methods, the CSRF token.
 * A JSON body is sent as JSON; a FormData body is sent as is. Throws an Error with a readable message.
 */
export async function djangoJson<T>(url: string, init: { method?: string; body?: BodyInit } = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers: Record<string, string> = { ...(await csrfHeaderFor(method)) }
  if (typeof init.body === 'string') headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(url, { method, body: init.body, headers, credentials: 'include' })
  } catch {
    throw new Error(`Can't reach the server at ${DJANGO_URL}. Is Django running?`)
  }

  if (response.status === 204) return undefined as T

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new Error(errorMessage(body, response.status))

  return body as T
}
