/**
 * The frame-by-frame report behind the result panel's cameras, timelines and
 * joint stories: <out>.report.json, which backend/mocap_pipeline/report.py
 * builds from the files a run leaves behind (2D joints per camera, clap times,
 * calibration, 3D joints). Built on first view and rebuilt when any of those
 * files is newer, so it works for every past run whose folder still has them.
 * Electron-free so the tests can load it with plain Node.
 */
import { spawn } from 'node:child_process'
import { promises as fs } from 'node:fs'
import path from 'node:path'

import { REPORT_VERSION } from '../shared/report'
import type { ReportResult } from '../shared/types'
import { SNAPSHOT_DIR } from './library'

const METRICS_SUFFIX = '.metrics.json'

/** The live files of the run a metrics file belongs to; a copy in runs/<time>/ maps to its folder. */
export function runFiles(metricsPath: string) {
  const name = path.basename(metricsPath)
  const stem = name.endsWith(METRICS_SUFFIX) ? name.slice(0, -METRICS_SUFFIX.length) : path.parse(name).name
  let folder = path.dirname(metricsPath)
  const snapshot = path.basename(path.dirname(folder)) === SNAPSHOT_DIR
  if (snapshot) folder = path.dirname(path.dirname(folder))
  return {
    folder,
    snapshot,
    metrics: path.join(folder, stem + METRICS_SUFFIX),
    out: path.join(folder, stem + '.json'),
    report: path.join(folder, stem + '.report.json'),
    // the smoothed output last: the speeds come from it, and a run may stop before writing it
    inputs: [
      path.join(folder, stem + '.pose.npz'),
      path.join(folder, stem + '.sync.json'),
      path.join(folder, 'calibration.json'),
      path.join(folder, stem + '.json'),
    ],
    keypointsPrefix: stem + '.keypoints.',
  }
}

async function mtime(file: string): Promise<number | null> {
  try {
    return (await fs.stat(file)).mtimeMs
  } catch {
    return null
  }
}

async function started(file: string): Promise<string | null> {
  try {
    return JSON.parse(await fs.readFile(file, 'utf8'))?.run?.started ?? null
  } catch {
    return null
  }
}

/** True when the saved report is at least as new as every file it was built from. */
export async function reportIsFresh(files: ReturnType<typeof runFiles>): Promise<boolean> {
  const own = await mtime(files.report)
  if (own === null) return false
  let entries: string[] = []
  try {
    entries = (await fs.readdir(files.folder)).filter((n) => n.startsWith(files.keypointsPrefix)).map((n) => path.join(files.folder, n))
  } catch {
    return false
  }
  for (const f of [...files.inputs, ...entries]) {
    const t = await mtime(f)
    if (t !== null && t > own) return false
  }
  try {
    return JSON.parse(await fs.readFile(files.report, 'utf8')).version === REPORT_VERSION
  } catch {
    return false
  }
}

function build(python: string, backendDir: string, out: string): Promise<string | null> {
  return new Promise((resolve) => {
    const lines: string[] = []
    const child = spawn(python, ['-u', '-m', 'mocap_pipeline.report', out], {
      cwd: backendDir,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      windowsHide: true,
    })
    child.on('error', (e) => resolve(`Could not start ${python}: ${e.message}`))
    child.stdout.on('data', (d) => lines.push(String(d)))
    child.stderr.on('data', (d) => lines.push(String(d)))
    child.on('close', (code) => {
      if (code === 0) return resolve(null)
      const last = lines.join('').split(/\r?\n/).filter((l) => l.trim()).slice(-1)[0]
      resolve(last ?? `exit code ${code}`)
    })
  })
}

/**
 * The report for the run whose metrics file this is. A copy in runs/<time>/ only
 * gets one while its folder's latest run is that same run: the per-frame files
 * are overwritten by the next run into the folder.
 */
export async function loadReport(metricsPath: string, python: string, backendDir: string): Promise<ReportResult> {
  const files = runFiles(metricsPath)
  if (files.snapshot) {
    const [mine, live] = await Promise.all([started(metricsPath), started(files.metrics)])
    if (!mine || mine !== live) {
      return {
        ok: false,
        error: 'This is a copy of an earlier run; its folder has been run again since, so the frame-by-frame files are the later run’s.',
      }
    }
  }
  if (!(await reportIsFresh(files))) {
    for (const f of files.inputs.slice(0, 2)) {
      if ((await mtime(f)) === null) return { ok: false, error: `${path.basename(f)} is not in the run's folder (did the run stop early?)` }
    }
    const error = await build(python, backendDir, files.out)
    if (error) return { ok: false, error }
  }
  return { ok: true, text: await fs.readFile(files.report, 'utf8') }
}
