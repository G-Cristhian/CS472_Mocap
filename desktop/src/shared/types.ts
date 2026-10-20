/** Shapes shared by the Electron main process, the preload bridge and the renderer. */

export interface VideoFile {
  path: string
  name: string
  sizeMb: number
}

export type Detector = 'mediapipe' | 'rtmpose'
export type Smoother = 'savgol' | 'butterworth'

export interface RunOptions {
  /** absolute paths, camera 0 first */
  videos: string[]
  heightM: number
  /** the take's own folder; out3d.json, calibration.json and the stage files go here */
  outDir: string
  detector: Detector
  /** stage 2c filter; both are kept so they can be compared on one take */
  smoother: Smoother
  /** horizontal field of view for non-iPhone cameras, degrees */
  fov: number
  /** multiplies how loud a clap must be against the room; 0.5 accepts a clap half as strong */
  clapThreshold: number
  /** clap time per video in seconds, camera 0 first; null = find them from the audio */
  clapTimes: number[] | null
  /** how many videos stage 1 detects at once, each in its own process; 0 = pick automatically */
  jobs: number
  recalibrate: boolean
  resume: boolean
}

export type Stage =
  | 'starting'
  | 'detecting'
  | 'syncing'
  | 'calibrating'
  | 'triangulating'
  | 'writing'
  | 'done'
  | 'failed'

export type VideoState = 'waiting' | 'detecting' | 'done' | 'reused' | 'failed'

/** Stage 1 as seen per video, so a failed file is named while the others carry on. */
export interface VideoProgress {
  name: string
  state: VideoState
  /** e.g. "frame 300 of 3600", "41 s", or the error text */
  detail: string
}

export interface Progress {
  stage: Stage
  /** 0..1 over the whole run */
  fraction: number
  /** what is being worked on right now, e.g. "Detecting joints in cam1.mp4, frame 300/3600" */
  detail: string
  videos: VideoProgress[]
}

export interface RunResult {
  ok: boolean
  exitCode: number | null
  bvhPath?: string
  jsonPath?: string
  metricsPath?: string
  error?: string
}

/** What check_videos printed about one file. */
export interface CheckedVideo {
  name: string
  /** "1920x1080, 59.94 fps, 1800 frames, 30.0 s" */
  video?: string
  lens?: string
  /** clap time in seconds, when one was found */
  clapS?: number
  warnings: string[]
  failures: string[]
}

export interface CheckResult {
  /** exit code 0: every file is usable */
  ok: boolean
  videos: CheckedVideo[]
  /** the cross-camera warnings and the refined clap times */
  across: string[]
  /** everything check_videos printed, for the log */
  output: string
  /** set when the check itself could not run (no Python, no module) */
  error?: string
}

/** What the preload script exposes to the page as window.backend. */
export interface Backend {
  chooseDirectory(): Promise<string | null>
  listVideos(dir: string): Promise<VideoFile[]>
  defaultOutDir(videoDir: string): Promise<string>
  /** the pre-flight check (mocap_pipeline.check_videos): seconds per take, no pose model */
  checkVideos(videos: string[], clapThreshold: number): Promise<CheckResult>
  run(options: RunOptions): Promise<RunResult>
  cancel(): Promise<void>
  onLog(callback: (line: string) => void): () => void
  onProgress(callback: (progress: Progress) => void): () => void
  readText(path: string): Promise<string>
  openFolder(path: string): Promise<void>
}
