/**
 * Runs backend/mocap_pipeline/run_pipeline.py as a child process and turns its
 * output into log lines and progress events. Also runs the pre-flight check,
 * backend/mocap_pipeline/check_videos.py, the same way.
 */
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { createInterface } from 'node:readline'
import path from 'node:path'

import { parseCheckOutput } from '../shared/check'
import { ProgressTracker } from '../shared/progress'
import type { CheckResult, Progress, RunOptions, RunResult } from '../shared/types'

/** The repository root: this file is desktop/dist/main/main/pipeline.js. */
export const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..')
export const BACKEND_DIR = path.join(REPO_ROOT, 'backend')

const PYTHON_ENV = { MOCAP_PROGRESS: '1', PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' }

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
    '--jobs',
    String(options.jobs),
  ]
  // the pipeline's own default is 1.0; only pass a changed value so the command stays readable
  if (options.clapThreshold !== 1) args.push('--clap-threshold', String(options.clapThreshold))
  if (options.clapTimes) args.push('--sync', ...options.clapTimes.map(String))
  if (options.recalibrate) args.push('--recalibrate')
  if (options.resume) args.push('--resume')
  return args
}

export function checkArgs(videos: string[], clapThreshold: number): string[] {
  const args = ['-u', '-m', 'mocap_pipeline.check_videos', ...videos]
  if (clapThreshold !== 1) args.push('--clap-threshold', String(clapThreshold))
  return args
}

function commandLine(python: string, args: string[]): string {
  return `$ ${python} ${args.map((a) => (a.includes(' ') ? `"${a}"` : a)).join(' ')}`
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
  onLine(commandLine(python, args))

  let child: ChildProcess
  let cancelled = false
  const done = new Promise<RunResult>((resolve) => {
    child = spawn(python, args, {
      cwd: BACKEND_DIR,
      env: { ...process.env, ...PYTHON_ENV },
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

/** The pre-flight check: seconds per take, no pose model. Everything it prints also goes to onLine. */
export function runCheck(videos: string[], clapThreshold: number, onLine: (line: string) => void): Promise<CheckResult> {
  const python = resolvePython()
  const args = checkArgs(videos, clapThreshold)
  onLine(commandLine(python, args))
  const lines: string[] = []
  return new Promise((resolve) => {
    const child = spawn(python, args, { cwd: BACKEND_DIR, env: { ...process.env, ...PYTHON_ENV }, windowsHide: true })
    child.on('error', (e) => {
      onLine(`Could not start ${python}: ${e.message}`)
      resolve({ ok: false, videos: [], across: [], output: '', error: `Could not start ${python}: ${e.message}` })
    })
    const collect = (line: string) => {
      onLine(line)
      lines.push(line)
    }
    if (child.stdout) createInterface({ input: child.stdout }).on('line', collect)
    if (child.stderr) createInterface({ input: child.stderr }).on('line', collect)
    child.on('close', (code) => {
      const result = parseCheckOutput(lines.join('\n'), code)
      // nothing parsed and a non-zero exit: the check itself did not run (missing module, bad Python)
      if (!result.videos.length && code !== 0) result.error = lines.filter((l) => l.trim()).slice(-1)[0] ?? `exit code ${code}`
      resolve(result)
    })
  })
}
