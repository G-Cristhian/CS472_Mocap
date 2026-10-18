/**
 * Runs backend/mocap_pipeline/run_pipeline.py as a child process and turns its
 * output into log lines and progress events.
 */
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { createInterface } from 'node:readline'
import path from 'node:path'

import { ProgressTracker } from '../shared/progress'
import type { Progress, RunOptions, RunResult } from '../shared/types'

/** The repository root: this file is desktop/dist/main/main/pipeline.js. */
export const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..')
export const BACKEND_DIR = path.join(REPO_ROOT, 'backend')

/** The backend venv's Python if it exists, otherwise whatever `python3` / `python` is on the PATH. */
export function resolvePython(): string {
  const candidates = [
    path.join(BACKEND_DIR, '.venv', 'Scripts', 'python.exe'),
    path.join(BACKEND_DIR, '.venv', 'bin', 'python'),
  ]
  for (const c of candidates) if (existsSync(c)) return c
  return process.platform === 'win32' ? 'python' : 'python3'
}

export function pipelineArgs(options: RunOptions): string[] {
  const args = [
    '-u',
    '-m',
    'mocap_pipeline.run_pipeline',
    ...options.videos,
    '--height-m',
    String(options.heightM),
    '--out',
    path.join(options.outDir, 'out3d.json'),
    '--calibration',
    path.join(options.outDir, 'calibration.json'),
    '--detector',
    options.detector,
    '--smoother',
    options.smoother,
    '--fov',
    String(options.fov),
  ]
  if (options.recalibrate) args.push('--recalibrate')
  if (options.resume) args.push('--resume')
  return args
}

export interface RunHandle {
  done: Promise<RunResult>
  cancel(): void
}

export function runPipeline(
  options: RunOptions,
  onLine: (line: string) => void,
  onProgress: (progress: Progress) => void,
): RunHandle {
  const tracker = new ProgressTracker(options.videos)
  const python = resolvePython()
  const args = pipelineArgs(options)
  onLine(`$ ${python} ${args.map((a) => (a.includes(' ') ? `"${a}"` : a)).join(' ')}`)

  let child: ChildProcess
  let cancelled = false
  const done = new Promise<RunResult>((resolve) => {
    child = spawn(python, args, {
      cwd: BACKEND_DIR,
      env: { ...process.env, MOCAP_PROGRESS: '1', PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
      windowsHide: true,
    })
    child.on('error', (e) => {
      onLine(`Could not start ${python}: ${e.message}`)
      resolve({ ok: false, exitCode: null, error: `Could not start ${python}: ${e.message}` })
    })
    const feed = (fromStderr: boolean) => (line: string) => {
      onLine(line)
      const p = tracker.feed(line, fromStderr)
      if (p) onProgress(p)
    }
    if (child.stdout) createInterface({ input: child.stdout }).on('line', feed(false))
    if (child.stderr) createInterface({ input: child.stderr }).on('line', feed(true))
    child.on('close', (code) => resolve(tracker.result(code, cancelled)))
  })

  return {
    done,
    cancel() {
      cancelled = true
      child?.kill()
    },
  }
}
