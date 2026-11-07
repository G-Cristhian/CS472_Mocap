/**
 * The results library: every run's numbers, read back from the output folders
 * on disk, so it lists past runs and terminal runs too and survives closing
 * the app. Electron-free so the tests can load it with plain Node.
 *
 * A run into a folder that already holds one overwrites <out>.metrics.json and
 * <out>.bvh (a --resume rerun with the other smoother does this on purpose).
 * So after every run the app copies both into <folder>/runs/<start time>/
 * (snapshotRun), and the library reads those copies as well as the live files.
 */
import { promises as fs } from 'node:fs'
import path from 'node:path'

import { summarise } from '../shared/metrics'
import type { LibraryRun } from '../shared/types'

const METRICS_SUFFIX = '.metrics.json'
export const SNAPSHOT_DIR = 'runs'

type Json = Record<string, unknown>

async function readJson(file: string): Promise<Json | null> {
  try {
    const value = JSON.parse(await fs.readFile(file, 'utf8'))
    return value && typeof value === 'object' && !Array.isArray(value) ? (value as Json) : null
  } catch {
    return null
  }
}

async function exists(file: string): Promise<boolean> {
  try {
    await fs.access(file)
    return true
  } catch {
    return false
  }
}

async function metricsFiles(dir: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true })
    return entries.filter((e) => e.isFile() && e.name.endsWith(METRICS_SUFFIX)).map((e) => path.join(dir, e.name))
  } catch {
    return []
  }
}

async function subfolders(dir: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true })
    return entries.filter((e) => e.isDirectory()).map((e) => path.join(dir, e.name))
  } catch {
    return []
  }
}

/** "2026-11-07T14:25:17-08:00" -> "20261107-142517", a folder name every system accepts. */
export function snapshotName(started: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/.exec(started)
  return m ? `${m[1]}${m[2]}${m[3]}-${m[4]}${m[5]}${m[6]}` : started.replace(/[^\w-]+/g, '_')
}

/**
 * Copies a finished run's metrics and skeleton (every <out>.metrics.json in `outDir`, with its
 * <out>.bvh) into outDir/runs/<start time>/, so a later run into the same folder cannot erase
 * them. Returns the snapshot folders made; a run that wrote no metrics leaves nothing to keep.
 */
export async function snapshotRun(outDir: string): Promise<string[]> {
  const made: string[] = []
  for (const metricsPath of await metricsFiles(outDir)) {
    const m = await readJson(metricsPath)
    const started = (m?.run as Json | undefined)?.started
    if (typeof started !== 'string') continue
    const dir = path.join(outDir, SNAPSHOT_DIR, snapshotName(started))
    await fs.mkdir(dir, { recursive: true })
    await fs.copyFile(metricsPath, path.join(dir, path.basename(metricsPath)))
    const bvh = metricsPath.slice(0, -METRICS_SUFFIX.length) + '.bvh'
    if (await exists(bvh)) await fs.copyFile(bvh, path.join(dir, path.basename(bvh)))
    made.push(dir)
  }
  return made
}

function str(v: unknown): string | null {
  return typeof v === 'string' ? v : null
}

function num(m: Json, ...keys: string[]): number | null {
  let node: unknown = m
  for (const k of keys) node = node && typeof node === 'object' ? (node as Json)[k] : undefined
  return typeof node === 'number' && isFinite(node) ? node : null
}

/** Every camera's frame count in stage 1 added up; null when stage 1 recorded none. */
function videoFrames(m: Json): number | null {
  const stage1 = m.stage1
  if (!stage1 || typeof stage1 !== 'object') return null
  let total = 0
  for (const cam of Object.values(stage1 as Json)) {
    const f = cam && typeof cam === 'object' ? (cam as Json).frames : undefined
    if (typeof f === 'number' && isFinite(f)) total += f
  }
  return total || null
}

/** One library row from one metrics file; null when it is not a pipeline run's metrics. */
export async function readRun(metricsPath: string, folder: string): Promise<LibraryRun | null> {
  const m = await readJson(metricsPath)
  const run = m?.run as Json | undefined
  if (!m || !run || typeof run !== 'object') return null
  const videos = Array.isArray(run.videos) ? run.videos.filter((v): v is string => typeof v === 'string') : []
  // the take is the folder the videos came from; Windows paths read on a Mac still split on "\"
  const take = videos.length ? videos[0].split(/[\\/]/).slice(-2, -1)[0] || path.basename(folder) : path.basename(folder)
  const bvh = metricsPath.slice(0, -METRICS_SUFFIX.length) + '.bvh'
  const options = run.detector_options && typeof run.detector_options === 'object' ? (run.detector_options as Json) : null
  return {
    metricsPath,
    bvhPath: (await exists(bvh)) ? bvh : null,
    folder,
    take,
    started: str(run.started),
    finished: str(run.finished),
    status: str(run.status) ?? 'unknown',
    detector: str(run.detector) ?? '–',
    rtmposeMode: options ? str(options.mode) : null,
    rtmposeDetectEvery: options && typeof options.detect_every === 'number' ? options.detect_every : null,
    cameras: videos.length,
    resumed: run.resume === true,
    frames: num(m, 'pose_final', 'frames'),
    videoFrames: videoFrames(m),
    detectS: num(m, 'timing', 'detect_total_s'),
    summary: summarise(m),
  }
}

/**
 * Every run under `parents` (each subfolder is one output folder, as backend/output holds them)
 * and in `folders` (output folders elsewhere, such as ones chosen by hand this session): the live
 * metrics and the snapshots in runs/. The live file and its snapshot are one run, read once.
 * Newest first.
 */
export async function listRuns(parents: string[], folders: string[] = []): Promise<LibraryRun[]> {
  const outputFolders = new Set(folders.map((f) => path.resolve(f)))
  for (const parent of parents) for (const f of await subfolders(parent)) outputFolders.add(path.resolve(f))
  const seen = new Set<string>()
  const runs: LibraryRun[] = []
  for (const folder of outputFolders) {
    const snapshots = (await subfolders(path.join(folder, SNAPSHOT_DIR))).sort().reverse()
    // snapshots first: their files are never overwritten, so they win over the live copy of the same run
    const files = [
      ...(await Promise.all(snapshots.map(metricsFiles))).flat(),
      ...(await metricsFiles(folder)),
    ]
    for (const file of files) {
      const run = await readRun(file, folder)
      if (!run) continue
      const key = `${folder}\n${path.basename(file)}\n${run.started ?? file}`
      if (seen.has(key)) continue
      seen.add(key)
      runs.push(run)
    }
  }
  return runs.sort((a, b) => (b.started ?? '').localeCompare(a.started ?? ''))
}
