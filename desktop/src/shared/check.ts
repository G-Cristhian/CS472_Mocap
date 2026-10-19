/**
 * Reads what backend/mocap_pipeline/check_videos.py prints into one record per
 * video. Pure, so the browser mock and the tests use it too.
 *
 * The output looks like:
 *
 *     cam0.MOV
 *       video   1920x1080, 59.94 fps, 1800 frames, 30.0 s
 *       lens    iPhone 16 Pro, Back Camera, 24 mm (35 mm equiv.) from metadata
 *       clap    1.196 s
 *       WARNING clap close to the 10 s search window; clap sooner
 *       FAIL    no clap: ...
 *
 *     across cameras
 *       WARNING frame rates differ between phones: [30, 60] (...)
 *       claps   cam0.MOV 1.196 s, cam1.MOV 0.903 s (cross-checked against camera 0)
 *
 *     All files usable.
 */
import type { CheckResult, CheckedVideo } from './types'

export function parseCheckOutput(output: string, exitCode: number | null): CheckResult {
  const videos: CheckedVideo[] = []
  const across: string[] = []
  let current: CheckedVideo | null = null
  let inAcross = false

  for (const raw of output.split(/\r?\n/)) {
    const line = raw.trimEnd()
    if (!line.trim()) continue
    if (!/^\s/.test(line)) {
      // a line at the left margin names a file, opens the cross-camera block, or is the verdict
      if (line === 'across cameras') {
        inAcross = true
        current = null
      } else if (/^(All files usable\.|\d+ file\(s\) the pipeline cannot use\.|WARNING )/.test(line)) {
        if (line.startsWith('WARNING ')) across.push(line.slice(8))
        inAcross = false
        current = null
      } else {
        current = { name: line, warnings: [], failures: [] }
        videos.push(current)
        inAcross = false
      }
      continue
    }
    const m = line.match(/^\s+(\S+)\s+(.*)$/)
    if (!m) continue
    const [, key, text] = m
    if (inAcross) {
      across.push(key === 'WARNING' ? text : `${key} ${text}`)
      continue
    }
    if (!current) continue
    if (key === 'video') current.video = text
    else if (key === 'lens') current.lens = text
    else if (key === 'clap') {
      const t = text.match(/^([\d.]+) s/)
      if (t) current.clapS = Number(t[1])
    } else if (key === 'WARNING') current.warnings.push(text)
    else if (key === 'FAIL') current.failures.push(text)
  }
  return { ok: exitCode === 0, videos, across, output }
}
