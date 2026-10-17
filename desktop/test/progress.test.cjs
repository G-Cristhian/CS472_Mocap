// The progress tracker against the lines a real run prints (node --test, after tsc -p tsconfig.main.json).
const test = require('node:test')
const assert = require('node:assert/strict')
const { ProgressTracker } = require('../dist/main/shared/progress.js')

const VIDEOS = ['C:\\takes\\t1\\cam0.mp4', 'C:\\takes\\t1\\cam1.mp4']

function run(lines, stderrFrom = Infinity) {
  const t = new ProgressTracker(VIDEOS)
  const seen = []
  lines.forEach((l, i) => {
    const p = t.feed(l, i >= stderrFrom)
    if (p) seen.push(p)
  })
  return { t, seen, last: seen[seen.length - 1] }
}

test('a full run climbs to 1 and reports done with the file paths', () => {
  const { t, seen, last } = run([
    'Cameras: cam0 webcam, cam1 webcam',
    'Detecting joints in C:\\takes\\t1\\cam0.mp4 (mediapipe)',
    'progress: detect C:\\takes\\t1\\cam0.mp4 30/120',
    'progress: detect C:\\takes\\t1\\cam0.mp4 60/120',
    'Detecting joints in C:\\takes\\t1\\cam1.mp4 (mediapipe)',
    'progress: detect C:\\takes\\t1\\cam1.mp4 120/120',
    'Clap at cam0 1.000 s, cam1 0.850 s',
    'Calibration started from cam0 and cam1',
    'Calibration from the performer: cam0 1.44 px, cam1 1.33 px',
    'Scale: 6.8342 m per unit, floor found, Y up',
    'Saved calibration to C:\\out\\calibration.json',
    'Saved 360 frames of 3D joints to C:\\out\\out3d.json',
    'Saved skeleton animation to C:\\out\\out3d.bvh',
    'Saved metrics to C:\\out\\out3d.metrics.json',
  ])
  const fractions = seen.map((p) => p.fraction)
  for (let i = 1; i < fractions.length; i++) assert.ok(fractions[i] >= fractions[i - 1], `monotonic at ${i}`)
  assert.equal(seen[1].stage, "detecting")
  assert.match(seen[1].detail, /cam0\.mp4, frame 30 of 120/)
  assert.ok(Math.abs(seen[1].fraction - 0.75 * 0.125) < 1e-9)       // a quarter of one of two cameras
  assert.equal(last.stage, 'done')
  assert.equal(last.fraction, 1)
  const r = t.result(0)
  assert.equal(r.ok, true)
  assert.equal(r.bvhPath, 'C:\\out\\out3d.bvh')
  assert.equal(r.jsonPath, 'C:\\out\\out3d.json')
  assert.equal(r.metricsPath, 'C:\\out\\out3d.metrics.json')
})

test('resume lines count a camera as finished', () => {
  const { last } = run([
    'Using saved joints for C:\\takes\\t1\\cam0.mp4 (out3d.keypoints.cam0.npz)',
    'Using saved joints for C:\\takes\\t1\\cam1.mp4 (out3d.keypoints.cam1.npz)',
  ])
  assert.equal(last.fraction, 0.75)
  assert.match(last.detail, /Reusing saved joints/)
})

test('a SystemExit message on stderr becomes the error', () => {
  const { t, last } = run(
    [
      'Detecting joints in C:\\takes\\t1\\cam0.mp4 (mediapipe)',
      'Clap at cam0 1.000 s, cam1 0.850 s',
      'Calibration from the performer failed (only 40 distinct joints seen by cam0 and cam1 together, need 200).',
      'Record the ChArUco board with every camera and rerun with --charuco-videos cam0_board.mp4 cam1_board.mp4',
    ],
    2,
  )
  assert.equal(last.stage, 'calibrating')
  const r = t.result(1)
  assert.equal(r.ok, false)
  assert.match(r.error, /charuco-videos/)
})

test('cancel wins over the exit code', () => {
  const { t } = run(['Cameras: cam0 webcam, cam1 webcam'])
  assert.deepEqual(t.result(null, true), { ok: false, exitCode: null, error: 'Cancelled' })
})

test('unknown lines change nothing', () => {
  const { seen } = run(['Hello', 'warning: something odd'])
  assert.equal(seen.length, 0)
})
