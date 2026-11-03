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

test('videos detected at once finish in any order and the bar never goes backwards', () => {
  const { seen, last } = run([
    'Detecting joints in C:\\takes\\t1\\cam0.mp4 (mediapipe)',
    'Detecting joints in C:\\takes\\t1\\cam1.mp4 (mediapipe)',
    'Detecting 2 videos at once, 2 processes',
    'progress: detect C:\\takes\\t1\\cam1.mp4 30/120',
    'progress: detect C:\\takes\\t1\\cam0.mp4 30/120',
    'progress: detect C:\\takes\\t1\\cam1.mp4 120/120',
    'Detected joints in C:\\takes\\t1\\cam1.mp4 (41 s)',
    'progress: detect C:\\takes\\t1\\cam0.mp4 90/120',
    'Detected joints in C:\\takes\\t1\\cam0.mp4 (52 s)',
  ])
  const fractions = seen.map((p) => p.fraction)
  for (let i = 1; i < fractions.length; i++) assert.ok(fractions[i] >= fractions[i - 1], `monotonic at ${i}`)
  assert.equal(last.stage, 'detecting')
  assert.equal(last.fraction, 0.75)                                  // both cameras done, nothing after yet
  assert.match(last.detail, /Detected joints in cam0\.mp4/)
})

test('a failed video on stderr names the file', () => {
  const { t } = run(
    [
      'Detecting joints in C:\\takes\\t1\\cam0.mp4 (mediapipe)',
      'Detecting joints in C:\\takes\\t1\\cam1.mp4 (mediapipe)',
      'Detected joints in C:\\takes\\t1\\cam0.mp4 (41 s)',
      'Detection failed for C:\\takes\\t1\\cam1.mp4: ValueError: No frames could be read from video',
      'Detection failed for cam1.mp4: ValueError: No frames could be read from video: C:\\takes\\t1\\cam1.mp4',
      'Detection failed for 1 of 2 video(s): cam1.mp4. The other 1 video(s)\' joints are saved next to the output: fix or leave out the failed ones and rerun with --resume.',
    ],
    4,
  )
  const r = t.result(1)
  assert.equal(r.ok, false)
  // the whole SystemExit text: which file failed and why, then the summary with its advice (#104)
  const lines = r.error.split('\n')
  assert.equal(lines.length, 2)
  assert.match(lines[0], /^Detection failed for cam1\.mp4: ValueError/)
  assert.match(lines[1], /^Detection failed for 1 of 2 video\(s\): cam1\.mp4/)
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
  assert.match(last.detail, /^Calibration from the performer failed/)
  const r = t.result(1)
  assert.equal(r.ok, false)
  // the reason first, then the advice; the first line used to be read as progress and lost (#104)
  assert.equal(
    r.error,
    'Calibration from the performer failed (only 40 distinct joints seen by cam0 and cam1 together, need 200).\n' +
      'Record the ChArUco board with every camera and rerun with --charuco-videos cam0_board.mp4 cam1_board.mp4',
  )
})

test('a two-line clap failure keeps the camera and the reason, not only the --sync advice (#104)', () => {
  const { t } = run(
    [
      'Detected joints in C:\\takes\\t1\\cam0.mp4 (41 s)',
      'Detected joints in C:\\takes\\t1\\cam1.mp4 (40 s)',
      'C:\\takes\\t1\\cam1.mp4: no clear clap in the first 10 s. The sharpest sound is at 1.62 s: 2.9x the background (need 4.0).',
      '--sync takes one clap time per video in seconds, e.g. --sync 1.25 0.80 1.10; a video player shows the time. --clap-threshold 0.5 accepts weaker claps.',
    ],
    2,
  )
  const lines = t.result(1).error.split('\n')
  assert.equal(lines.length, 2)
  assert.match(lines[0], /cam1\.mp4: no clear clap/)
  assert.match(lines[1], /^--sync takes one clap time/)
})

test('a traceback gives its exception line; a stdout line or a new traceback starts a new message', () => {
  const { t } = run(
    [
      'Clap at cam0 1.000 s, cam1 0.850 s',
      '/venv/lib/python3.12/site-packages/cv2/x.py:12: UserWarning: something deprecated',
      '  warnings.warn(',
      'Traceback (most recent call last):',
      '  File "/backend/mocap_pipeline/run_pipeline.py", line 700, in run',
      '    scale = estimate_scale(points)',
      '            ^^^^^^^^^^^^^^^^^^^^^^',
      'ValueError: no frame shows both ears and both ankles',
    ],
    1,
  )
  assert.equal(t.result(1).error, 'ValueError: no frame shows both ears and both ankles')

  // an earlier stderr message is replaced once stdout has printed in between
  const second = run(['Clap at cam0 1.000 s, cam1 0.850 s'], 99)
  second.t.feed('old message', true)
  second.t.feed('Saved calibration to C:\\out\\calibration.json', false)
  second.t.feed('new message', true)
  assert.equal(second.t.result(1).error, 'new message')
})

test('a run stopped by the system says so instead of "exited with code null" (#124)', () => {
  const { t } = run(['Detecting joints in C:\\takes\\t1\\cam0.mp4 (mediapipe)', 'some stray warning'], 1)
  assert.equal(t.result(null, false, 'SIGKILL').error, 'The pipeline was stopped by the system (SIGKILL); it may have run out of memory.')
  // cancel still wins, and an exit code without a signal keeps the message
  assert.equal(t.result(null, true, 'SIGTERM').error, 'Cancelled')
  assert.equal(t.result(1).error, 'some stray warning')
})

test('paths holding " (" are still matched to their camera (#106)', () => {
  const videos = ['C:\\Takes (Oct)\\cam0 (1).mp4', '/takes/Take (final)/cam1.mp4']
  const t = new ProgressTracker(videos)
  t.feed('Detecting joints in C:\\Takes (Oct)\\cam0 (1).mp4 (mediapipe)')
  assert.deepEqual(t.snapshot().videos[0], { name: 'cam0 (1).mp4', state: 'detecting', detail: 'starting' })
  t.feed('Detected joints in C:\\Takes (Oct)\\cam0 (1).mp4 (41 s)')
  t.feed('Using saved joints for /takes/Take (final)/cam1.mp4 (out3d.keypoints.cam1.npz)')
  assert.deepEqual(t.snapshot().videos, [
    { name: 'cam0 (1).mp4', state: 'done', detail: '41 s' },
    { name: 'cam1.mp4', state: 'reused', detail: 'saved joints reused' },
  ])
  assert.match(t.snapshot().detail, /Reusing saved joints for cam1\.mp4/)
})

test('RTMPose with its options starts the video at once, not at frame 30 (#124)', () => {
  const { last } = run(['Detecting joints in C:\\takes\\t1\\cam0.mp4 (rtmpose, mode balanced)'])
  assert.deepEqual(last.videos[0], { name: 'cam0.mp4', state: 'detecting', detail: 'starting' })
  assert.equal(last.detail, 'Detecting joints in cam0.mp4')
})

test('an unreadable frame count (-1) still shows the frame number (#106)', () => {
  const { last } = run(['progress: detect C:\\takes\\t1\\cam0.mp4 30/-1'])
  assert.deepEqual(last.videos[0], { name: 'cam0.mp4', state: 'detecting', detail: 'frame 30' })
  assert.equal(last.detail, 'Detecting joints in cam0.mp4, frame 30')
  assert.ok(last.fraction > 0)
})

test('"Chirp at" ends the sync stage like "Clap at" (#121)', () => {
  const { last } = run(['Chirp at cam0 1.000 s, cam1 0.850 s'])
  assert.equal(last.stage, 'calibrating')
  assert.equal(last.detail, 'Synchronised: cam0 1.000 s, cam1 0.850 s')
})

test('cancel wins over the exit code', () => {
  const { t } = run(['Cameras: cam0 webcam, cam1 webcam'])
  assert.deepEqual(t.result(null, true), { ok: false, exitCode: null, error: 'Cancelled' })
})

test('unknown lines change nothing', () => {
  const { seen } = run(['Hello', 'warning: something odd'])
  assert.equal(seen.length, 0)
})

test('each video carries its own state, and a failed one stays failed', () => {
  const { t, last } = run(
    [
      'Detecting joints in C:\\takes\\t1\\cam0.mp4 (mediapipe)',
      'Detecting joints in C:\\takes\\t1\\cam1.mp4 (mediapipe)',
      'progress: detect C:\\takes\\t1\\cam0.mp4 30/120',
      'Detection failed for C:\\takes\\t1\\cam1.mp4: ValueError: No frames could be read from video',
      'progress: detect C:\\takes\\t1\\cam1.mp4 30/120',
      'Detected joints in C:\\takes\\t1\\cam0.mp4 (41 s)',
    ],
  )
  assert.deepEqual(
    last.videos,
    [
      { name: 'cam0.mp4', state: 'done', detail: '41 s' },
      { name: 'cam1.mp4', state: 'failed', detail: 'ValueError: No frames could be read from video' },
    ],
  )
  assert.equal(last.fraction, 0.75)
  // a later stage's line does not undo the failure
  t.feed('Clap at cam0 1.000 s, cam1 0.850 s')
  assert.equal(t.snapshot().videos[1].state, 'failed')
})

test('reused joints show as reused, with a waiting video still waiting', () => {
  const { last } = run(['Using saved joints for C:\\takes\\t1\\cam0.mp4 (out3d.keypoints.cam0.npz)'])
  assert.deepEqual(
    last.videos.map((v) => v.state),
    ['reused', 'waiting'],
  )
})
