import { AnimationMixer, Bone, Vector3 } from 'three'
import { BVHLoader } from 'three/examples/jsm/loaders/BVHLoader.js'

/**
 * A take ready to draw: every joint's position (metres, Y up) on every frame,
 * plus which joints are joined by a bone. Built from either a .bvh (the
 * pipeline's skeleton animation) or out3d.json (the pipeline's raw 3D joints).
 */
export interface Motion {
  name: string
  kind: 'bvh' | 'landmarks'
  /** joint names, as in the file */
  joints: string[]
  /** for each joint, the viewport joint id it stands for (rig parts use these), or null */
  partJoints: (string | null)[]
  /** pairs of joint indices drawn as bones */
  bones: [number, number][]
  /** seconds of each frame */
  times: Float32Array
  /** frames x joints x 3, metres; NaN where a joint is missing */
  positions: Float32Array
  duration: number
  fps: number
}

/** BVH joint name (the pipeline's H36M skeleton) -> viewport joint id used by the rig parts */
const BVH_PART_JOINTS: Record<string, string> = {
  Hip: 'pelvis',
  Thorax: 'chest',
  Neck: 'neck',
  NeckEnd: 'head',
  LeftShoulder: 'l-shoulder',
  LeftElbow: 'l-elbow',
  LeftWrist: 'l-wrist',
  LeftKnee: 'l-knee',
  LeftAnkle: 'l-foot',
  RightShoulder: 'r-shoulder',
  RightElbow: 'r-elbow',
  RightWrist: 'r-wrist',
  RightKnee: 'r-knee',
  RightAnkle: 'r-foot',
}

/** The 33 MediaPipe pose landmarks, in index order (backend/mocap_pipeline/joints.py) */
export const MEDIAPIPE_JOINTS = [
  'NOSE', 'LEFT_EYE_INNER', 'LEFT_EYE', 'LEFT_EYE_OUTER',
  'RIGHT_EYE_INNER', 'RIGHT_EYE', 'RIGHT_EYE_OUTER',
  'LEFT_EAR', 'RIGHT_EAR', 'MOUTH_LEFT', 'MOUTH_RIGHT',
  'LEFT_SHOULDER', 'RIGHT_SHOULDER', 'LEFT_ELBOW', 'RIGHT_ELBOW',
  'LEFT_WRIST', 'RIGHT_WRIST', 'LEFT_PINKY', 'RIGHT_PINKY',
  'LEFT_INDEX', 'RIGHT_INDEX', 'LEFT_THUMB', 'RIGHT_THUMB',
  'LEFT_HIP', 'RIGHT_HIP', 'LEFT_KNEE', 'RIGHT_KNEE',
  'LEFT_ANKLE', 'RIGHT_ANKLE', 'LEFT_HEEL', 'RIGHT_HEEL',
  'LEFT_FOOT_INDEX', 'RIGHT_FOOT_INDEX',
]

/** MediaPipe's pose connections (POSE_CONNECTIONS), as landmark index pairs */
const MEDIAPIPE_CONNECTIONS: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 7], [0, 4], [4, 5], [5, 6], [6, 8], [9, 10],
  [11, 12], [11, 13], [13, 15], [15, 17], [15, 19], [15, 21], [17, 19],
  [12, 14], [14, 16], [16, 18], [16, 20], [16, 22], [18, 20],
  [11, 23], [12, 24], [23, 24], [23, 25], [24, 26], [25, 27], [26, 28],
  [27, 29], [28, 30], [29, 31], [30, 32], [27, 31], [28, 32],
]

const MEDIAPIPE_PART_JOINTS: Record<string, string> = {
  NOSE: 'head',
  LEFT_SHOULDER: 'l-shoulder',
  LEFT_ELBOW: 'l-elbow',
  LEFT_WRIST: 'l-wrist',
  LEFT_HIP: 'pelvis',
  LEFT_KNEE: 'l-knee',
  LEFT_ANKLE: 'l-foot',
  RIGHT_SHOULDER: 'r-shoulder',
  RIGHT_ELBOW: 'r-elbow',
  RIGHT_WRIST: 'r-wrist',
  RIGHT_HIP: 'pelvis',
  RIGHT_KNEE: 'r-knee',
  RIGHT_ANKLE: 'r-foot',
}

/**
 * .bvh -> Motion. Parsed and played with three's BVHLoader; every frame's
 * bone positions are worked out once up front so playback only interpolates.
 * BVH is in centimetres by convention, so positions are scaled to metres.
 */
export function motionFromBvh(text: string, name: string, unitsToMetres = 0.01): Motion {
  const { skeleton, clip } = new BVHLoader().parse(text)
  const bones = skeleton.bones
  const root = bones[0]
  if (!root) throw new Error('This .bvh has no joints')

  // end sites have no name in BVH; call them after their parent
  const joints = bones.map((b) => (b.name === 'ENDSITE' && b.parent ? `${b.parent.name}End` : b.name))
  const index = new Map<Bone, number>(bones.map((b, i) => [b, i]))
  const boneLinks: [number, number][] = []
  bones.forEach((b, i) => {
    const parent = b.parent instanceof Bone ? index.get(b.parent) : undefined
    if (parent !== undefined) boneLinks.push([parent, i])
  })

  const track = clip.tracks[0]
  const frameTimes = track ? track.times : new Float32Array([0])
  const frames = frameTimes.length
  const fps = frames > 1 ? 1 / (frameTimes[1] - frameTimes[0]) : 30

  const mixer = new AnimationMixer(root)
  mixer.clipAction(clip).play()
  const positions = new Float32Array(frames * bones.length * 3)
  const p = new Vector3()
  for (let f = 0; f < frames; f++) {
    mixer.setTime(frameTimes[f])
    root.updateMatrixWorld(true)
    bones.forEach((bone, j) => {
      bone.getWorldPosition(p)
      positions.set([p.x * unitsToMetres, p.y * unitsToMetres, p.z * unitsToMetres], (f * bones.length + j) * 3)
    })
  }
  mixer.stopAllAction()

  return {
    name,
    kind: 'bvh',
    joints,
    partJoints: joints.map((j) => BVH_PART_JOINTS[j] ?? null),
    bones: boneLinks,
    times: Float32Array.from(frameTimes),
    positions,
    duration: frameTimes[frames - 1] ?? 0,
    fps,
  }
}

interface LandmarkFrame {
  t: number
  landmarks: Record<string, { x: number; y: number; z: number } | null>
}

/** out3d.json (pipeline output: [{t, landmarks: {NOSE: {x, y, z} | null, ...}}, ...]) -> Motion */
export function motionFromLandmarksJson(text: string, name: string): Motion {
  const data = JSON.parse(text) as unknown
  if (!Array.isArray(data) || data.length === 0 || typeof (data[0] as LandmarkFrame).landmarks !== 'object') {
    throw new Error('Not a pipeline out3d.json (expected a list of {t, landmarks} frames)')
  }
  const frames = data as LandmarkFrame[]
  const J = MEDIAPIPE_JOINTS.length
  const positions = new Float32Array(frames.length * J * 3).fill(NaN)
  const times = new Float32Array(frames.length)
  frames.forEach((frame, f) => {
    times[f] = frame.t
    MEDIAPIPE_JOINTS.forEach((joint, j) => {
      const p = frame.landmarks[joint]
      if (p) positions.set([p.x, p.y, p.z], (f * J + j) * 3)
    })
  })
  const duration = times[times.length - 1] - times[0]
  return {
    name,
    kind: 'landmarks',
    joints: MEDIAPIPE_JOINTS,
    partJoints: MEDIAPIPE_JOINTS.map((j) => MEDIAPIPE_PART_JOINTS[j] ?? null),
    bones: MEDIAPIPE_CONNECTIONS,
    times,
    positions,
    duration,
    fps: frames.length > 1 ? (frames.length - 1) / Math.max(duration, 1e-6) : 30,
  }
}

/** A .bvh or .json file's text -> Motion, by extension (or by sniffing the content). */
export function parseMotion(text: string, fileName: string): Motion {
  const lower = fileName.toLowerCase()
  if (lower.endsWith('.bvh') || text.trimStart().startsWith('HIERARCHY')) return motionFromBvh(text, fileName)
  if (lower.endsWith('.json') || text.trimStart().startsWith('[')) return motionFromLandmarksJson(text, fileName)
  throw new Error('Open a .bvh or an out3d.json file')
}

/**
 * Joint positions at time t (seconds from the start of the take), linearly
 * interpolated between the two nearest frames. A joint missing in either
 * frame comes out as NaN. Writes into `out` (joints x 3).
 */
export function samplePositions(motion: Motion, t: number, out: Float32Array): void {
  const { times, positions } = motion
  const J = motion.joints.length
  const start = times[0]
  const time = start + Math.min(Math.max(t, 0), motion.duration)

  // binary search for the frame at or before `time`
  let lo = 0
  let hi = times.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (times[mid] <= time) lo = mid
    else hi = mid - 1
  }
  const next = Math.min(lo + 1, times.length - 1)
  const span = times[next] - times[lo]
  const w = span > 0 ? (time - times[lo]) / span : 0
  const a = lo * J * 3
  const b = next * J * 3
  for (let i = 0; i < J * 3; i++) {
    out[i] = positions[a + i] * (1 - w) + positions[b + i] * w
  }
}

/** Box around every position in the take (ignoring missing joints), for framing the camera. */
export function motionBounds(motion: Motion) {
  const min = [Infinity, Infinity, Infinity]
  const max = [-Infinity, -Infinity, -Infinity]
  const { positions } = motion
  for (let i = 0; i < positions.length; i += 3) {
    for (let k = 0; k < 3; k++) {
      const v = positions[i + k]
      if (Number.isFinite(v)) {
        min[k] = Math.min(min[k], v)
        max[k] = Math.max(max[k], v)
      }
    }
  }
  if (!Number.isFinite(min[0])) return { min: [-1, 0, -1], max: [1, 2, 1] }
  return { min, max }
}
