/**
 * The file-system side of the main process, kept free of Electron so the
 * tests can load it with plain Node: which files in a folder are the take's
 * videos, where a run's output goes by default, and which files the page may
 * read back.
 */
import { promises as fs } from 'node:fs'
import path from 'node:path'

import type { VideoFile } from '../shared/types'

export const VIDEO_EXTENSIONS = new Set(['.mov', '.mp4'])
/** What read-text serves: the pipeline's results and logs, nothing else. */
export const RESULT_EXTENSIONS = new Set(['.bvh', '.json', '.log', '.txt'])

/** The videos in a folder, sorted by name with numbers in order (cam2 before cam10): the filming protocol's camera order. */
export async function listVideos(dir: string): Promise<VideoFile[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true })
  const videos: VideoFile[] = []
  for (const e of entries) {
    if (!e.isFile() || !VIDEO_EXTENSIONS.has(path.extname(e.name).toLowerCase())) continue
    const full = path.join(dir, e.name)
    const st = await fs.stat(full)
    videos.push({ path: full, name: e.name, sizeMb: Math.round((st.size / 1024 / 1024) * 10) / 10 })
  }
  return videos.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
}

/** backend/output/<take folder name>-<YYYYMMDD-HHMM>, one folder per take as processing-a-take.md asks. */
export function defaultOutDir(backendDir: string, videoDir: string, now: Date = new Date()): string {
  const stamp = now.toISOString().slice(0, 16).replace(/[-:T]/g, '').replace(/(\d{8})(\d{4})/, '$1-$2')
  return path.join(backendDir, 'output', `${path.basename(videoDir)}-${stamp}`)
}

/** True for an absolute path to a result file the page is allowed to read. */
export function isResultFile(file: string): boolean {
  return path.isAbsolute(file) && RESULT_EXTENSIONS.has(path.extname(file).toLowerCase())
}
