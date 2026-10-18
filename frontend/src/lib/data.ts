import type { Camera, Clip, Project, RigPart } from '@/types'

// Mock calibration suit for the prototype screens. The person's name comes from their account.
export const currentUser = { suit: 'Suit A' }

export const projects: Project[] = [
  {
    id: 'sprint-cycle',
    name: 'Sprint Cycle',
    sport: 'Track & Field',
    clips: 6,
    updated: '2 hours ago',
    updatedBy: 'you',
    source: 'ai',
    accent: 'purple',
    pose: 'stand',
  },
  {
    id: 'quarterback-reads',
    name: 'Quarterback Reads',
    sport: 'Football',
    clips: 12,
    updated: 'Yesterday',
    updatedBy: 'Ada R.',
    source: 'suit',
    accent: 'blue',
    pose: 'walk',
  },
  {
    id: 'fencing-lunges',
    name: 'Fencing Lunges',
    sport: 'Sport',
    clips: 4,
    updated: '3 days ago',
    updatedBy: 'you',
    source: 'ai',
    accent: 'pink',
    pose: 'lunge',
  },
  {
    id: 'range-of-motion',
    name: 'Range of Motion',
    sport: 'Calibration',
    clips: 2,
    updated: '5 days ago',
    updatedBy: 'you',
    source: 'suit',
    accent: 'orange',
    pose: 'stand',
  },
  {
    id: 'table-tennis-serve',
    name: 'Table Tennis Serve',
    sport: 'Sport',
    clips: 9,
    updated: '1 week ago',
    updatedBy: 'Ada R.',
    source: 'ai',
    accent: 'amber',
    pose: 'serve',
  },
  {
    id: 'elevation-tracking',
    name: 'Elevation Tracking',
    sport: 'R&D',
    clips: 3,
    updated: '2 weeks ago',
    updatedBy: 'you',
    source: 'suit',
    accent: 'purple',
    pose: 'arms-up',
  },
]

export const clips: Clip[] = [
  { id: 'take-04', name: 'Take 04', projectId: 'sprint-cycle', projectName: 'Sprint Cycle', duration: '0:24', source: 'ai', accent: 'purple', pose: 'run' },
  { id: 'take-03', name: 'Take 03', projectId: 'sprint-cycle', projectName: 'Sprint Cycle', duration: '0:31', source: 'suit', accent: 'blue', pose: 'walk' },
  { id: 'pocket-drop', name: 'Pocket drop', projectId: 'quarterback-reads', projectName: 'Quarterback Reads', duration: '0:12', source: 'suit', accent: 'blue', pose: 'walk' },
  { id: 'lunge-a', name: 'Lunge A', projectId: 'fencing-lunges', projectName: 'Fencing Lunges', duration: '0:08', source: 'ai', accent: 'pink', pose: 'lunge' },
  { id: 'lunge-b', name: 'Lunge B', projectId: 'fencing-lunges', projectName: 'Fencing Lunges', duration: '0:09', source: 'review', accent: 'amber', pose: 'lunge' },
  { id: 'shoulder-sweep', name: 'Shoulder sweep', projectId: 'range-of-motion', projectName: 'Range of Motion', duration: '0:44', source: 'suit', accent: 'orange', pose: 'arms-up' },
  { id: 'hip-rotation', name: 'Hip rotation', projectId: 'range-of-motion', projectName: 'Range of Motion', duration: '0:38', source: 'suit', accent: 'orange', pose: 'arms-up' },
  { id: 'serve-flat', name: 'Serve — flat', projectId: 'table-tennis-serve', projectName: 'Table Tennis Serve', duration: '0:06', source: 'ai', accent: 'purple', pose: 'serve' },
  { id: 'serve-topspin', name: 'Serve — topspin', projectId: 'table-tennis-serve', projectName: 'Table Tennis Serve', duration: '0:07', source: 'ai', accent: 'purple', pose: 'serve' },
  { id: 'step-up-test', name: 'Step-up test', projectId: 'elevation-tracking', projectName: 'Elevation Tracking', duration: '0:19', source: 'review', accent: 'amber', pose: 'lunge' },
]

export const cameras: Camera[] = [
  { id: 1, label: 'CAM 1', status: 'streaming', resolution: '1920 × 1080', fps: 60 },
  { id: 2, label: 'CAM 2', status: 'streaming', resolution: '1920 × 1080', fps: 60 },
  { id: 3, label: 'CAM 3', status: 'offline', resolution: '1920 × 1080', fps: 60 },
  { id: 4, label: 'CAM 4', status: 'streaming', resolution: '1280 × 720', fps: 30 },
]

export const takes = [
  { id: 'take-04', name: 'Take 04', duration: '0:24' },
  { id: 'take-03', name: 'Take 03', duration: '0:31' },
  { id: 'take-02', name: 'Take 02', duration: '0:18' },
  { id: 'take-01', name: 'Take 01', duration: '0:22' },
]

export const rigParts: RigPart[] = [
  { id: 'head', name: 'Head and neck', status: 'ai', confidence: 91, origin: 'Inferred from three cameras — the suit has no head sensor.', joints: ['head', 'neck'] },
  { id: 'spine', name: 'Spine and hips', status: 'suit', confidence: 99, origin: 'Read straight from the suit spine and hip markers.', joints: ['chest', 'pelvis', 'l-shoulder', 'r-shoulder'] },
  { id: 'left-forearm', name: 'Left forearm', status: 'ai', confidence: 87, origin: 'Blended from the shoulder marker and two cameras.', joints: ['l-elbow', 'l-wrist'] },
  { id: 'right-forearm', name: 'Right forearm', status: 'ai', confidence: 84, origin: 'Blended from the shoulder marker and two cameras.', joints: ['r-elbow', 'r-wrist'] },
  { id: 'left-leg', name: 'Left leg', status: 'suit', confidence: 98, origin: 'Suit thigh and shin markers, no gap filling needed.', joints: ['l-knee'] },
  { id: 'right-leg', name: 'Right leg', status: 'suit', confidence: 97, origin: 'Suit thigh and shin markers, no gap filling needed.', joints: ['r-knee'] },
  { id: 'left-foot', name: 'Left foot', status: 'review', confidence: 52, origin: 'Camera 3 dropped for 1.4s — the foot slides through the floor.', joints: ['l-foot'] },
  { id: 'right-foot', name: 'Right foot', status: 'suit', confidence: 96, origin: 'Suit ankle marker with floor lock applied.', joints: ['r-foot'] },
]

export const savedDevices = [
  { id: 'suit-a', name: 'Suit A', kind: 'Full-body suit · 17 markers', status: 'Connected', battery: 82, lastSeen: 'Now' },
  { id: 'suit-b', name: 'Suit B', kind: 'Full-body suit · 17 markers', status: 'Idle', battery: 41, lastSeen: '2 days ago' },
  { id: 'gloves-1', name: 'Gloves — pair 1', kind: 'Finger capture · 10 sensors', status: 'Idle', battery: 64, lastSeen: 'Yesterday' },
  { id: 'cam-rig', name: 'Camera rig — Studio B', kind: '4 cameras · genlocked', status: '3 of 4 online', battery: 100, lastSeen: 'Now' },
]

export const sourceLabel: Record<string, string> = {
  ai: 'AI',
  suit: 'Suit',
  review: 'Review',
}

export function projectById(id: string | undefined) {
  return projects.find((p) => p.id === id)
}

export function clipsForProject(id: string | undefined) {
  return clips.filter((c) => c.projectId === id)
}
