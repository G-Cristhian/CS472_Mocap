/**
 * A stand-in for the Electron bridge so the page can be worked on in a plain
 * browser (`npm run preview`). It replays the lines a real run prints through
 * the same ProgressTracker, and serves the frontend's sample BVH as the result.
 */
import { ProgressTracker } from '../shared/progress'
import type { Backend, Progress, VideoFile } from '../shared/types'

const VIDEOS: VideoFile[] = [
  { path: '/mock/take01/take01_cam0_iphone16pro.MOV', name: 'take01_cam0_iphone16pro.MOV', sizeMb: 412.3 },
  { path: '/mock/take01/take01_cam1_iphone15.MOV', name: 'take01_cam1_iphone15.MOV', sizeMb: 398.0 },
  { path: '/mock/take01/take01_cam2_fold.mp4', name: 'take01_cam2_fold.mp4', sizeMb: 350.6 },
]

function script(videos: string[], outDir: string): string[] {
  const lines = [`Cameras: ${videos.map((_, i) => `cam${i} webcam`).join(', ')}`]
  for (const v of videos) lines.push(`Detecting joints in ${v} (mediapipe)`)
  if (videos.length > 1) lines.push(`Detecting ${videos.length} videos at once, ${videos.length} processes`)
  for (let f = 30; f <= 300; f += 30) for (const v of videos) lines.push(`progress: detect ${v} ${f}/300`)
  for (const v of videos) lines.push(`Detected joints in ${v} (${(40 + videos.indexOf(v) * 3).toFixed(0)} s)`)
  lines.push(
    `Clap at ${videos.map((_, i) => `cam${i} ${(1 + i * 0.3).toFixed(3)} s`).join(', ')}`,
    'Calibration started from cam0 and cam1',
    'Calibration from the performer: cam0 1.44 px, cam1 1.33 px, cam2 1.42 px',
    'Scale: 6.8342 m per unit, floor found, Y up',
    `Saved calibration to ${outDir}/calibration.json`,
    `Saved 360 frames of 3D joints to ${outDir}/out3d.json`,
    `Saved skeleton animation to ${outDir}/out3d.bvh`,
    `Saved metrics to ${outDir}/out3d.metrics.json`,
  )
  return lines
}

const logListeners = new Set<(line: string) => void>()
const progressListeners = new Set<(p: Progress) => void>()
let cancelled = false

export const mock: Backend = {
  async chooseDirectory() {
    return '/mock/take01'
  },
  async listVideos() {
    return VIDEOS
  },
  async defaultOutDir(videoDir) {
    return `/mock/output/${videoDir.split('/').pop()}-20261016-1830`
  },
  async run(options) {
    cancelled = false
    const tracker = new ProgressTracker(options.videos)
    for (const line of script(options.videos, options.outDir)) {
      if (cancelled) return { ok: false, exitCode: null, error: 'Cancelled' }
      await new Promise((r) => setTimeout(r, line.startsWith('progress') ? 60 : 250))
      logListeners.forEach((cb) => cb(line))
      const p = tracker.feed(line)
      if (p) progressListeners.forEach((cb) => cb(p))
    }
    return tracker.result(0)
  },
  async cancel() {
    cancelled = true
  },
  onLog(cb) {
    logListeners.add(cb)
    return () => logListeners.delete(cb)
  },
  onProgress(cb) {
    progressListeners.add(cb)
    return () => progressListeners.delete(cb)
  },
  async readText(file) {
    if (file.endsWith('.bvh')) return (await fetch('./sample_take.bvh')).text()
    if (file.endsWith('metrics.json')) {
      return JSON.stringify({
        calibrate: { reprojection_error_px: { cam0: 1.44, cam1: 1.33, cam2: 1.42 } },
        rig: { bone_lengths: { mean_std_m: 0.004 } },
        pose_final: { missing_fraction: 0.003 },
        scale: { upright_frames: 60 },
        timing: { total_s: 184.2 },
      })
    }
    throw new Error(`mock has no ${file}`)
  },
  async openFolder() {
    alert('In Electron this opens the output folder.')
  },
}
