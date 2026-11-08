/**
 * A run's frame-by-frame numbers (backend/mocap_pipeline/report.py writes
 * <out>.report.json) turned into what the result panel shows: the colour of
 * each joint at each moment and the key that explains it, the cameras and
 * which is worst, which joints were hard to track and when, and the series
 * for the timelines. Pure, so it is tested on its own (test/report.test.cjs).
 */
import { LIMITS, type MmScale } from './metrics'

export type Point = [number | null, number | null]

export interface ReportCamera {
  id: string
  width: number
  height: number
  position: [number, number, number]
  forward: [number, number, number]
  up: [number, number, number]
  focal_px: number
  centre_px: [number, number]
  calibration_error_px: number | null
  distance_m: number | null
  mm_per_px: number | null
}

export interface ReportPerCamera {
  id: string
  error_px: (number | null)[]
  error_mm: (number | null)[]
  seen: number[]
  mean_error_px: number | null
  mean_error_mm: number | null
  lost_fraction: number
  points: Point[][]
  reprojected: Point[][]
}

export interface Report {
  version: number
  fps: number
  times: (number | null)[]
  joints: string[]
  thresholds: { min_confidence: number; max_reprojection_px: number }
  cameras: ReportCamera[]
  performer_centre: (number | null)[]
  per_camera: ReportPerCamera[]
  joint_views: number[][]
  joint_error_px: (number | null)[][]
  joint_error_mm: (number | null)[][]
  /** metres per second per frame and joint, after smoothing */
  joint_speed: (number | null)[][]
}

export const REPORT_VERSION = 3

export function parseReport(text: string): Report {
  const r = JSON.parse(text) as Report
  if (r.version !== REPORT_VERSION) throw new Error(`report version ${r.version}, this app reads ${REPORT_VERSION}`)
  return r
}

export const frameCount = (r: Report) => r.times.length

/** The report frame shown at t seconds of the BVH (both are the pipeline's 30 fps shared clock). */
export function frameAt(r: Report, t: number): number {
  return Math.max(0, Math.min(frameCount(r) - 1, Math.round(t * r.fps)))
}

/** "RIGHT_FOOT_INDEX" -> "right toes" */
export function prettyJoint(name: string): string {
  return name.toLowerCase().replace('foot_index', 'toes').replace(/_/g, ' ')
}

function median(values: number[]): number | null {
  if (!values.length) return null
  const s = [...values].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/** How many millimetres one pixel is at the performer, per camera and overall. */
export function mmScale(r: Report): MmScale {
  const perCamera: Record<string, number> = {}
  for (const c of r.cameras) if (c.mm_per_px) perCamera[c.id] = c.mm_per_px
  return { perCamera, median: median(Object.values(perCamera)) }
}

const mmText = (px: number, mmPerPx: number | null) => (mmPerPx ? ` (about ${Math.round(px * mmPerPx)} mm)` : '')
const pct = (fraction: number) => `${(fraction * 100).toFixed(fraction < 0.1 ? 1 : 0)} %`

// ---- the skeleton's colours and their key ----------------------------------------------------

export type ColourMode = 'error' | 'views' | 'plain'
/** good / mid / bad like the numbers; none = no 3D point in this frame (filled in by the smoother) */
export type JointState = 'good' | 'mid' | 'bad' | 'none'

export const STATE_COLOURS: Record<JointState, string> = {
  good: '#3fb950',
  mid: '#d29922',
  bad: '#f85149',
  none: '#a371f7',
}

/** Which tracked joints each BVH joint is built from (backend joints.py, RIG_JOINT_SOURCES). */
export const RIG_SOURCES: Record<string, string[]> = {
  Hip: ['LEFT_HIP', 'RIGHT_HIP'],
  RightHip: ['RIGHT_HIP'],
  RightKnee: ['RIGHT_KNEE'],
  RightAnkle: ['RIGHT_ANKLE'],
  LeftHip: ['LEFT_HIP'],
  LeftKnee: ['LEFT_KNEE'],
  LeftAnkle: ['LEFT_ANKLE'],
  Spine: ['LEFT_HIP', 'RIGHT_HIP', 'LEFT_SHOULDER', 'RIGHT_SHOULDER'],
  Thorax: ['LEFT_SHOULDER', 'RIGHT_SHOULDER'],
  Neck: ['LEFT_SHOULDER', 'RIGHT_SHOULDER', 'LEFT_EAR', 'RIGHT_EAR'],
  Head: ['LEFT_EAR', 'RIGHT_EAR', 'LEFT_SHOULDER', 'RIGHT_SHOULDER'],
  LeftShoulder: ['LEFT_SHOULDER'],
  LeftElbow: ['LEFT_ELBOW'],
  LeftWrist: ['LEFT_WRIST'],
  RightShoulder: ['RIGHT_SHOULDER'],
  RightElbow: ['RIGHT_ELBOW'],
  RightWrist: ['RIGHT_WRIST'],
}

const WORSE: JointState[] = ['good', 'mid', 'bad', 'none']

export function jointState(r: Report, frame: number, joint: number, mode: ColourMode): JointState {
  const views = r.joint_views[frame]?.[joint] ?? 0
  if (views === 0) return 'none'
  if (mode === 'views') return views >= r.cameras.length ? 'good' : 'mid'
  const px = r.joint_error_px[frame]?.[joint]
  if (px === null || px === undefined) return 'mid'
  return px <= LIMITS.px.good ? 'good' : px >= LIMITS.px.bad ? 'bad' : 'mid'
}

/** A BVH joint's state: the worst of the tracked joints it is built from; null when none are tracked. */
export function rigState(r: Report, frame: number, rigJoint: string, mode: ColourMode): JointState | null {
  const sources = (RIG_SOURCES[rigJoint] ?? []).map((n) => r.joints.indexOf(n)).filter((j) => j >= 0)
  if (!sources.length || mode === 'plain') return null
  let worst = 0
  for (const j of sources) worst = Math.max(worst, WORSE.indexOf(jointState(r, frame, j, mode)))
  return WORSE[worst]
}

export interface KeyEntry {
  state: JointState
  label: string
}

/** The key under the viewer: what each colour means, with the numbers behind it. */
export function colourKey(mode: ColourMode, r: Report | null): KeyEntry[] {
  const mm = r ? mmScale(r).median : null
  const none: KeyEntry = { state: 'none', label: 'no 3D point: fewer than 2 cameras saw it, the smoother filled it in' }
  if (mode === 'views') {
    const n = r?.cameras.length ?? 3
    return n > 2
      ? [
          { state: 'good', label: `seen by all ${n} cameras` },
          { state: 'mid', label: n === 3 ? 'seen by 2 cameras' : `seen by 2 to ${n - 1} cameras` },
          none,
        ]
      : [{ state: 'good', label: 'seen by both cameras' }, none]
  }
  if (mode === 'plain') return []
  return [
    { state: 'good', label: `cameras agree within ${LIMITS.px.good} px${mmText(LIMITS.px.good, mm)}` },
    { state: 'mid', label: `${LIMITS.px.good} to ${LIMITS.px.bad} px apart` },
    { state: 'bad', label: `${LIMITS.px.bad} px or more${mmText(LIMITS.px.bad, mm)}` },
    none,
  ]
}

// ---- cameras ---------------------------------------------------------------------------------

export interface CameraLine {
  id: string
  errorPx: number | null
  errorMm: number | null
  lostFraction: number
  calibrationPx: number | null
  mmPerPx: number | null
  distanceM: number | null
  /** the joints this camera disagreed on most, pixels, worst first */
  worstJoints: { joint: string; px: number }[]
}

function dist(a: Point | undefined, b: Point | undefined): number | null {
  if (!a || !b || a[0] === null || a[1] === null || b[0] === null || b[1] === null) return null
  return Math.hypot(a[0] - b[0], a[1] - b[1])
}

/** Mean pixel gap per joint for one camera, over the frames where it saw the joint and a 3D point exists. */
export function cameraJointErrors(r: Report, c: number): number[] {
  const cam = r.per_camera[c]
  const sums = r.joints.map(() => 0)
  const counts = r.joints.map(() => 0)
  for (let f = 0; f < frameCount(r); f++) {
    for (let j = 0; j < r.joints.length; j++) {
      const d = dist(cam.points[f]?.[j], cam.reprojected[f]?.[j])
      if (d !== null) {
        sums[j] += d
        counts[j]++
      }
    }
  }
  return sums.map((s, j) => (counts[j] ? s / counts[j] : NaN))
}

/** Every camera, worst first by how far its 2D joints are from the 3D skeleton. */
export function cameraLines(r: Report): CameraLine[] {
  const lines = r.cameras.map((cam, c): CameraLine => {
    const pc = r.per_camera[c]
    const perJoint = cameraJointErrors(r, c)
    return {
      id: cam.id,
      errorPx: pc.mean_error_px,
      errorMm: pc.mean_error_mm,
      lostFraction: pc.lost_fraction,
      calibrationPx: cam.calibration_error_px,
      mmPerPx: cam.mm_per_px,
      distanceM: cam.distance_m,
      worstJoints: r.joints
        .map((joint, j) => ({ joint, px: perJoint[j] }))
        .filter((x) => isFinite(x.px))
        .sort((a, b) => b.px - a.px)
        .slice(0, 3),
    }
  })
  return lines.sort((a, b) => (b.errorMm ?? -1) - (a.errorMm ?? -1))
}

/** Degrees between two cameras' lines of sight to the performer, every pair, narrowest first. */
export function pairAngles(r: Report): { a: string; b: string; degrees: number }[] {
  const centre = r.performer_centre
  if (!centre || centre.some((v) => v === null)) return []
  const dirs = r.cameras.map((c) => {
    const v = c.position.map((p, i) => p - (centre[i] as number))
    const n = Math.hypot(...v) || 1
    return v.map((x) => x / n)
  })
  const out: { a: string; b: string; degrees: number }[] = []
  for (let i = 0; i < dirs.length; i++) {
    for (let k = i + 1; k < dirs.length; k++) {
      const dot = dirs[i].reduce((s, x, n) => s + x * dirs[k][n], 0)
      out.push({ a: r.cameras[i].id, b: r.cameras[k].id, degrees: (Math.acos(Math.max(-1, Math.min(1, dot))) * 180) / Math.PI })
    }
  }
  return out.sort((x, y) => x.degrees - y.degrees)
}

/** Below this, two cameras see the performer from nearly the same side (team rule of thumb, desktop-tester.md). */
export const NARROW_PAIR_DEG = 30

/** The camera story: which camera is worst, by how much, and why it might be. */
export function cameraStory(r: Report): string[] {
  const lines = cameraLines(r)
  if (!lines.length || lines[0].errorPx === null) return []
  const worst = lines[0]
  const best = lines[lines.length - 1]
  const out: string[] = []
  out.push(
    `${worst.id} is the worst camera: its 2D joints are on average ${worst.errorPx!.toFixed(1)} px`
      + (worst.errorMm !== null ? ` (about ${worst.errorMm.toFixed(0)} mm at the performer)` : '')
      + ' from where the 3D skeleton lands in its picture'
      + (best !== worst && best.errorPx !== null ? `, against ${best.errorPx.toFixed(1)} px for ${best.id}, the best.` : '.'),
  )
  if (worst.worstJoints.length) {
    out.push(`It disagreed most on the ${worst.worstJoints.map((w) => `${prettyJoint(w.joint)} (${w.px.toFixed(0)} px)`).join(', ')}.`)
  }
  if (worst.lostFraction > 0) out.push(`It saw no one in ${pct(worst.lostFraction)} of the frames.`)
  if (worst.calibrationPx !== null) {
    out.push(`Its calibration error is ${worst.calibrationPx.toFixed(1)} px${mmText(worst.calibrationPx, worst.mmPerPx)}.`)
  }
  const pairs = pairAngles(r)
  if (pairs.length && pairs[0].degrees < NARROW_PAIR_DEG) {
    const p = pairs[0]
    const widest = pairs[pairs.length - 1]
    out.push(
      `${p.a} and ${p.b} look at the performer from nearly the same direction (${p.degrees.toFixed(0)}° apart), `
        + 'so between them they pin down depth poorly'
        + (widest !== p ? `; the widest pair is ${widest.a} and ${widest.b} (${widest.degrees.toFixed(0)}°).` : '.'),
    )
  }
  return out
}

// ---- joints ----------------------------------------------------------------------------------

export interface JointLine {
  joint: string
  /** frames with no 3D point (fewer than 2 cameras saw it, or the cameras disagreed too much) */
  lostFraction: number
  lostFrames: number
  /** the longest run of such frames, in seconds of the shared clock */
  longestGap: { start: number; end: number; frames: number } | null
  errorPx: number | null
  errorMm: number | null
  /** per camera, the share of frames it did not see this joint confidently, most first */
  missedBy: { camera: string; fraction: number }[]
  /** the camera whose 2D was furthest from the 3D point, pixels */
  furthest: { camera: string; px: number } | null
}

function mean(values: (number | null | undefined)[]): number | null {
  let s = 0
  let n = 0
  for (const v of values) {
    if (typeof v === 'number' && isFinite(v)) {
      s += v
      n++
    }
  }
  return n ? s / n : null
}

/** Every tracked joint, the hardest first: most often without a 3D point, then the largest error. */
export function jointLines(r: Report): JointLine[] {
  const n = frameCount(r)
  const camErrors = r.cameras.map((_, c) => cameraJointErrors(r, c))
  const time = (f: number) => r.times[f] ?? f / r.fps
  return r.joints
    .map((joint, j): JointLine => {
      let lost = 0
      let run = 0
      let best: JointLine['longestGap'] = null
      for (let f = 0; f <= n; f++) {
        const isLost = f < n && (r.joint_views[f]?.[j] ?? 0) === 0
        if (isLost) {
          lost++
          run++
        } else if (run) {
          if (!best || run > best.frames) best = { start: time(f - run), end: time(f - 1) + 1 / r.fps, frames: run }
          run = 0
        }
      }
      const missedBy = r.per_camera
        .map((pc) => {
          let missed = 0
          for (let f = 0; f < n; f++) {
            const p = pc.points[f]?.[j]
            if (!p || p[0] === null) missed++
          }
          return { camera: pc.id, fraction: n ? missed / n : 0 }
        })
        .sort((a, b) => b.fraction - a.fraction)
      const furthest = r.cameras
        .map((c, k) => ({ camera: c.id, px: camErrors[k][j] }))
        .filter((x) => isFinite(x.px))
        .sort((a, b) => b.px - a.px)[0] ?? null
      return {
        joint,
        lostFraction: n ? lost / n : 0,
        lostFrames: lost,
        longestGap: best,
        errorPx: mean(r.joint_error_px.map((row) => row[j])),
        errorMm: mean(r.joint_error_mm.map((row) => row[j])),
        missedBy,
        furthest,
      }
    })
    .sort((a, b) => b.lostFraction - a.lostFraction || (b.errorPx ?? 0) - (a.errorPx ?? 0))
}

/** One joint's story in a sentence or three. */
export function jointStory(line: JointLine, frames: number): string {
  const name = prettyJoint(line.joint)
  const parts: string[] = []
  if (line.lostFrames) {
    let s = `${name[0].toUpperCase()}${name.slice(1)} had no 3D position in ${pct(line.lostFraction)} of frames (${line.lostFrames} of ${frames})`
    if (line.longestGap && line.longestGap.frames > 1) {
      s += `, the longest stretch ${(line.longestGap.end - line.longestGap.start).toFixed(1)} s from ${line.longestGap.start.toFixed(1)} s to ${line.longestGap.end.toFixed(1)} s`
    }
    parts.push(s + '.')
  } else {
    parts.push(`${name[0].toUpperCase()}${name.slice(1)} had a 3D position in every frame.`)
  }
  const missed = line.missedBy.filter((m) => m.fraction >= 0.01)
  if (missed.length) {
    parts.push(
      missed.map((m, i) => `${m.camera}${i ? ' in' : ' did not see it confidently in'} ${pct(m.fraction)}`).join(', ')
        + ' of frames.',
    )
  }
  if (line.errorPx !== null) {
    parts.push(
      `When found, the cameras disagreed by ${line.errorPx.toFixed(1)} px`
        + (line.errorMm !== null ? ` (about ${line.errorMm.toFixed(0)} mm)` : '')
        + (line.furthest ? `, ${line.furthest.camera} most (${line.furthest.px.toFixed(0)} px).` : '.'),
    )
  }
  return parts.join(' ')
}

export const BODY_PARTS: Record<string, string[]> = {
  head: ['NOSE', 'LEFT_EYE_INNER', 'LEFT_EYE', 'LEFT_EYE_OUTER', 'RIGHT_EYE_INNER', 'RIGHT_EYE', 'RIGHT_EYE_OUTER', 'LEFT_EAR', 'RIGHT_EAR', 'MOUTH_LEFT', 'MOUTH_RIGHT'],
  torso: ['LEFT_SHOULDER', 'RIGHT_SHOULDER', 'LEFT_HIP', 'RIGHT_HIP'],
  'left arm': ['LEFT_ELBOW', 'LEFT_WRIST', 'LEFT_PINKY', 'LEFT_INDEX', 'LEFT_THUMB'],
  'right arm': ['RIGHT_ELBOW', 'RIGHT_WRIST', 'RIGHT_PINKY', 'RIGHT_INDEX', 'RIGHT_THUMB'],
  'left leg': ['LEFT_KNEE', 'LEFT_ANKLE', 'LEFT_HEEL', 'LEFT_FOOT_INDEX'],
  'right leg': ['RIGHT_KNEE', 'RIGHT_ANKLE', 'RIGHT_HEEL', 'RIGHT_FOOT_INDEX'],
}

/** Body parts, hardest first, by the mean of their joints' lost share and error. */
export function bodyParts(lines: JointLine[]): { part: string; lostFraction: number; errorPx: number | null }[] {
  return Object.entries(BODY_PARTS)
    .map(([part, names]) => {
      const mine = lines.filter((l) => names.includes(l.joint))
      return { part, lostFraction: mean(mine.map((l) => l.lostFraction)) ?? 0, errorPx: mean(mine.map((l) => l.errorPx)), count: mine.length }
    })
    .filter((p) => p.count)
    .sort((a, b) => b.lostFraction - a.lostFraction || (b.errorPx ?? 0) - (a.errorPx ?? 0))
    .map(({ part, lostFraction, errorPx }) => ({ part, lostFraction, errorPx }))
}

export function bodyStory(lines: JointLine[]): string {
  const parts = bodyParts(lines)
  if (parts.length < 2) return ''
  const hard = parts[0]
  const easy = parts[parts.length - 1]
  const what = (p: typeof hard) =>
    `${pct(p.lostFraction)} of frames without a 3D position` + (p.errorPx !== null ? `, ${p.errorPx.toFixed(1)} px apart when found` : '')
  return `The ${hard.part} was the hardest to track (${what(hard)}); the ${easy.part} the easiest (${what(easy)}).`
}

// ---- flags: stretches of the take where joints were lost or the cameras disagreed --------------

/**
 * A joint is in trouble in a frame when it has no 3D position, or when the
 * cameras disagree on it by the guide's red limit or more. Trouble lasting at
 * least minFrames (with gaps of up to bridgeFrames inside) is a joint's
 * stretch. Stretches of different joints that cover mostly the same time
 * (intersection over union of at least sameTime, each widened by padFrames)
 * make one flag, so one joint lost for the whole take does not swallow the
 * short problems of the others; flags may overlap.
 */
export const FLAG_RULES = { minFrames: 3, bridgeFrames: 3, padFrames: 3, sameTime: 0.3, spikePx: LIMITS.px.bad, fastShare: 0.1, majorWeight: 15 }

/** A flag worth reading in full: at least majorWeight joint-frames in trouble (half a second of one joint, or 5 joints for 3 frames). */
/** config.MAX_REPROJECTION_ERROR_PX: a view further off than this is dropped by triangulation */
const MAX_KEPT_PX = 15

export const isMajor = (flag: Flag) => flag.weight >= FLAG_RULES.majorWeight

export interface FlagJoint {
  joint: string
  /** frames of the flag in which this joint had no 3D position */
  lostFrames: number
  /** frames of the flag in which the cameras were spikePx or more apart on it */
  spikeFrames: number
  peakPx: number | null
  /** the camera most to blame: the one that missed it most when that explains the loss, else the one furthest off */
  camera: { id: string; missed: number; px: number | null; why: 'missed' | 'off' } | null
  /** fastest speed in the flag, m/s, and the share of the take the joint moves at least that fast */
  speed: { mps: number; fasterShare: number } | null
}

export interface Flag {
  start: number
  end: number
  startFrame: number
  endFrame: number
  kind: 'lost' | 'spike' | 'both'
  joints: FlagJoint[]
  /** cameras that saw no one in at least half of the flag's frames */
  sawNoOne: string[]
  /** joint-frames in trouble: how bad the flag is, for ranking */
  weight: number
}

function speedRank(r: Report, j: number): number[] {
  const values: number[] = []
  for (const row of r.joint_speed ?? []) {
    const v = row[j]
    if (typeof v === 'number' && isFinite(v)) values.push(v)
  }
  return values.sort((a, b) => a - b)
}

/** Every flag in the take, in time order. */
export function findFlags(r: Report): Flag[] {
  const n = frameCount(r)
  const rules = FLAG_RULES
  // 1. each joint's stretches of trouble
  const stretches: { j: number; a: number; b: number }[] = []
  r.joints.forEach((_, j) => {
    let start = -1
    let last = -1
    let count = 0
    const close = () => {
      if (start >= 0 && count >= rules.minFrames) stretches.push({ j, a: start, b: last })
      start = -1
      count = 0
    }
    for (let f = 0; f < n; f++) {
      const views = r.joint_views[f]?.[j] ?? 0
      const px = r.joint_error_px[f]?.[j]
      const bad = views === 0 || (typeof px === 'number' && px >= rules.spikePx)
      if (!bad) continue
      if (start >= 0 && f - last > rules.bridgeFrames + 1) close()
      if (start < 0) start = f
      last = f
      count++
    }
    close()
  })
  // 2. stretches over mostly the same time make one flag
  stretches.sort((x, y) => x.a - y.a || y.b - x.b)
  const groups: { a: number; b: number; joints: Set<number> }[] = []
  const iou = (a0: number, b0: number, a1: number, b1: number) => {
    const p = rules.padFrames
    const inter = Math.min(b0 + p, b1 + p) - Math.max(a0 - p, a1 - p) + 1
    const union = Math.max(b0 + p, b1 + p) - Math.min(a0 - p, a1 - p) + 1
    return inter > 0 ? inter / union : 0
  }
  for (const s of stretches) {
    let best: (typeof groups)[number] | null = null
    let bestScore = rules.sameTime
    for (const g of groups) {
      const score = iou(s.a, s.b, g.a, g.b)
      if (score >= bestScore) {
        best = g
        bestScore = score
      }
    }
    if (best) {
      best.a = Math.min(best.a, s.a)
      best.b = Math.max(best.b, s.b)
      best.joints.add(s.j)
    } else {
      groups.push({ a: s.a, b: s.b, joints: new Set([s.j]) })
    }
  }
  groups.sort((x, y) => x.a - y.a)
  // 3. what happened in each: per joint, why, which camera, how fast it was moving
  const ranks = new Map<number, number[]>()
  const time = (f: number) => r.times[f] ?? f / r.fps
  return groups.map((g): Flag => {
    let lostAny = false
    let spikeAny = false
    let weight = 0
    const joints = [...g.joints].map((j): FlagJoint => {
      let lost = 0
      let spike = 0
      let peak: number | null = null
      let fastest: number | null = null
      for (let f = g.a; f <= g.b; f++) {
        const px = r.joint_error_px[f]?.[j]
        if ((r.joint_views[f]?.[j] ?? 0) === 0) lost++
        else if (typeof px === 'number' && px >= rules.spikePx) spike++
        if (typeof px === 'number' && (peak === null || px > peak)) peak = px
        const v = r.joint_speed?.[f]?.[j]
        if (typeof v === 'number' && isFinite(v) && (fastest === null || v > fastest)) fastest = v
      }
      lostAny ||= lost > 0
      spikeAny ||= spike > 0
      weight += lost + spike
      // blame: the camera that missed it most, if that explains most of the loss; else the one furthest off
      // (a joint every camera saw can still have no 3D point: the cameras disagreed too much to place it)
      let missedMost: FlagJoint['camera'] = null
      let furthest: FlagJoint['camera'] = null
      r.per_camera.forEach((pc) => {
        let missed = 0
        let sum = 0
        let count = 0
        for (let f = g.a; f <= g.b; f++) {
          const p = pc.points[f]?.[j]
          const q = pc.reprojected[f]?.[j]
          if (!p || p[0] === null || p[1] === null) {
            missed++
            continue
          }
          if (q && q[0] !== null && q[1] !== null) {
            sum += Math.hypot(p[0] - q[0], p[1] - q[1])
            count++
          }
        }
        const px = count ? sum / count : null
        if (!missedMost || missed > missedMost.missed) missedMost = { id: pc.id, missed, px, why: 'missed' }
        if (px !== null && (!furthest || furthest.px === null || px > furthest.px)) furthest = { id: pc.id, missed, px, why: 'off' }
      })
      const camera: FlagJoint['camera'] =
        lost > 0 && missedMost && (missedMost as NonNullable<FlagJoint['camera']>).missed >= lost / 2 ? missedMost : furthest ?? missedMost
      let speed: FlagJoint['speed'] = null
      if (fastest !== null) {
        if (!ranks.has(j)) ranks.set(j, speedRank(r, j))
        const sorted = ranks.get(j)!
        const atLeast = sorted.length ? sorted.filter((v) => v >= fastest!).length / sorted.length : 1
        speed = { mps: fastest, fasterShare: atLeast }
      }
      return { joint: r.joints[j], lostFrames: lost, spikeFrames: spike, peakPx: peak, camera, speed }
    })
    joints.sort((x, y) => y.lostFrames + y.spikeFrames - (x.lostFrames + x.spikeFrames))
    const frames = g.b - g.a + 1
    const sawNoOne = r.per_camera
      .filter((pc) => {
        let none = 0
        for (let f = g.a; f <= g.b; f++) if (pc.seen[f] === 0) none++
        return none >= frames / 2
      })
      .map((pc) => pc.id)
    return {
      start: time(g.a),
      end: time(g.b) + 1 / r.fps,
      startFrame: g.a,
      endFrame: g.b,
      kind: lostAny && spikeAny ? 'both' : lostAny ? 'lost' : 'spike',
      joints,
      sawNoOne,
      weight,
    }
  })
}

/** The flag's heading: when, how long, which joints. */
export function flagTitle(flag: Flag, r: Report): string {
  const names = flag.joints.map((j) => prettyJoint(j.joint))
  const many = flag.joints.length > Math.max(6, r.joints.length * 0.6)
  const what = flag.kind === 'lost' ? 'lost' : flag.kind === 'spike' ? `cameras ${LIMITS.px.bad} px or more apart` : 'lost, and cameras far apart'
  return `${flag.start.toFixed(1)}–${flag.end.toFixed(1)} s (${(flag.end - flag.start).toFixed(1)} s): `
    + (many ? `most of the body (${flag.joints.length} joints)` : names.join(', '))
    + `, ${what}`
}

/** What happened to each joint in the flag, a clause each, and why it might have. */
export function flagDetails(flag: Flag): string[] {
  const out: string[] = []
  if (flag.sawNoOne.length) out.push(`${flag.sawNoOne.join(' and ')} saw no one for most of it.`)
  const frames = flag.endFrame - flag.startFrame + 1
  for (const j of flag.joints.slice(0, 4)) {
    const parts: string[] = []
    if (j.lostFrames) parts.push(`no 3D position in ${j.lostFrames} of ${frames} frames`)
    if (j.spikeFrames) parts.push(`cameras up to ${j.peakPx?.toFixed(0)} px apart in ${j.spikeFrames}`)
    if (j.camera) {
      parts.push(
        j.camera.why === 'missed'
          ? `${j.camera.id} did not see it in ${j.camera.missed}`
          : `${j.lostFrames && !j.spikeFrames ? 'the cameras saw it but disagreed too much to place it, ' : ''}${j.camera.id} furthest off`
            + (j.camera.px === null ? '' : ` (${j.camera.px.toFixed(0)} px${j.camera.px > MAX_KEPT_PX ? ', so triangulation mostly left its view out' : ''})`),
      )
    }
    let s = `${prettyJoint(j.joint)}: ${parts.join(', ')}`
    if (j.speed) {
      const share = j.speed.fasterShare
      const rare = share < 0.01 ? 'its fastest in the take' : `faster than in ${(100 - share * 100).toFixed(0)} % of the take`
      s += share <= FLAG_RULES.fastShare
        ? `; it was moving fast (${j.speed.mps.toFixed(1)} m/s, ${rare}), so motion blur is a likely cause`
        : j.camera?.why === 'missed'
          ? `; it was not moving unusually fast (${j.speed.mps.toFixed(1)} m/s), so it was more likely hidden from that camera`
          : `; it was not moving unusually fast (${j.speed.mps.toFixed(1)} m/s)`
    }
    out.push(s + '.')
  }
  if (flag.joints.length > 4) out.push(`And ${flag.joints.length - 4} more: ${flag.joints.slice(4).map((j) => prettyJoint(j.joint)).join(', ')}.`)
  return out
}

// ---- timelines -------------------------------------------------------------------------------

/** Per frame, how many tracked joints had no 3D point. */
export function lostPerFrame(r: Report): number[] {
  return r.joint_views.map((row) => row.filter((v) => v === 0).length)
}

// ---- the cameras' 2D view -------------------------------------------------------------------

/** Lines between tracked joints for the 2D wire drawing, by MediaPipe name. */
export const WIRES: [string, string][] = [
  ['NOSE', 'LEFT_EYE'], ['NOSE', 'RIGHT_EYE'], ['LEFT_EYE', 'LEFT_EAR'], ['RIGHT_EYE', 'RIGHT_EAR'],
  ['LEFT_SHOULDER', 'RIGHT_SHOULDER'], ['LEFT_HIP', 'RIGHT_HIP'],
  ['LEFT_SHOULDER', 'LEFT_HIP'], ['RIGHT_SHOULDER', 'RIGHT_HIP'],
  ['LEFT_SHOULDER', 'LEFT_ELBOW'], ['LEFT_ELBOW', 'LEFT_WRIST'],
  ['RIGHT_SHOULDER', 'RIGHT_ELBOW'], ['RIGHT_ELBOW', 'RIGHT_WRIST'],
  ['LEFT_WRIST', 'LEFT_INDEX'], ['RIGHT_WRIST', 'RIGHT_INDEX'],
  ['LEFT_HIP', 'LEFT_KNEE'], ['LEFT_KNEE', 'LEFT_ANKLE'], ['LEFT_ANKLE', 'LEFT_HEEL'], ['LEFT_HEEL', 'LEFT_FOOT_INDEX'], ['LEFT_ANKLE', 'LEFT_FOOT_INDEX'],
  ['RIGHT_HIP', 'RIGHT_KNEE'], ['RIGHT_KNEE', 'RIGHT_ANKLE'], ['RIGHT_ANKLE', 'RIGHT_HEEL'], ['RIGHT_HEEL', 'RIGHT_FOOT_INDEX'], ['RIGHT_ANKLE', 'RIGHT_FOOT_INDEX'],
]

/** The part of a camera's picture the performer covers over the whole take, with a margin; null if never seen. */
export function performerBox(r: Report, c: number, margin = 0.15): { x: number; y: number; w: number; h: number } | null {
  let x0 = Infinity
  let y0 = Infinity
  let x1 = -Infinity
  let y1 = -Infinity
  for (const frame of [r.per_camera[c].points, r.per_camera[c].reprojected]) {
    for (const row of frame) {
      for (const p of row) {
        if (!p || p[0] === null || p[1] === null) continue
        x0 = Math.min(x0, p[0])
        y0 = Math.min(y0, p[1])
        x1 = Math.max(x1, p[0])
        y1 = Math.max(y1, p[1])
      }
    }
  }
  if (!isFinite(x0)) return null
  const cam = r.cameras[c]
  const mx = (x1 - x0) * margin + 20
  const my = (y1 - y0) * margin + 20
  // never narrower than 3:4, so a standing performer does not make a sliver of a view
  const cx = (x0 + x1) / 2
  const half = Math.max((x1 - x0) / 2 + mx, ((y1 - y0) / 2 + my) * 0.75)
  const x = Math.max(0, cx - half)
  const y = Math.max(0, y0 - my)
  return { x, y, w: Math.min(cam.width, cx + half) - x, h: Math.min(cam.height, y1 + my) - y }
}

/** The wire pairs as joint indices in this report, leaving out joints it does not track. */
export function wireIndices(r: Report): [number, number][] {
  return WIRES.map(([a, b]) => [r.joints.indexOf(a), r.joints.indexOf(b)] as [number, number]).filter(([a, b]) => a >= 0 && b >= 0)
}

// ---- the glossary ----------------------------------------------------------------------------

export const GLOSSARY: { term: string; text: string }[] = [
  {
    term: 'Pixels (px) and millimetres',
    text: 'Errors are measured on the camera picture, in pixels. The app also gives the size at the performer: one pixel covers more of the body the further the camera stands, so the millimetres are pixels × distance ÷ focal length, per camera.',
  },
  {
    term: 'Reprojection error',
    text: 'Take a 3D point, project it back into a camera’s picture, and measure how far it lands from where that camera’s detector put the joint. Zero means the camera and the 3D skeleton agree exactly. The cameras’ view below draws both: the solid wire is what the detector saw, the dashed wire is the 3D skeleton seen from that camera, and the gap between them is the reprojection error.',
  },
  {
    term: 'Calibration error',
    text: 'The reprojection error left after working out where each camera stands and where it points (stage 2b), one number per camera for the whole take. High means the camera positions themselves are off, which shifts every joint; it does not change over time.',
  },
  {
    term: 'Triangulation error',
    text: 'The reprojection error of the final 3D joints (stage 2c), averaged over joints, cameras and frames. It changes frame by frame (the timeline shows it per camera): high where a camera mis-detected a joint, or where the performer moved fast.',
  },
  {
    term: 'Joints missing / no 3D position',
    text: 'A joint gets a 3D position only when at least 2 cameras saw it with confidence ≥ 0.5 and they agree within 15 px. Otherwise that frame has no point and the smoother fills short gaps from the frames around it; the skeleton shows those in purple.',
  },
  {
    term: 'Bone length spread',
    text: 'How much each bone’s length changes over the take. Real bones do not stretch, so a spread of more than a couple of centimetres means the joints at its ends were placed inconsistently.',
  },
  {
    term: 'Jitter',
    text: 'How much the joints shake from frame to frame (their acceleration), before and after smoothing. Smoothing should cut it.',
  },
]
