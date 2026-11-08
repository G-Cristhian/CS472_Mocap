/**
 * Turns <out>.metrics.json (backend/mocap_pipeline/metrics.py) into the rows the
 * result panel shows: where the error comes from, camera by camera and joint
 * by joint, and what smoothing did to it. Pure, so it is tested on its own.
 */

/** green, amber (between the two limits), red; '' when there is no number or no limit */
export type Grade = 'good' | 'mid' | 'bad' | ''

export interface MetricRow {
  label: string
  value: string
  grade: Grade
  /** the limits behind the colour, for the key: "green ≤ 3 px, red ≥ 10 px" */
  scale?: string
}

/** The processing guide's limits (processing-a-take.md step 4), shared by every panel that colours a number. */
export const LIMITS = {
  px: { good: 3, bad: 10 },
  boneMm: { good: 10, bad: 20 },
  missingPercent: { good: 5, bad: 15 },
  upright: { good: 30, bad: 10 },
} as const

/** Millimetres per pixel at the performer, from the run's report (report.ts): per camera, and their median. */
export interface MmScale {
  perCamera: Record<string, number>
  median: number | null
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

/** green at or past `good`, red at or past `bad`; the thresholds are processing-a-take.md step 4 */
export function grade(value: number | null, good: number, bad: number): Grade {
  if (value === null) return ''
  if (good < bad) return value <= good ? 'good' : value >= bad ? 'bad' : 'mid'
  return value >= good ? 'good' : value <= bad ? 'bad' : 'mid'
}

const dash = '–'
const fix = (v: number | null, digits: number, unit = '') => (v === null ? dash : `${v.toFixed(digits)}${unit}`)

/** "5.27 px (about 8 mm)": a pixel error and what it is at the performer, when the scale is known. */
export function pxWithMm(px: number | null, mmPerPx: number | null | undefined, digits = 2): string {
  if (px === null) return dash
  return mmPerPx ? `${px.toFixed(digits)} px (about ${(px * mmPerPx).toFixed(0)} mm)` : `${px.toFixed(digits)} px`
}

const pxScale = `green ≤ ${LIMITS.px.good} px, red ≥ ${LIMITS.px.bad} px`

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

export function metricSections(m: Json, mm?: MmScale): MetricSection[] {
  const s = summarise(m)
  const worstCam = Object.entries(numbers(m, 'calibrate.reprojection_error_px')).sort((a, b) => b[1] - a[1])[0]?.[0]
  const sections: MetricSection[] = []

  // ---- the headline, the five numbers the old panel showed ----
  const upright = num(m, 'scale.upright_frames')
  sections.push({
    title: 'At a glance',
    rows: [
      {
        label: 'Calibration error, worst camera' + (worstCam ? ` (${worstCam})` : ''),
        value: pxWithMm(s.calibrationWorstPx, worstCam ? mm?.perCamera[worstCam] : null),
        grade: grade(s.calibrationWorstPx, LIMITS.px.good, LIMITS.px.bad),
        scale: pxScale,
      },
      {
        label: 'Triangulation error, mean',
        value: pxWithMm(s.reprojectionPx, mm?.median),
        grade: grade(s.reprojectionPx, LIMITS.px.good, LIMITS.px.bad),
        scale: pxScale,
      },
      {
        label: 'Bone length spread',
        value: fix(s.boneSpreadMm, 1, ' mm'),
        grade: grade(s.boneSpreadMm, LIMITS.boneMm.good, LIMITS.boneMm.bad),
        scale: `green ≤ ${LIMITS.boneMm.good} mm, red ≥ ${LIMITS.boneMm.bad} mm`,
      },
      {
        label: 'Joints missing',
        value: fix(s.missingPercent, 1, ' %'),
        grade: grade(s.missingPercent, LIMITS.missingPercent.good, LIMITS.missingPercent.bad),
        scale: `green ≤ ${LIMITS.missingPercent.good} %, red ≥ ${LIMITS.missingPercent.bad} %`,
      },
      {
        label: 'Upright frames for height',
        value: upright === null ? dash : String(upright),
        grade: grade(upright, LIMITS.upright.good, LIMITS.upright.bad),
        scale: `green ≥ ${LIMITS.upright.good}, red ≤ ${LIMITS.upright.bad}`,
      },
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
        grade: nobody === null ? '' : nobody > 20 ? 'bad' : nobody < 5 ? 'good' : 'mid',
        scale: 'nobody seen: green under 5 %, red over 20 %',
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
    for (const [cid, px] of Object.entries(calib)) {
      rows.push({ label: `${cid} calibration error`, value: pxWithMm(px, mm?.perCamera[cid]), grade: grade(px, LIMITS.px.good, LIMITS.px.bad), scale: pxScale })
    }
    const scale = num(m, 'scale.metres_per_unit')
    if (scale !== null) {
      rows.push({
        label: 'Scale',
        value: `${scale.toFixed(4)} m per unit${at(m, 'scale.rescaled_from_height') ? ', from the performer height' : ''}`,
        grade: '',
      })
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
        { label: 'Mean reprojection error', value: pxWithMm(s.reprojectionPx, mm?.median), grade: grade(s.reprojectionPx, LIMITS.px.good, LIMITS.px.bad), scale: pxScale },
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
          grade: reduction === null ? '' : reduction > 40 ? 'good' : reduction < 10 ? 'bad' : 'mid',
          scale: 'green over 40 % less, red under 10 % less',
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
        { label: 'Bone length spread, mean', value: fix(s.boneSpreadMm, 1, ' mm'), grade: grade(s.boneSpreadMm, LIMITS.boneMm.good, LIMITS.boneMm.bad), scale: `green ≤ ${LIMITS.boneMm.good} mm, red ≥ ${LIMITS.boneMm.bad} mm` },
        { label: 'Least rigid bones', value: worst(spread, 4, 1, ' mm'), grade: '' },
      ],
    })
  }

  return sections
}
