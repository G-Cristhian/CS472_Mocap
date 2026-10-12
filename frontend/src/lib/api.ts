// Client for the backend API (backend/api.py, run with `cd backend && uvicorn api:app`).

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

export type TakeStatus = 'queued' | 'running' | 'done' | 'failed'
export type TakeStage = 'detecting' | 'calibrating' | 'triangulating' | 'writing'

/** A take record as the API returns it (status.json in the take's folder). */
export interface Take {
  id: string
  name: string | null
  project_id: string | null
  created_at: string
  camera_count: number
  height_m: number
  status: TakeStatus
  stage: TakeStage | null
  error: string | null
  finished_at: string | null
}

/** Thrown when the API can't be reached at all (not running, wrong URL, blocked by CORS). */
export class ApiUnreachableError extends Error {
  constructor() {
    super(`Can't reach the API at ${API_URL}`)
    this.name = 'ApiUnreachableError'
  }
}

/** One take, or null if the API has no take with that id. */
export async function getTake(id: string, signal?: AbortSignal): Promise<Take | null> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/takes/${encodeURIComponent(id)}`, { signal })
  } catch (e) {
    // fetch only rejects on network failure or abort
    if (signal?.aborted) throw e
    throw new ApiUnreachableError()
  }
  if (response.status === 404) return null
  if (!response.ok) throw new Error(`The API answered HTTP ${response.status}`)
  return (await response.json()) as Take
}

/** Where to download one of a finished take's result files. */
export function takeFileUrl(id: string, file: 'out3d.bvh' | 'out3d.json') {
  return `${API_URL}/takes/${encodeURIComponent(id)}/${file}`
}
