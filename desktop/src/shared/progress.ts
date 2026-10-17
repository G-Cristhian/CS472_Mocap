/**
 * Turns the pipeline's printed lines into a progress bar. Pure, so the main
 * process, the browser mock and the tests all use the same one.
 *
 * The lines come from backend/mocap_pipeline/run_pipeline.py (and detect.py's
 * "progress:" lines, printed when MOCAP_PROGRESS is set). Detection is most of
 * the wall time, so it gets most of the bar, split evenly across the videos.
 */
import type { Progress, RunResult, Stage } from './types'

const WEIGHTS = { detect: 0.75, sync: 0.05, calibrate: 0.08, triangulate: 0.05, write: 0.07 }

function baseName(path: string): string {
  return path.replace(/\\/g, '/').split('/').pop() ?? path
}

export class ProgressTracker {
  private readonly cameras: string[]
  private readonly detectDone = new Map<string, number>() // basename -> 0..1
  private stage: Stage = 'starting'
  private detail = 'Starting'
  private after = 0 // fraction of the non-detect stages completed, in WEIGHTS units
  private current = ''
  readonly paths: { bvh?: string; json?: string; metrics?: string } = {}
  private lastError = ''

  constructor(videoPaths: string[]) {
    this.cameras = videoPaths.map(baseName)
    for (const c of this.cameras) this.detectDone.set(c, 0)
  }

  /** Feed one stdout or stderr line. Returns the new progress when it changed, else null. */
  feed(line: string, fromStderr = false): Progress | null {
    const before = this.snapshot()
    this.apply(line.trimEnd(), fromStderr)
    const now = this.snapshot()
    return now.stage !== before.stage || now.fraction !== before.fraction || now.detail !== before.detail ? now : null
  }

  snapshot(): Progress {
    const detect = this.cameras.length
      ? [...this.detectDone.values()].reduce((s, f) => s + f, 0) / this.cameras.length
      : 1
    const fraction = Math.min(1, WEIGHTS.detect * detect + this.after)
    return { stage: this.stage, fraction, detail: this.detail }
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

  private apply(line: string, fromStderr: boolean): void {
    let m: RegExpMatchArray | null

    if ((m = line.match(/^progress: detect (.+) (\d+)\/(\d+)$/))) {
      const cam = this.cameraOf(m[1])
      const done = Number(m[2])
      const total = Number(m[3])
      if (cam) {
        this.detectDone.set(cam, total > 0 ? Math.min(0.99, done / total) : 0.5)
        this.stage = 'detecting'
        this.detail = `Detecting joints in ${cam}, frame ${done}${total ? ` of ${total}` : ''}`
      }
      return
    }
    if ((m = line.match(/^Detecting joints in (.+?)( \(\w+\))?$/))) {
      const cam = this.cameraOf(m[1])
      if (this.current) this.detectDone.set(this.current, 1)
      this.current = cam ?? ''
      this.stage = 'detecting'
      this.detail = `Detecting joints in ${cam ?? baseName(m[1])}`
      return
    }
    if ((m = line.match(/^Using saved joints for (.+?) \(/))) {
      const cam = this.cameraOf(m[1])
      if (cam) this.detectDone.set(cam, 1)
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

  private finishDetect(): void {
    for (const c of this.cameras) this.detectDone.set(c, 1)
    this.current = ''
  }
}
