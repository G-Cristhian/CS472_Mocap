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

/** One camera of a take, as GET /takes/{id}/keypoints.json lists them. */
export interface KeypointCamera {
  camera_id: string
  width: number
  height: number
  fps: number
  frames: number
  /** seconds into this camera's video at which the clap happens; null if sync never ran */
  clap_time_s: number | null
}

/** One camera's 2D joints per frame, as GET /takes/{id}/keypoints/{camera}.json returns them. */
export interface Keypoints2D extends Omit<KeypointCamera, 'frames'> {
  /** the 33 MediaPipe joint names, in the order of points[frame] and confidence[frame] */
  joints: string[]
  /** seconds from the start of this video; subtract clap_time_s for the take's clock */
  timestamps: number[]
  /** pixels, origin top-left; null where the detector found nothing */
  points: ([number, number] | null)[][]
  confidence: number[][]
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, { signal })
  } catch (e) {
    if (signal?.aborted) throw e
    throw new ApiUnreachableError()
  }
  if (!response.ok) throw new Error(`The API answered HTTP ${response.status}`)
  return (await response.json()) as T
}

/** The cameras whose 2D joints the API has for a finished take. */
export async function listKeypointCameras(id: string, signal?: AbortSignal): Promise<KeypointCamera[]> {
  const body = await getJson<{ cameras: KeypointCamera[] }>(`${API_URL}/takes/${encodeURIComponent(id)}/keypoints.json`, signal)
  return body.cameras
}

/** One camera's 2D joints for a finished take. */
export function getKeypoints(id: string, camera: string, signal?: AbortSignal): Promise<Keypoints2D> {
  return getJson<Keypoints2D>(`${API_URL}/takes/${encodeURIComponent(id)}/keypoints/${encodeURIComponent(camera)}.json`, signal)
}

export interface NewTake {
  videos: File[]
  heightM: number
  name?: string
  projectId?: string
}

export async function createTake({ videos, heightM, name, projectId }: NewTake): Promise<Take> {
  const form = new FormData()
  form.append('height_m', String(heightM))
  if (name) form.append('name', name)
  if (projectId) form.append('project_id', projectId)
  videos.forEach((file, i) => form.append(`cam${i}`, file, file.name))

  let response: Response
  try {
    response = await fetch(`${API_URL}/takes`, { method: 'POST', body: form })
  } catch {
    throw new ApiUnreachableError()
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `The API answered HTTP ${response.status}`)
  }
  return (await response.json()) as Take
}
