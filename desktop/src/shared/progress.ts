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

const MEMORY_ADVICE =
  'Most likely cause: the computer ran out of memory. Close other programs, or set Videos detected at once to 1, and run again.'

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
  private readonly videoPaths: string[]
  private atOnce = 1 // videos detected at the same time, from "Detecting N videos at once, M processes"
  private readonly videos = new Map<string, VideoTrack>() // basename -> state
  private stage: Stage = 'starting'
  private detail = 'Starting'
  private after = 0 // fraction of the non-detect stages completed, in WEIGHTS units
  readonly paths: { bvh?: string; json?: string; metrics?: string } = {}
  private message: string[] = [] // the pipeline's last message, one entry per line
  private inTraceback = false
  private inCleanupError = false // an "Exception ignored in ..." block printed while Python shuts down
  private lastFromStderr = false

  constructor(videoPaths: string[]) {
    this.videoPaths = videoPaths
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

  /** The result for a finished process. `signal` is set when the system stopped it (Node's 'close' event). */
  result(exitCode: number | null, cancelled = false, signal: string | null = null): RunResult {
    if (cancelled) return { ok: false, exitCode, error: 'Cancelled' }
    const ok = exitCode === 0 && this.stage !== 'failed'
    let error: string | undefined
    if (!ok) {
      const lines = [...this.message]
      if (exitCode === null && signal) {
        // keep what Python printed before it stopped: a native crash (SIGSEGV, SIGABRT) says why there
        lines.unshift(`The pipeline was stopped by signal ${signal}.`)
        if (signal === 'SIGKILL') lines.push(MEMORY_ADVICE)
      } else if (lines.some((l) => /BrokenProcessPool|terminated abruptly/.test(l))) {
        // a detection worker killed when memory runs out makes every video fail the same way, and the
        // pipeline then blames the setup (run_pipeline.py); the abrupt stop points at memory instead
        lines.push(MEMORY_ADVICE)
      }
      error = lines.join('\n') || `The pipeline exited with code ${exitCode}`
    }
    return {
      ok,
      exitCode,
      bvhPath: this.paths.bvh,
      jsonPath: this.paths.json,
      metricsPath: this.paths.metrics,
      error,
    }
  }

  /**
   * The camera a line is about: the video path (as the app passed it) or file name that `rest` starts
   * with, followed by `sep`. Matching the known names, rather than splitting the text, copes with paths
   * holding brackets or colons ("Takes (Oct)/cam0 (1).mp4", "take 1: warmup.mp4"). Longest name wins.
   */
  private cameraAt(rest: string, sep: string): { cam: string; after: string } | undefined {
    let best: { cam: string; after: string; length: number } | undefined
    this.videoPaths.forEach((full, i) => {
      for (const name of [full, this.cameras[i]]) {
        if (rest.startsWith(name + sep) && (!best || name.length > best.length)) {
          best = { cam: this.cameras[i], after: rest.slice(name.length + sep.length), length: name.length }
        }
      }
    })
    return best && { cam: best.cam, after: best.after }
  }

  /** Starts the next queued videos, up to the number detected at once. */
  private startQueued(): void {
    let running = [...this.videos.values()].filter((v) => v.state === 'detecting').length
    for (const c of this.cameras) {
      const v = this.videos.get(c)!
      if (running >= this.atOnce) break
      if (v.state === 'waiting' && v.detail === 'queued') {
        Object.assign(v, { state: 'detecting', detail: 'starting' })
        running++
      }
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

  /**
   * Collects the pipeline's message from stderr before any line is read as progress, so the first
   * line of a message that looks like progress ("Calibration from the performer failed ...") is
   * kept. Consecutive stderr lines stay together: a SystemExit text is usually the diagnosis, then
   * the advice. A traceback keeps only its exception line; warnings and indented lines are skipped.
   */
  private noteStderr(line: string): void {
    if (!line.trim()) return
    if (this.inCleanupError) {
      // skip its traceback and the exception line that ends it: it is not why the run failed
      if (line.startsWith('Traceback') || /^\s/.test(line)) return
      this.inCleanupError = false
      return
    }
    if (line.startsWith('Exception ignored')) {
      this.inCleanupError = true
      return
    }
    if (line.startsWith('Traceback')) {
      this.message = []
      this.inTraceback = true
      return
    }
    if (/^\s/.test(line)) return // a traceback's File, code and ^^^ lines, or a warning's source line
    // library chatter, not the run's message: Python warnings, logging lines, glog/absl lines
    // ("W0000 00:00:...", from MediaPipe and TensorFlow Lite) and progress bars
    if (/^\S.*:\d+: \w*Warning: /.test(line)) return
    if (/^(DEBUG|INFO|WARNING)[:\s]/.test(line) || /^[IWEF]\d{4} /.test(line) || /\d%\|/.test(line)) return
    if (this.inTraceback || !this.lastFromStderr) this.message = []
    this.inTraceback = false
    this.message.push(line.replace(/^FAILED:\s*/, ''))
  }

  private apply(line: string, fromStderr: boolean): void {
    if (fromStderr) this.noteStderr(line)
    else this.inTraceback = false
    this.lastFromStderr = fromStderr
    this.read(line, fromStderr)
  }

  private read(line: string, fromStderr: boolean): void {
    let m: RegExpMatchArray | null

    // a frame count OpenCV cannot read is printed as -1: the frame number still counts
    if ((m = line.match(/^progress: detect (.+) (\d+)\/(-?\d+)$/))) {
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
            detail: `frame ${done}${total > 0 ? ` of ${total}` : ''}`,
          })
        }
        this.stage = 'detecting'
        this.detail = `Detecting joints in ${cam}, frame ${done}${total > 0 ? ` of ${total}` : ''}`
      }
      return
    }
    // the path is everything before the last bracket, which holds the detector and its options
    // ("(mediapipe)", "(rtmpose, mode balanced)"); a path may itself hold " (" ("Takes (Oct)")
    if ((m = line.match(/^Detecting joints in (.+?)(?: \([^()]*\))?$/))) {
      // printed for every video before any starts; the ones beyond "at once" wait their turn
      const cam = this.cameraAt(line.slice('Detecting joints in '.length), ' (')?.cam ?? this.cameraOf(m[1])
      const v = cam ? this.videos.get(cam) : undefined
      if (v && v.state === 'waiting') {
        v.detail = 'queued'
        this.startQueued()
      }
      this.stage = 'detecting'
      this.detail = `Detecting joints in ${cam ?? baseName(m[1])}`
      return
    }
    if ((m = line.match(/^Detecting \d+ videos at once, (\d+) process/))) {
      this.atOnce = Number(m[1])
      this.startQueued()
      return
    }
    if (line.startsWith('Detected joints in ')) {
      const hit = this.cameraAt(line.slice('Detected joints in '.length), ' (')
      const cam = hit?.cam ?? this.cameraOf(line.slice('Detected joints in '.length).replace(/ \([^()]*\)$/, ''))
      const detail = hit ? hit.after.replace(/\)$/, '') : (line.match(/ \(([^()]*)\)$/)?.[1] ?? '')
      this.setVideo(cam, { fraction: 1, state: 'done', detail })
      this.startQueued()
      this.stage = 'detecting'
      this.detail = `Detected joints in ${cam ?? baseName(line.slice('Detected joints in '.length))}`
      return
    }
    if (line.startsWith('Detection failed for ') && !/^Detection failed for \d+ of \d+ video/.test(line)) {
      // the per-file line from stage 1 (the full path on stdout, the file name in the SystemExit text);
      // the "N of M video(s)" summary is handled as an error below
      const hit = this.cameraAt(line.slice('Detection failed for '.length), ': ')
      if (hit) {
        this.setVideo(hit.cam, { fraction: 1, state: 'failed', detail: hit.after })
        this.startQueued()
        this.stage = 'detecting'
        this.detail = `Detection failed for ${hit.cam}`
        return
      }
    }
    if (line.startsWith('Using saved joints for ')) {
      // the joints file named in the bracket repeats the file stem, so it may hold brackets too
      const rest = line.slice('Using saved joints for '.length)
      const cam = this.cameraAt(rest, ' (')?.cam ?? this.cameraOf(rest.replace(/ \([^()]*\)$/, ''))
      this.setVideo(cam, { fraction: 1, state: 'reused', detail: 'saved joints reused' })
      this.stage = 'detecting'
      this.detail = `Reusing saved joints for ${cam ?? baseName(rest)}`
      return
    }
    // run_pipeline.py prints "Chirp at" instead of "Clap at" when the chirp is the sync sound
    if ((m = line.match(/^(?:Clap|Chirp) at (.*)$/)) || line.startsWith('Using saved clap times')) {
      this.finishDetect()
      this.after = WEIGHTS.sync
      this.stage = 'calibrating'
      this.detail = m ? `Synchronised: ${m[1]}` : 'Synchronised from the saved clap times'
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
    // stderr lines were collected by noteStderr; an error printed on stdout is a one-line message
    if (!fromStderr && (line.startsWith('FAILED') || /Error:/.test(line)) && !/^\s/.test(line)) {
      this.message = [line.replace(/^FAILED:\s*/, '')]
    }
    if (line.startsWith('FAILED')) {
      this.stage = 'failed'
      this.detail = this.message.join(' ')
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
