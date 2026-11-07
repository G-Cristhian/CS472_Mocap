/**
 * The results library's table: its columns, how a column sorts, which rows a
 * filter keeps, and how each number is coloured. Pure, so it is tested on its
 * own (test/libraryTable.test.cjs); the page only draws it.
 */
import { grade, type Grade } from './metrics'
import type { LibraryRun } from './types'

export interface Column {
  key: string
  title: string
  /** what the cell shows */
  text(r: LibraryRun): string
  /** what it sorts by; null sorts last either way */
  value(r: LibraryRun): number | string | null
  grade?(r: LibraryRun): Grade
  /** a hover note on the header */
  note?: string
}

const fix = (v: number | null, digits: number) => (v === null ? '–' : v.toFixed(digits))

/** "RTMPose balanced, every 5" / "MediaPipe" */
export function detectorText(r: LibraryRun): string {
  if (r.detector === 'mediapipe') return 'MediaPipe'
  if (r.detector !== 'rtmpose') return r.detector
  const every = r.rtmposeDetectEvery ?? 1
  return `RTMPose ${r.rtmposeMode ?? 'balanced'}${every === 1 ? '' : `, every ${every}`}`
}

/** "2026-11-07T14:25:17-08:00" -> "2026-11-07 14:25", the wall-clock time the pipeline wrote */
export function startedText(started: string | null): string {
  return started ? started.slice(0, 16).replace('T', ' ') : '–'
}

/** video frames detected per second of stage 1, all cameras together; a resumed run did not detect */
export function detectFps(r: LibraryRun): number | null {
  return r.resumed || !r.detectS || !r.videoFrames ? null : r.videoFrames / r.detectS
}

export const COLUMNS: Column[] = [
  { key: 'started', title: 'Started', text: (r) => startedText(r.started), value: (r) => r.started },
  { key: 'take', title: 'Take', text: (r) => r.take, value: (r) => r.take.toLowerCase() },
  { key: 'detector', title: 'Detector', text: detectorText, value: (r) => detectorText(r).toLowerCase() },
  {
    key: 'smoother',
    title: 'Smoother',
    text: (r) => (r.summary.smoother === 'savgol' ? 'Savitzky-Golay' : r.summary.smoother === 'butterworth' ? 'Butterworth' : r.summary.smoother),
    value: (r) => r.summary.smoother,
  },
  { key: 'cameras', title: 'Cams', text: (r) => String(r.cameras || '–'), value: (r) => r.cameras || null },
  { key: 'status', title: 'Status', text: (r) => r.status, value: (r) => r.status },
  {
    key: 'total',
    title: 'Time (s)',
    text: (r) => `${fix(r.summary.totalS, 0)}${r.resumed ? ' (resumed)' : ''}`,
    value: (r) => r.summary.totalS,
    note: 'Whole run. A resumed run reused the detection, so its time is not comparable.',
  },
  {
    key: 'detect',
    title: 'Detection (s)',
    text: (r) => (r.resumed ? '–' : fix(r.detectS, 0)),
    value: (r) => (r.resumed ? null : r.detectS),
    note: 'Stage 1, all videos at once: the part the detector settings change.',
  },
  {
    key: 'fps',
    title: 'Frames/s',
    text: (r) => fix(detectFps(r), 1),
    value: detectFps,
    note: 'Video frames detected per second, all cameras together: the detector’s speed on this machine.',
  },
  {
    key: 'calibration',
    title: 'Calib. worst (px)',
    text: (r) => fix(r.summary.calibrationWorstPx, 2),
    value: (r) => r.summary.calibrationWorstPx,
    grade: (r) => grade(r.summary.calibrationWorstPx, 3, 10),
  },
  {
    key: 'reprojection',
    title: 'Triang. (px)',
    text: (r) => fix(r.summary.reprojectionPx, 2),
    value: (r) => r.summary.reprojectionPx,
    grade: (r) => grade(r.summary.reprojectionPx, 3, 10),
    note: 'Mean reprojection error of the 3D joints.',
  },
  {
    key: 'bones',
    title: 'Bone spread (mm)',
    text: (r) => fix(r.summary.boneSpreadMm, 1),
    value: (r) => r.summary.boneSpreadMm,
    grade: (r) => grade(r.summary.boneSpreadMm, 10, 20),
  },
  {
    key: 'missing',
    title: 'Missing (%)',
    text: (r) => fix(r.summary.missingPercent, 1),
    value: (r) => r.summary.missingPercent,
    grade: (r) => grade(r.summary.missingPercent, 5, 15),
  },
  {
    key: 'jitter',
    title: 'Jitter raw → smoothed (mm)',
    text: (r) => `${fix(r.summary.jitterRawMm, 1)} → ${fix(r.summary.jitterFinalMm, 1)}`,
    value: (r) => r.summary.jitterFinalMm,
  },
]

export interface LibraryView {
  /** '' for every take */
  take: string
  /** hide runs whose status is not "done" */
  doneOnly: boolean
  sortKey: string
  descending: boolean
}

export const DEFAULT_VIEW: LibraryView = { take: '', doneOnly: false, sortKey: 'started', descending: true }

/** The takes in the library, for the filter, sorted by name. */
export function takes(runs: LibraryRun[]): string[] {
  return [...new Set(runs.map((r) => r.take))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
}

/** The rows to show, filtered and sorted; empty values go last whichever way the column sorts. */
export function viewRows(runs: LibraryRun[], view: LibraryView): LibraryRun[] {
  const column = COLUMNS.find((c) => c.key === view.sortKey) ?? COLUMNS[0]
  const kept = runs.filter((r) => (!view.take || r.take === view.take) && (!view.doneOnly || r.status === 'done'))
  return kept
    .map((r, i) => ({ r, i, v: column.value(r) }))
    .sort((a, b) => {
      if (a.v === null || b.v === null) return a.v === b.v ? a.i - b.i : a.v === null ? 1 : -1
      const c = typeof a.v === 'number' && typeof b.v === 'number' ? a.v - b.v : String(a.v).localeCompare(String(b.v))
      return (view.descending ? -c : c) || a.i - b.i
    })
    .map((x) => x.r)
}
