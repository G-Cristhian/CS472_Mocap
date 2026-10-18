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

export interface Progress {
  stage: Stage
  /** 0..1 over the whole run */
  fraction: number
  /** what is being worked on right now, e.g. "Detecting joints in cam1.mp4, frame 300/3600" */
  detail: string
}

export interface RunResult {
  ok: boolean
  exitCode: number | null
  bvhPath?: string
  jsonPath?: string
  metricsPath?: string
  error?: string
}

/** What the preload script exposes to the page as window.backend. */
export interface Backend {
  chooseDirectory(): Promise<string | null>
  listVideos(dir: string): Promise<VideoFile[]>
  defaultOutDir(videoDir: string): Promise<string>
  run(options: RunOptions): Promise<RunResult>
  cancel(): Promise<void>
  onLog(callback: (line: string) => void): () => void
  onProgress(callback: (progress: Progress) => void): () => void
  readText(path: string): Promise<string>
  openFolder(path: string): Promise<void>
}
