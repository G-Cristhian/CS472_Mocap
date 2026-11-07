/**
 * The comparison matrix: one take, several settings, one run each. Pure, so it
 * is tested on its own (test/queue.test.cjs).
 *
 * Every detector setting gets its own output folder, because a run overwrites
 * the metrics and stage files of an earlier run in the same folder. The
 * smoothers of one detector setting share that folder: the first runs in full,
 * the others with --resume, which reuses the joints, clap times, calibration
 * and 3D points and only redoes smoothing and the skeleton (seconds, not
 * minutes). Their metrics survive because the app keeps a copy of every run's
 * results (library.ts, snapshotRun).
 */
import type { Detector, RtmposeMode, RunOptions, Smoother } from './types'

export interface Matrix {
  detectors: Detector[]
  smoothers: Smoother[]
  /** RTMPose only */
  rtmposeModes: RtmposeMode[]
  /** RTMPose only: person detector every N frames */
  rtmposeDetectEvery: number[]
}

/** "1, 5" -> [1, 5]; whole numbers from 1 to 100, repeats dropped. A string is the error to show. */
export function parseDetectEvery(text: string): number[] | string {
  const parts = text.split(/[\s,]+/).filter(Boolean)
  if (!parts.length) return 'Give at least one detect-every value, such as 1 or 1, 5.'
  const values: number[] = []
  for (const p of parts) {
    const n = Number(p)
    if (!Number.isInteger(n) || n < 1 || n > 100) return `Detect every must be whole numbers from 1 to 100; "${p}" is not.`
    if (!values.includes(n)) values.push(n)
  }
  return values
}

/** What makes two runs' detections different: "mediapipe", "rtmpose-balanced-every5". */
export function detectionName(o: Pick<RunOptions, 'detector' | 'rtmposeMode' | 'rtmposeDetectEvery'>): string {
  if (o.detector !== 'rtmpose') return o.detector
  return `rtmpose-${o.rtmposeMode ?? 'balanced'}-every${o.rtmposeDetectEvery ?? 1}`
}

/** A short human label: "RTMPose balanced, detector every 5, Savitzky-Golay". */
export function settingsLabel(o: Pick<RunOptions, 'detector' | 'rtmposeMode' | 'rtmposeDetectEvery' | 'smoother'>): string {
  const smoother = o.smoother === 'savgol' ? 'Savitzky-Golay' : 'Butterworth'
  if (o.detector !== 'rtmpose') return `MediaPipe, ${smoother}`
  const every = o.rtmposeDetectEvery ?? 1
  return `RTMPose ${o.rtmposeMode ?? 'balanced'}, detector ${every === 1 ? 'every frame' : `every ${every}`}, ${smoother}`
}

/**
 * Every combination of the matrix for one take, from the form's settings (`base`), grouped by
 * detector setting so each group's first run detects and the rest resume. `baseOutDir` gets a
 * suffix per detector setting; when one of those folders is already used by a queued run
 * (`taken`), the whole set moves to `baseOutDir-2`, `-3`… so two batches never share a folder.
 * A string is the error to show.
 */
export function expandMatrix(
  base: RunOptions,
  matrix: Matrix,
  baseOutDir: string,
  taken: ReadonlySet<string> = new Set(),
): RunOptions[] | string {
  if (!matrix.detectors.length) return 'Tick at least one detector.'
  if (!matrix.smoothers.length) return 'Tick at least one smoother.'
  if (matrix.detectors.includes('rtmpose')) {
    if (!matrix.rtmposeModes.length) return 'Tick at least one RTMPose mode.'
    if (!matrix.rtmposeDetectEvery.length) return 'Give at least one RTMPose detect-every value.'
  }
  const detections: Pick<RunOptions, 'detector' | 'rtmposeMode' | 'rtmposeDetectEvery'>[] = []
  for (const detector of matrix.detectors) {
    if (detector !== 'rtmpose') {
      detections.push({ detector })
      continue
    }
    for (const rtmposeMode of matrix.rtmposeModes)
      for (const rtmposeDetectEvery of matrix.rtmposeDetectEvery) detections.push({ detector, rtmposeMode, rtmposeDetectEvery })
  }
  let prefix = baseOutDir
  for (let n = 2; detections.some((d) => taken.has(`${prefix}-${detectionName(d)}`)); n++) prefix = `${baseOutDir}-${n}`
  const runs: RunOptions[] = []
  for (const d of detections) {
    const outDir = `${prefix}-${detectionName(d)}`
    matrix.smoothers.forEach((smoother, i) => {
      const { rtmposeMode: _m, rtmposeDetectEvery: _e, ...rest } = base
      runs.push({
        ...rest,
        ...d,
        smoother,
        outDir,
        // the first smoother detects (as the form says); the others reuse its stage files
        ...(i === 0 ? {} : { resume: true, recalibrate: false }),
      })
    })
  }
  return runs
}
