/**
 * A stand-in for the Electron bridge so the page can be worked on in a plain
 * browser (`npm run preview`). It replays the lines a real run prints through
 * the same ProgressTracker, and serves the frontend's sample BVH as the result.
 */
import { parseCheckOutput } from '../shared/check'
import { ProgressTracker } from '../shared/progress'
import type { Backend, Progress, RunOptions, VideoFile } from '../shared/types'

const VIDEOS: VideoFile[] = [
  { path: '/mock/take01/take01_cam0_iphone16pro.MOV', name: 'take01_cam0_iphone16pro.MOV', sizeMb: 412.3 },
  { path: '/mock/take01/take01_cam1_iphone15.MOV', name: 'take01_cam1_iphone15.MOV', sizeMb: 398.0 },
  { path: '/mock/take01/take01_cam2_fold.mp4', name: 'take01_cam2_fold.mp4', sizeMb: 350.6 },
]

function script(options: RunOptions): string[] {
  const { videos, outDir, detector, resume } = options
  const lines = [`Cameras: ${videos.map((_, i) => `cam${i} webcam`).join(', ')}`]
  if (resume) {
    for (const v of videos) lines.push(`Using saved joints for ${v} (out3d.keypoints.${v.split('/').pop()}.npz)`)
    lines.push('Using saved clap times from out3d.sync.json')
    lines.push(`Using existing calibration ${outDir}/calibration.json`)
    lines.push(`Using saved 3D joints from ${outDir}/out3d.pose_raw.json`)
  } else {
    for (const v of videos) lines.push(`Detecting joints in ${v} (${detector})`)
    if (videos.length > 1) lines.push(`Detecting ${videos.length} videos at once, ${videos.length} processes`)
    for (let f = 30; f <= 300; f += 30) for (const v of videos) lines.push(`progress: detect ${v} ${f}/300`)
    for (const v of videos) lines.push(`Detected joints in ${v} (${(40 + videos.indexOf(v) * 3).toFixed(0)} s)`)
    lines.push(
      options.clapTimes
        ? `Clap at ${videos.map((_, i) => `cam${i} ${options.clapTimes![i].toFixed(3)} s`).join(', ')}`
        : `Clap at ${videos.map((_, i) => `cam${i} ${(1 + i * 0.3).toFixed(3)} s`).join(', ')}`,
      'Calibration started from cam0 and cam1',
      'Calibration from the performer: cam0 1.44 px, cam1 1.33 px, cam2 1.42 px',
      `Scale: 6.8342 m per unit, height measured to the ${detector === 'rtmpose' ? 'head top' : 'ears'}, floor found, Y up`,
      `Saved calibration to ${outDir}/calibration.json`,
    )
  }
  lines.push(
    `Saved 360 frames of 3D joints to ${outDir}/out3d.json`,
    `Saved skeleton animation to ${outDir}/out3d.bvh`,
    `Saved metrics to ${outDir}/out3d.metrics.json`,
  )
  return lines
}

/** What check_videos prints for the mock take: one faint clap at the given threshold. */
function checkOutput(videos: string[], threshold: number): string {
  const blocks = videos.map((v, i) => {
    const name = v.split('/').pop()!
    const faint = i === 2 && threshold >= 1
    return [
      name,
      `  video   1920x1080, ${i === 2 ? '30.00' : '59.94'} fps, ${i === 2 ? 900 : 1800} frames, 30.0 s`,
      i === 2 ? '  WARNING frame rate under 50; the protocol asks for 60 (or 120 for set C)' : '',
      name.endsWith('.MOV')
        ? `  lens    iPhone ${i ? '15' : '16 Pro'}, Back Camera, 24 mm (35 mm equiv.) from metadata`
        : '  lens    no lens metadata (not an iPhone file): needs --fov, default 65',
      faint
        ? `  FAIL    no clap: ${name}: no clear clap in the first 10 s. The sharpest sound is at 1.62 s: 2.9x the background (need 4.0), 2.4x louder than just before it (need 2.0), reaching its peak in 12 ms (at most 25). If that is the clap, rerun with --clap-threshold 0.5; otherwise give the clap times with --sync.`
        : `  clap    ${(1 + i * 0.3).toFixed(3)} s`,
    ]
      .filter(Boolean)
      .join('\n')
  })
  const ok = !(videos.length > 2 && threshold >= 1)
  const across =
    videos.length > 1
      ? ['across cameras', videos.length > 2 ? '  WARNING frame rates differ between phones: [30, 60] (fine for the pipeline, but a take set should be recorded at one rate)' : '']
          .concat(ok ? [`  claps   ${videos.map((v, i) => `${v.split('/').pop()} ${(1 + i * 0.3).toFixed(3)} s`).join(', ')} (cross-checked against camera 0)`] : [])
          .filter(Boolean)
          .join('\n')
      : ''
  return [...blocks, across, ok ? 'All files usable.' : '1 file(s) the pipeline cannot use.'].filter(Boolean).join('\n\n')
}

const METRICS = {
  run: { detector: 'mediapipe', smoother: 'savgol' },
  stage1: {
    cam0: { frames: 1800, fps_nominal: 59.94, no_person_fraction: 0.012, mean_confidence: 0.91 },
    cam1: { frames: 1800, fps_nominal: 59.94, no_person_fraction: 0.03, mean_confidence: 0.88 },
    cam2: { frames: 900, fps_nominal: 30.0, no_person_fraction: 0.24, mean_confidence: 0.79 },
  },
  sync: { clap_time_s: { cam0: 1.0, cam1: 1.3, cam2: 1.6 }, clap_times_from: 'audio', clap_threshold: 1.0, common_frames: 360, common_fps: 30 },
  calibrate: { reprojection_error_px: { cam0: 1.44, cam1: 1.33, cam2: 1.42 } },
  scale: { upright_frames: 60, metres_per_unit: 6.8342, rescaled_from_height: true, height_from: 'ears' },
  triangulate: {
    cameras: 3, frames: 360, mean_reprojection_px: 2.1,
    mean_reprojection_px_per_joint: { NOSE: 1.2, LEFT_WRIST: 4.8, RIGHT_WRIST: 5.1, LEFT_ANKLE: 3.9, RIGHT_ANKLE: 2.2, LEFT_HIP: 1.1 },
    views_dropped: 14, joints_failed: 3, joints_with_fewer_than_2_views: 40,
  },
  pose_raw: { missing_fraction: 0.02, mean_views_per_joint: 2.7, jitter_mm: 15.5 },
  pose_final: {
    missing_fraction: 0.003, jitter_mm: 5.7,
    missing_fraction_per_joint: { LEFT_WRIST: 0.03, RIGHT_WRIST: 0.01, LEFT_ANKLE: 0.004, NOSE: 0 },
  },
  smooth: { method: 'savgol', settings: { window_frames: 7, polyorder: 2 }, gaps: { filled: 22, left_missing: 3 }, runs_too_short: 1 },
  rig: { bone_lengths: { mean_std_m: 0.004, per_bone: { LeftForeArm: { std_m: 0.009 }, RightForeArm: { std_m: 0.007 }, LeftLeg: { std_m: 0.002 } } } },
  timing: { total_s: 184.2, detect: { cam0_s: 40, cam1_s: 43, cam2_s: 46 } },
}

const logListeners = new Set<(line: string) => void>()
const progressListeners = new Set<(p: Progress) => void>()
let cancelled = false
let lastSmoother = 'savgol'
let lastDetector = 'mediapipe'

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
  async checkVideos(videos, clapThreshold) {
    const output = checkOutput(videos, clapThreshold)
    for (const line of output.split('\n')) logListeners.forEach((cb) => cb(line))
    await new Promise((r) => setTimeout(r, 600))
    return parseCheckOutput(output, output.endsWith('All files usable.') ? 0 : 1)
  },
  async run(options) {
    cancelled = false
    lastSmoother = options.smoother
    lastDetector = options.detector
    const tracker = new ProgressTracker(options.videos)
    for (const line of script(options)) {
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
      const butter = lastSmoother === 'butterworth'
      // RTMPose finds the top of the head itself, so the height is measured to it
      const rtmpose = lastDetector === 'rtmpose'
      return JSON.stringify({
        ...METRICS,
        run: { ...METRICS.run, smoother: lastSmoother, detector: lastDetector },
        scale: rtmpose ? { ...METRICS.scale, height_from: 'head top', head_top_above_ears_m: 0.131 } : METRICS.scale,
        triangulate: rtmpose
          ? { ...METRICS.triangulate, mean_reprojection_px_per_joint: { ...METRICS.triangulate.mean_reprojection_px_per_joint, HEAD_TOP: 3.4 } }
          : METRICS.triangulate,
        smooth: butter
          ? { ...METRICS.smooth, method: 'butterworth', settings: { cutoff_hz: 8, order: 2 } }
          : METRICS.smooth,
        pose_final: { ...METRICS.pose_final, jitter_mm: butter ? 6.3 : 5.7 },
        timing: { ...METRICS.timing, total_s: butter ? 9.4 : 184.2 },
      })
    }
    throw new Error(`mock has no ${file}`)
  },
  async openFolder() {
    alert('In Electron this opens the output folder.')
  },
}
