import type { Camera, Recording, RigPart } from '@/types'

export const recordings: Recording[] = [
  { id: 'mario-walking-cam1', name: 'Camera 1', motionId: 'mario-walking', duration: '0:12', camera: 'CAM 1', origin: 'upload' },
  { id: 'mario-walking-cam2', name: 'Camera 2', motionId: 'mario-walking', duration: '0:12', camera: 'CAM 2', origin: 'upload' },
  { id: 'mario-jumping-cam1', name: 'Camera 1', motionId: 'mario-jumping', duration: '0:08', camera: 'CAM 1', origin: 'upload' },
  { id: 'mario-jumping-cam2', name: 'Camera 2', motionId: 'mario-jumping', duration: '0:08', camera: 'CAM 2', origin: 'upload' },
  { id: 'sprint-cycle-cam1', name: 'Camera 1', motionId: 'sprint-cycle', duration: '0:24', camera: 'CAM 1', origin: 'stream' },
  { id: 'sprint-cycle-cam2', name: 'Camera 2', motionId: 'sprint-cycle', duration: '0:24', camera: 'CAM 2', origin: 'stream' },
  { id: 'serve-cam1', name: 'Camera 1', motionId: 'table-tennis-serve', duration: '0:06', camera: 'CAM 1', origin: 'upload' },
  { id: 'serve-cam2', name: 'Camera 2', motionId: 'table-tennis-serve', duration: '0:06', camera: 'CAM 2', origin: 'upload' },
  { id: 'pocket-drop-cam1', name: 'Camera 1', motionId: 'quarterback-reads', duration: '0:12', camera: 'CAM 1', origin: 'upload' },
  { id: 'pocket-drop-cam2', name: 'Camera 2', motionId: 'quarterback-reads', duration: '0:12', camera: 'CAM 2', origin: 'upload' },
  { id: 'lunge-cam1', name: 'Camera 1', motionId: 'fencing-lunges', duration: '0:08', camera: 'CAM 1', origin: 'upload' },
  { id: 'lunge-cam2', name: 'Camera 2', motionId: 'fencing-lunges', duration: '0:08', camera: 'CAM 2', origin: 'upload' },
  { id: 'shoulder-cam1', name: 'Camera 1', motionId: 'range-of-motion', duration: '0:44', camera: 'CAM 1', origin: 'upload' },
  { id: 'shoulder-cam2', name: 'Camera 2', motionId: 'range-of-motion', duration: '0:44', camera: 'CAM 2', origin: 'upload' },
  { id: 'step-up-cam1', name: 'Camera 1', motionId: 'elevation-tracking', duration: '0:19', camera: 'CAM 1', origin: 'upload' },
  { id: 'step-up-cam2', name: 'Camera 2', motionId: 'elevation-tracking', duration: '0:19', camera: 'CAM 2', origin: 'upload' },
  { id: 'upload-01', name: 'Upload 01', motionId: null, duration: '0:31', camera: 'Upload', origin: 'upload' },
]

export const cameras: Camera[] = [
  { id: 1, label: 'CAM 1', status: 'streaming', resolution: '1920 × 1080', fps: 60 },
  { id: 2, label: 'CAM 2', status: 'streaming', resolution: '1920 × 1080', fps: 60 },
  { id: 3, label: 'CAM 3', status: 'offline', resolution: '1920 × 1080', fps: 60 },
  { id: 4, label: 'CAM 4', status: 'streaming', resolution: '1280 × 720', fps: 30 },
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
