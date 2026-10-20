/**
 * Turns <out>.metrics.json (backend/mocap_pipeline/metrics.py) into the rows the
 * result panel shows: where the error comes from, camera by camera and joint
 * by joint, and what smoothing did to it. Pure, so it is tested on its own.
 */

export type Grade = 'good' | 'bad' | ''

export interface MetricRow {
  label: string
  value: string
  grade: Grade
}

export interface MetricSection {
  title: string
  rows: MetricRow[]
}

/** The handful of numbers worth keeping per run, to compare runs of one take. */
export interface RunSummary {
  detector: string
  smoother: string
  clapSource: string
  calibrationWorstPx: number | null
  reprojectionPx: number | null
  jitterRawMm: number | null
  jitterFinalMm: number | null
  boneSpreadMm: number | null
  missingPercent: number | null
  totalS: number | null
}

type Json = Record<string, unknown>

function at(m: Json, path: string): unknown {
  let node: unknown = m
  for (const key of path.split('.')) {
    if (node === null || typeof node !== 'object') return undefined
    node = (node as Json)[key]
  }
  return node
}

function num(m: Json, path: string): number | null {
  const v = at(m, path)
  return typeof v === 'number' && isFinite(v) ? v : null
}

function numbers(m: Json, path: string): Record<string, number> {
  const v = at(m, path)
  if (v === null || typeof v !== 'object') return {}
  const out: Record<string, number> = {}
  for (const [k, x] of Object.entries(v as Json)) if (typeof x === 'number' && isFinite(x)) out[k] = x
  return out
}

function grade(value: number | null, good: number, bad: number): Grade {
  if (value === null) return ''
  if (good < bad) return value <= good ? 'good' : value >= bad ? 'bad' : ''
  return value >= good ? 'good' : value <= bad ? 'bad' : ''
}

const dash = '–'
const fix = (v: number | null, digits: number, unit = '') => (v === null ? dash : `${v.toFixed(digits)}${unit}`)

/** The largest values first, as "name value, name value". */
function worst(values: Record<string, number>, n: number, digits: number, unit: string): string {
  const sorted = Object.entries(values).sort((a, b) => b[1] - a[1]).slice(0, n)
  return sorted.length ? sorted.map(([k, v]) => `${k.toLowerCase()} ${v.toFixed(digits)}${unit}`).join(', ') : dash
}

export function summarise(m: Json): RunSummary {
  const calib = numbers(m, 'calibrate.reprojection_error_px')
  const calibValues = Object.values(calib)
  const raw = num(m, 'pose_raw.jitter_mm')
  const final = num(m, 'pose_final.jitter_mm')
  const bone = num(m, 'rig.bone_lengths.mean_std_m')
  const missing = num(m, 'pose_final.missing_fraction')
  return {
    detector: String(at(m, 'run.detector') ?? dash),
    smoother: String(at(m, 'smooth.method') ?? at(m, 'run.smoother') ?? dash),
    clapSource: String(at(m, 'sync.clap_times_from') ?? dash),
    calibrationWorstPx: calibValues.length ? Math.max(...calibValues) : null,
    reprojectionPx: num(m, 'triangulate.mean_reprojection_px'),
    jitterRawMm: raw,
    jitterFinalMm: final,
    boneSpreadMm: bone === null ? null : bone * 1000,
    missingPercent: missing === null ? null : missing * 100,
    totalS: num(m, 'timing.total_s'),
  }
}

export function metricSections(m: Json): MetricSection[] {
  const s = summarise(m)
  const sections: MetricSection[] = []

  // ---- the headline, the five numbers the old panel showed ----
  const upright = num(m, 'scale.upright_frames')
  sections.push({
    title: 'At a glance',
    rows: [
      { label: 'Calibration error, worst camera', value: fix(s.calibrationWorstPx, 2, ' px'), grade: grade(s.calibrationWorstPx, 3, 10) },
      { label: 'Triangulation error, mean', value: fix(s.reprojectionPx, 2, ' px'), grade: grade(s.reprojectionPx, 3, 10) },
      { label: 'Bone length spread', value: fix(s.boneSpreadMm, 1, ' mm'), grade: grade(s.boneSpreadMm, 10, 20) },
      { label: 'Joints missing', value: fix(s.missingPercent, 1, ' %'), grade: grade(s.missingPercent, 5, 15) },
      { label: 'Upright frames for height', value: upright === null ? dash : String(upright), grade: grade(upright, 30, 10) },
      { label: 'Total time', value: fix(s.totalS, 0, ' s'), grade: '' },
    ],
  })

  // ---- stage 1: how well each camera saw the performer ----
  const stage1 = at(m, 'stage1')
  if (stage1 && typeof stage1 === 'object') {
    const rows: MetricRow[] = []
    for (const [cid, v] of Object.entries(stage1 as Json)) {
      if (cid === 'failed' || !v || typeof v !== 'object') continue
      const cam = v as Json
      const nobody = typeof cam.no_person_fraction === 'number' ? cam.no_person_fraction * 100 : null
      const conf = typeof cam.mean_confidence === 'number' ? cam.mean_confidence : null
      const took = num(m, `timing.detect.${cid}_s`)
      rows.push({
        label: cid,
        value: `${cam.frames ?? dash} frames at ${typeof cam.fps_nominal === 'number' ? cam.fps_nominal.toFixed(1) : dash} fps, `
          + `nobody seen ${fix(nobody, 1, ' %')}, confidence ${fix(conf, 2)}`
          + (took === null ? '' : `, ${took.toFixed(0)} s`),
        grade: nobody === null ? '' : nobody > 20 ? 'bad' : nobody < 5 ? 'good' : '',
      })
    }
    const failed = at(m, 'stage1.failed')
    if (failed && typeof failed === 'object') {
      for (const [cid, err] of Object.entries(failed as Json)) rows.push({ label: `${cid} failed`, value: String(err), grade: 'bad' })
    }
    if (rows.length) sections.push({ title: 'Stage 1, detection per camera', rows })
  }

  // ---- stage 2a: the shared clock ----
  const claps = numbers(m, 'sync.clap_time_s')
  if (Object.keys(claps).length) {
    const threshold = num(m, 'sync.clap_threshold')
    sections.push({
      title: 'Stage 2a, synchronisation',
      rows: [
        { label: 'Clap times', value: Object.entries(claps).map(([c, t]) => `${c} ${t.toFixed(3)} s`).join(', '), grade: '' },
        { label: 'Clap times from', value: s.clapSource + (threshold !== null && threshold !== 1 ? `, threshold ×${threshold}` : ''), grade: '' },
        { label: 'Common clock', value: `${num(m, 'sync.common_frames') ?? dash} frames at ${num(m, 'sync.common_fps') ?? dash} fps`, grade: '' },
      ],
    })
  }

  // ---- stage 2b: where the cameras are, and whether the height was used ----
  const calib = numbers(m, 'calibrate.reprojection_error_px')
  if (Object.keys(calib).length || at(m, 'calibrate.reused_file')) {
    const rows: MetricRow[] = []
    const reused = at(m, 'calibrate.reused_file')
    if (reused) {
      rows.push({
        label: 'Calibration',
        value: `reused ${String(reused)}; the performer height was not used (untick Resume or tick Recalibrate to apply it)`,
        grade: '',
      })
    }
    for (const [cid, px] of Object.entries(calib)) rows.push({ label: `${cid} reprojection error`, value: fix(px, 2, ' px'), grade: grade(px, 3, 10) })
    const scale = num(m, 'scale.metres_per_unit')
    if (scale !== null) {
      // "head top" when the detector found the top of the head (RTMPose), else "ears" plus a fixed offset
      const to = at(m, 'scale.height_from')
      rows.push({
        label: 'Scale',
        value: `${scale.toFixed(4)} m per unit${at(m, 'scale.rescaled_from_height') ? ', from the performer height' : ''}`
          + (typeof to === 'string' ? ` measured to the ${to}` : ''),
        grade: '',
      })
    }
    const aboveEars = num(m, 'scale.head_top_above_ears_m')
    if (aboveEars !== null) {
      rows.push({ label: 'Head top above the ears', value: `${(aboveEars * 100).toFixed(1)} cm, as the detector found it`, grade: '' })
    }
    sections.push({ title: 'Stage 2b, calibration', rows })
  }

  // ---- stage 2c: triangulation, joint by joint ----
  if (at(m, 'triangulate')) {
    const perJoint = numbers(m, 'triangulate.mean_reprojection_px_per_joint')
    const missingPerJoint = numbers(m, 'pose_final.missing_fraction_per_joint')
    const views = num(m, 'pose_raw.mean_views_per_joint')
    const dropped = num(m, 'triangulate.views_dropped')
    const failed = num(m, 'triangulate.joints_failed')
    const few = num(m, 'triangulate.joints_with_fewer_than_2_views')
    sections.push({
      title: 'Stage 2c, triangulation',
      rows: [
        { label: 'Mean reprojection error', value: fix(s.reprojectionPx, 2, ' px'), grade: grade(s.reprojectionPx, 3, 10) },
        { label: 'Worst joints', value: worst(perJoint, 4, 1, ' px'), grade: '' },
        { label: 'Most often missing', value: worst(Object.fromEntries(Object.entries(missingPerJoint).map(([k, v]) => [k, v * 100])), 4, 0, ' %'), grade: '' },
        { label: 'Cameras per joint, mean', value: fix(views, 2), grade: '' },
        {
          label: 'Dropped',
          value: `${dropped ?? dash} camera views, ${failed ?? dash} joints still off, ${few ?? dash} joints seen by fewer than 2 cameras`,
          grade: '',
        },
      ],
    })
  }

  // ---- smoothing: what the filter changed ----
  if (at(m, 'smooth') || s.jitterRawMm !== null) {
    const settings = at(m, 'smooth.settings')
    const gaps = at(m, 'smooth.gaps') as Json | undefined
    const reduction = s.jitterRawMm && s.jitterFinalMm !== null ? (1 - s.jitterFinalMm / s.jitterRawMm) * 100 : null
    sections.push({
      title: 'Smoothing',
      rows: [
        {
          label: 'Smoother',
          value: s.smoother + (settings && typeof settings === 'object' ? ` (${Object.entries(settings as Json).map(([k, v]) => `${k} ${String(v)}`).join(', ')})` : ''),
          grade: '',
        },
        {
          label: 'Jitter, raw → smoothed',
          value: `${fix(s.jitterRawMm, 1)} → ${fix(s.jitterFinalMm, 1)} mm/frame²${reduction === null ? '' : ` (${reduction.toFixed(0)} % less)`}`,
          grade: reduction === null ? '' : reduction > 40 ? 'good' : reduction < 10 ? 'bad' : '',
        },
        {
          label: 'Gaps',
          value: gaps ? `${gaps.filled ?? dash} filled, ${gaps.left_missing ?? dash} too long and left missing` : dash,
          grade: '',
        },
        { label: 'Runs too short to smooth', value: String(at(m, 'smooth.runs_too_short') ?? dash), grade: '' },
      ],
    })
  }

  // ---- stage 3: the rig ----
  const bones = at(m, 'rig.bone_lengths.per_bone')
  if (bones && typeof bones === 'object') {
    const spread: Record<string, number> = {}
    for (const [name, b] of Object.entries(bones as Json)) {
      const std = (b as Json)?.std_m
      if (typeof std === 'number') spread[name] = std * 1000
    }
    sections.push({
      title: 'Stage 3, skeleton',
      rows: [
        { label: 'Bone length spread, mean', value: fix(s.boneSpreadMm, 1, ' mm'), grade: grade(s.boneSpreadMm, 10, 20) },
        { label: 'Least rigid bones', value: worst(spread, 4, 1, ' mm'), grade: '' },
      ],
    })
  }

  return sections
}
