/**
 * Turns the pipeline's printed lines into a progress bar. Pure, so the main
 * process, the browser mock and the tests all use the same one.
 *
 * The lines come from backend/mocap_pipeline/run_pipeline.py (and detect.py's
 * "progress:" lines, printed when MOCAP_PROGRESS is set). Detection is most of
 * the wall time, so it gets most of the bar, split evenly across the videos.
 * Each video also gets its own state, so a file that fails is named while the
 * others carry on.
 */
import type { Progress, RunResult, Stage, VideoProgress, VideoState } from './types'

const WEIGHTS = { detect: 0.75, sync: 0.05, calibrate: 0.08, triangulate: 0.05, write: 0.07 }

function baseName(path: string): string {
  return path.replace(/\\/g, '/').split('/').pop() ?? path
}

interface VideoTrack {
  fraction: number // 0..1
  state: VideoState
  detail: string
}

export class ProgressTracker {
  private readonly cameras: string[]
  private readonly videos = new Map<string, VideoTrack>() // basename -> state
  private stage: Stage = 'starting'
  private detail = 'Starting'
  private after = 0 // fraction of the non-detect stages completed, in WEIGHTS units
  readonly paths: { bvh?: string; json?: string; metrics?: string } = {}
  private lastError = ''

  constructor(videoPaths: string[]) {
    this.cameras = videoPaths.map(baseName)
    for (const c of this.cameras) this.videos.set(c, { fraction: 0, state: 'waiting', detail: '' })
  }

  /** Feed one stdout or stderr line. Returns the new progress when it changed, else null. */
  feed(line: string, fromStderr = false): Progress | null {
    const before = JSON.stringify(this.snapshot())
    this.apply(line.trimEnd(), fromStderr)
    const now = this.snapshot()
    return JSON.stringify(now) !== before ? now : null
  }

  snapshot(): Progress {
    const detect = this.cameras.length
      ? [...this.videos.values()].reduce((s, v) => s + v.fraction, 0) / this.cameras.length
      : 1
    const fraction = Math.min(1, WEIGHTS.detect * detect + this.after)
    const videos: VideoProgress[] = this.cameras.map((name) => {
      const v = this.videos.get(name)!
      return { name, state: v.state, detail: v.detail }
    })
    return { stage: this.stage, fraction, detail: this.detail, videos }
  }

  /** The result for a finished process. */
  result(exitCode: number | null, cancelled = false): RunResult {
    if (cancelled) return { ok: false, exitCode, error: 'Cancelled' }
    const ok = exitCode === 0 && this.stage !== 'failed'
    return {
      ok,
      exitCode,
      bvhPath: this.paths.bvh,
      jsonPath: this.paths.json,
      metricsPath: this.paths.metrics,
      error: ok ? undefined : this.lastError || `The pipeline exited with code ${exitCode}`,
    }
  }

  private cameraOf(path: string): string | undefined {
    const name = baseName(path)
    return this.cameras.find((c) => c === name)
  }

  private setVideo(cam: string | undefined, patch: Partial<VideoTrack>): void {
    if (!cam) return
    const v = this.videos.get(cam)
    if (v) Object.assign(v, patch)
  }

  private apply(line: string, fromStderr: boolean): void {
    let m: RegExpMatchArray | null

    if ((m = line.match(/^progress: detect (.+) (\d+)\/(\d+)$/))) {
      const cam = this.cameraOf(m[1])
      const done = Number(m[2])
      const total = Number(m[3])
      if (cam) {
        const v = this.videos.get(cam)!
        // a video that already finished (or failed) keeps its state; progress lines can lag behind
        if (v.state === 'waiting' || v.state === 'detecting') {
          this.setVideo(cam, {
            fraction: total > 0 ? Math.min(0.99, done / total) : 0.5,
            state: 'detecting',
            detail: `frame ${done}${total ? ` of ${total}` : ''}`,
          })
        }
        this.stage = 'detecting'
        this.detail = `Detecting joints in ${cam}, frame ${done}${total ? ` of ${total}` : ''}`
      }
      return
    }
    if ((m = line.match(/^Detecting joints in (.+?)( \(\w+\))?$/))) {
      // several videos are detected at once, so one starting says nothing about the others
      const cam = this.cameraOf(m[1])
      this.setVideo(cam, { state: 'detecting', detail: 'starting' })
      this.stage = 'detecting'
      this.detail = `Detecting joints in ${cam ?? baseName(m[1])}`
      return
    }
    if ((m = line.match(/^Detected joints in (.+?)( \((.*)\))?$/))) {
      const cam = this.cameraOf(m[1])
      this.setVideo(cam, { fraction: 1, state: 'done', detail: m[3] ?? '' })
      this.stage = 'detecting'
      this.detail = `Detected joints in ${cam ?? baseName(m[1])}`
      return
    }
    if ((m = line.match(/^Detection failed for (.+?): (.+)$/)) && !/^\d+ of \d+ video/.test(m[1])) {
      // the per-file line from stage 1; the "N of M video(s)" summary is handled as an error below
      const cam = this.cameraOf(m[1])
      if (cam) {
        this.setVideo(cam, { fraction: 1, state: 'failed', detail: m[2] })
        this.stage = 'detecting'
        this.detail = `Detection failed for ${cam}`
        if (fromStderr) this.lastError = line
        return
      }
    }
    if ((m = line.match(/^Using saved joints for (.+?) \(/))) {
      const cam = this.cameraOf(m[1])
      this.setVideo(cam, { fraction: 1, state: 'reused', detail: 'saved joints reused' })
      this.stage = 'detecting'
      this.detail = `Reusing saved joints for ${cam ?? baseName(m[1])}`
      return
    }
    if (line.startsWith('Clap at') || line.startsWith('Using saved clap times')) {
      this.finishDetect()
      this.after = WEIGHTS.sync
      this.stage = 'calibrating'
      this.detail = line.startsWith('Clap at') ? `Synchronised: ${line.slice(8)}` : 'Synchronised from the saved clap times'
      return
    }
    if (line.startsWith('Calibration started from') || line.startsWith('Calibration from the performer')) {
      this.finishDetect()
      this.after = Math.max(this.after, WEIGHTS.sync)
      this.stage = 'calibrating'
      this.detail = line
      return
    }
    if (line.startsWith('Scale:')) {
      this.stage = 'calibrating'
      this.detail = line
      return
    }
    if (line.startsWith('Saved calibration to') || line.startsWith('Using existing calibration')) {
      this.finishDetect()
      this.after = WEIGHTS.sync + WEIGHTS.calibrate
      this.stage = 'triangulating'
      this.detail = 'Triangulating the 3D joints'
      return
    }
    if (line.startsWith('Using saved 3D joints')) {
      this.after = WEIGHTS.sync + WEIGHTS.calibrate + WEIGHTS.triangulate
      this.stage = 'writing'
      this.detail = 'Reusing the saved 3D joints'
      return
    }
    if ((m = line.match(/^Saved \d+ frames of 3D joints to (.+)$/))) {
      this.paths.json = m[1]
      this.after = WEIGHTS.sync + WEIGHTS.calibrate + WEIGHTS.triangulate + WEIGHTS.write * 0.5
      this.stage = 'writing'
      this.detail = 'Writing the skeleton animation'
      return
    }
    if ((m = line.match(/^Saved skeleton animation to (.+)$/))) {
      this.paths.bvh = m[1]
      this.after = WEIGHTS.sync + WEIGHTS.calibrate + WEIGHTS.triangulate + WEIGHTS.write
      this.finishDetect()
      this.stage = 'done'
      this.detail = `Saved ${baseName(m[1])}`
      return
    }
    if ((m = line.match(/^Saved metrics to (.+)$/))) {
      this.paths.metrics = m[1]
      return
    }
    if (line.startsWith('Stopped after')) {
      this.stage = 'done'
      this.detail = line
      return
    }
    if (line.startsWith('FAILED') || line.startsWith('Traceback') || /Error:/.test(line) || fromStderr) {
      // the last non-empty stderr line is usually the human message (SystemExit text)
      if (line.trim() && !line.startsWith('Traceback') && !/^\s+File "/.test(line) && !/^\s+\^/.test(line)) {
        this.lastError = line.replace(/^FAILED:\s*/, '')
      }
      if (line.startsWith('FAILED')) {
        this.stage = 'failed'
        this.detail = this.lastError
      }
    }
  }

  /** Once a later stage prints, every video that has not failed is done. */
  private finishDetect(): void {
    for (const v of this.videos.values()) {
      if (v.state !== 'failed') {
        v.fraction = 1
        if (v.state !== 'reused') v.state = 'done'
      }
    }
  }
}
