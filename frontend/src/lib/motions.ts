import { DJANGO_URL, djangoJson } from '@/lib/django'
import type { Accent, Motion } from '@/types'

/** A performer, as a motion lists them. */
export interface ApiPerformerRef {
  id: number
  full_name: string
  height_m: number | null
}

/** One camera of a motion: a recording the motion uses. `uuid` is the link's; `recording` is the recording's. */
export interface ApiMotionRecording {
  uuid: string
  recording: string
  name: string
  camera_slot: number
  width: number | null
  height: number | null
  fps: number | null
  duration_s: number | null
  performer: ApiPerformerRef | null
}

/** One output of a motion: a pipeline run, or a manual edit of one. */
export interface ApiMotionVersion {
  uuid: string
  number: number
  source: string
  label: string
  pose_model: string
  status: string
  /** why the render failed, when it did */
  error: string
  created_at: string
}

/** A motion as the Django API returns it. */
export interface ApiMotion {
  uuid: string
  name: string
  /** The projects the motion is in: none, one, or several */
  projects: { uuid: string; name: string }[]
  /** draft until the pipeline has run; then the status of its latest run */
  status: string
  recording_count: number
  /** The cameras: the recordings the motion uses, by camera slot */
  recordings: ApiMotionRecording[]
  /** The performers in those recordings, each once */
  performers: ApiPerformerRef[]
  /** The motion's outputs, oldest first */
  versions: ApiMotionVersion[]
  created_at: string
  updated_at: string
}

export const MOTION_STATUS_LABEL: Record<string, string> = {
  draft: 'Draft',
  queued: 'Queued',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
}

/** Labels for a version's source and pose model, matching the backend's choices. */
export const SOURCE_LABEL: Record<string, string> = { pipeline: 'Pipeline', manual: 'Manual edit' }
export const POSE_LABEL: Record<string, string> = { mediapipe: 'MediaPipe', rtmpose: 'RTMPose' }

const BASE = `${DJANGO_URL}/api/v1/motions/`
const ACCENTS: Accent[] = ['purple', 'blue', 'pink', 'orange', 'amber']

/** Maps an API motion to the card shape the lists use. Duration and source come later, from the pipeline. */
function toMotion(api: ApiMotion): Motion {
  // the accent comes from the id, so a motion keeps its colour between visits
  const seed = Array.from(api.uuid).reduce((sum, c) => sum + c.charCodeAt(0), 0)

  return {
    id: api.uuid,
    name: api.name,
    projects: api.projects.map((p) => ({ id: p.uuid, name: p.name })),
    // no duration until the pipeline has processed the motion; empty hides it on the card
    duration: '',
    source: 'ai',
    accent: ACCENTS[seed % ACCENTS.length],
    pose: 'stand',
  }
}

/** The motions that are in the given project. */
export function motionsInProject(motions: Motion[], projectId: string): Motion[] {
  return motions.filter((m) => m.projects.some((p) => p.id === projectId))
}

/** The logged-in user's motions, newest first. */
export async function listMotions(): Promise<Motion[]> {
  const body = await djangoJson<ApiMotion[]>(BASE)

  return body.map(toMotion)
}

/** One of the logged-in user's motions, with its projects, cameras and performers. Fails for anyone else's. */
export async function getMotion(uuid: string): Promise<ApiMotion> {
  return djangoJson<ApiMotion>(`${BASE}${uuid}/`)
}

/** Creates a motion. With a projectId it goes into that project; with null it goes into none. */
export async function createMotion(input: { name: string; projectId: string | null }): Promise<Motion> {
  const body = await djangoJson<ApiMotion>(BASE, {
    method: 'POST',
    body: JSON.stringify({ name: input.name, project: input.projectId }),
  })

  return toMotion(body)
}

/**
 * Renders the motion as a new version with the given pose model. Answers at once; the version's
 * status (queued, running, done or failed) says how the render is going.
 */
export async function startRendering(motionUuid: string, poseModel: string): Promise<void> {
  await djangoJson(`${BASE}${motionUuid}/versions/`, {
    method: 'POST',
    body: JSON.stringify({ pose_model: poseModel }),
  })
}

/**
 * The skeleton (.bvh) of one finished version, as a local object URL the viewer can play. It is
 * fetched with the login cookie, which the viewer's own loader cannot send. Free it when done.
 */
export async function loadVersionBvh(motionUuid: string, number: number): Promise<string> {
  const response = await fetch(`${BASE}${motionUuid}/versions/${number}/bvh/`, { credentials: 'include' })
  if (!response.ok) throw new Error(`Could not load the skeleton (HTTP ${response.status})`)

  return URL.createObjectURL(await response.blob())
}

/** Puts the motion into a project. A motion can be in several. */
export async function addMotionToProject(motionUuid: string, projectUuid: string): Promise<void> {
  await djangoJson(`${BASE}${motionUuid}/projects/`, {
    method: 'POST',
    body: JSON.stringify({ project: projectUuid }),
  })
}

/**
 * Sets which of the user's recordings the motion uses, all at once: two to four. Recordings that stay keep
 * their camera; the rest are added or taken out. The server refuses a count outside two to four.
 */
export async function setMotionRecordings(motionUuid: string, recordingUuids: string[]): Promise<void> {
  await djangoJson(`${BASE}${motionUuid}/recordings/`, {
    method: 'PUT',
    body: JSON.stringify({ recordings: recordingUuids }),
  })
}
