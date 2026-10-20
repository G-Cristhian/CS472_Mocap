export type Source = 'ai' | 'suit' | 'review'
export type Accent = 'purple' | 'blue' | 'pink' | 'orange' | 'amber'
export type Pose = 'stand' | 'walk' | 'run' | 'lunge' | 'serve' | 'arms-up'

/** A folder of motions for one subject, e.g. "Mario" or "Athlete training". */
export interface Project {
  id: string
  name: string
  category: string
  updated: string
}

/** One processed skeleton, built from 2 to 4 recordings. */
export interface Motion {
  id: string
  name: string
  projectId: string
  projectName: string
  duration: string
  source: Source
  accent: Accent
  pose: Pose
  // Where to download the BVH file
  fileUrl?: string
}

/** One video from one camera. Attached to a motion, or not yet. */
export interface Recording {
  id: string
  name: string
  motionId: string | null
  duration: string
  camera: string
  origin: 'upload' | 'stream'
  /** The performer chosen in the API; empty for recordings from the mock data */
  performerId?: number | null
  /** True when the server has a preview image for this recording */
  hasThumbnail?: boolean
}

/** An uploaded clip kept in Supabase. Not used by the Django app; kept with the Supabase code (lib/clips.ts). */
export interface Clip {
  id: string
  name: string
  projectId: string
  projectName: string
  duration: string
  source: Source
  accent: Accent
  pose: Pose
  // Where to download the BVH file
  fileUrl?: string
}

export interface Camera {
  id: number
  label: string
  status: 'streaming' | 'offline'
  resolution: string
  fps: number
}

export type RigStatus = Source

export interface RigPart {
  id: string
  name: string
  status: RigStatus
  confidence: number
  origin: string
  joints: string[]
}
