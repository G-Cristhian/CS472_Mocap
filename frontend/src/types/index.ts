export type Source = 'ai' | 'suit' | 'review'
export type Accent = 'purple' | 'blue' | 'pink' | 'orange' | 'amber'
export type Pose = 'stand' | 'walk' | 'run' | 'lunge' | 'serve' | 'arms-up'

export interface Project {
  id: string
  name: string
  sport: string
  clips: number
  updated: string
  updatedBy: string
  source: Source
  accent: Accent
  pose: Pose
}

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
