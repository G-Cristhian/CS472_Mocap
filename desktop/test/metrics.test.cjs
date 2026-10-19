// The result panel's rows from a metrics.json (node --test, after tsc -p tsconfig.main.json).
const test = require('node:test')
const assert = require('node:assert/strict')
const { metricSections, summarise } = require('../dist/main/shared/metrics.js')

const M = {
  run: { detector: 'mediapipe', smoother: 'savgol' },
  stage1: { cam0: { frames: 100, fps_nominal: 60, no_person_fraction: 0.3, mean_confidence: 0.8 } },
  sync: { clap_time_s: { cam0: 1, cam1: 1.25 }, clap_times_from: 'given', clap_threshold: 0.5, common_frames: 90, common_fps: 30 },
  calibrate: { reused_file: 'C:\\out\\calibration.json', reprojection_error_px: { cam0: 1.5, cam1: 12.0 } },
  scale: { upright_frames: 5 },
  triangulate: { mean_reprojection_px: 2.0, mean_reprojection_px_per_joint: { NOSE: 1, LEFT_WRIST: 9, RIGHT_WRIST: 7 }, views_dropped: 2, joints_failed: 1, joints_with_fewer_than_2_views: 4 },
  pose_raw: { jitter_mm: 10, mean_views_per_joint: 2.5 },
  pose_final: { jitter_mm: 4, missing_fraction: 0.2, missing_fraction_per_joint: { LEFT_WRIST: 0.5 } },
  smooth: { method: 'savgol', settings: { window_frames: 7 }, gaps: { filled: 3, left_missing: 1 }, runs_too_short: 0 },
  rig: { bone_lengths: { mean_std_m: 0.025, per_bone: { LeftArm: { std_m: 0.03 } } } },
  timing: { total_s: 12.4, detect: { cam0_s: 7 } },
}

test('the summary keeps the comparison numbers in mm, px, % and s', () => {
  assert.deepEqual(summarise(M), {
    detector: 'mediapipe', smoother: 'savgol', clapSource: 'given',
    calibrationWorstPx: 12, reprojectionPx: 2, jitterRawMm: 10, jitterFinalMm: 4,
    boneSpreadMm: 25, missingPercent: 20, totalS: 12.4,
  })
})

test('every stage gets a section, and bad numbers are graded bad', () => {
  const sections = metricSections(M)
  assert.deepEqual(
    sections.map((s) => s.title),
    ['At a glance', 'Stage 1, detection per camera', 'Stage 2a, synchronisation', 'Stage 2b, calibration', 'Stage 2c, triangulation', 'Smoothing', 'Stage 3, skeleton'],
  )
  const rows = Object.fromEntries(sections.flatMap((s) => s.rows.map((r) => [r.label, r])))
  assert.equal(rows['Calibration error, worst camera'].value, '12.00 px')
  assert.equal(rows['Calibration error, worst camera'].grade, 'bad')
  assert.equal(rows['Joints missing'].grade, 'bad')
  assert.equal(rows['Upright frames for height'].grade, 'bad')
  assert.match(rows['cam0'].value, /nobody seen 30\.0 %.*7 s/)
  assert.equal(rows['cam0'].grade, 'bad')
  assert.match(rows['Calibration'].value, /height was not used/)
  assert.equal(rows['Clap times from'].value, 'given, threshold ×0.5')
  assert.equal(rows['Worst joints'].value, 'left_wrist 9.0 px, right_wrist 7.0 px, nose 1.0 px')
  assert.equal(rows['Jitter, raw → smoothed'].value, '10.0 → 4.0 mm/frame² (60 % less)')
  assert.equal(rows['Jitter, raw → smoothed'].grade, 'good')
  assert.equal(rows['Gaps'].value, '3 filled, 1 too long and left missing')
})

test('an empty metrics file still gives the glance section with dashes', () => {
  const sections = metricSections({})
  assert.equal(sections.length, 1)
  assert.ok(sections[0].rows.every((r) => r.value.startsWith('–')))
})
