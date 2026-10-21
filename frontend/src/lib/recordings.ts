import { DJANGO_URL, djangoJson } from '@/lib/django'
import type { Recording } from '@/types'

/** A recording as the Django API returns it. */
export interface ApiRecording {
  uuid: string
  name: string
  performer: number | null
  has_thumbnail: boolean
  lens_source: string
  width: number | null
  height: number | null
  fps: number | null
  duration_s: number | null
  created_at: string
}

const BASE = `${DJANGO_URL}/api/v1/recordings/`

/** Where a recording's preview image comes from. Needs the login cookie, so the image must send credentials. */
export function recordingThumbnailUrl(uuid: string): string {
  return `${BASE}${uuid}/thumbnail/`
}

/** Where a recording's video is played from. Needs the login cookie, so the player must send credentials. */
export function recordingVideoUrl(uuid: string): string {
  return `${BASE}${uuid}/video/`
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)

  return `${m}:${s.toString().padStart(2, '0')}`
}

/** Maps an API recording to the shape the screens use. Motions are not linked yet, so none is set. */
function toRecording(api: Pick<ApiRecording, 'uuid' | 'name'> & Partial<ApiRecording>): Recording {
  return {
    id: api.uuid,
    name: api.name || 'Untitled recording',
    motionId: null,
    duration: api.duration_s ? formatDuration(api.duration_s) : '—',
    camera: 'Upload',
    origin: 'upload',
    performerId: api.performer ?? null,
    hasThumbnail: api.has_thumbnail ?? false,
  }
}

/** The logged-in user's recordings, newest first. */
export async function listRecordings(): Promise<Recording[]> {
  const body = await djangoJson<ApiRecording[]>(BASE)

  return body.map((api) => toRecording(api))
}

/** One of the logged-in user's recordings. Fails for anyone else's. */
export async function getRecording(uuid: string): Promise<Recording> {
  const body = await djangoJson<ApiRecording>(`${BASE}${uuid}/`)

  return toRecording(body)
}

/** Uploads one video. Django creates the Recording for the logged-in user and returns it. */
export async function uploadRecording(file: File): Promise<Recording> {
  const form = new FormData()
  form.append('video', file)

  const body = await djangoJson<ApiRecording>(BASE, { method: 'POST', body: form })

  return toRecording(body)
}

/** Sets which performer a recording belongs to. Pass null to clear it. */
export async function setRecordingPerformer(uuid: string, performerId: number | null): Promise<Recording> {
  const body = await djangoJson<ApiRecording>(`${BASE}${uuid}/`, {
    method: 'PATCH',
    body: JSON.stringify({ performer: performerId }),
  })

  return toRecording(body)
}
