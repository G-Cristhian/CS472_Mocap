// The results library: snapshots of each run and the scan of the output folders (src/main/library.ts).
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { listRuns, snapshotName, snapshotRun } = require('../dist/main/main/library.js')

function withTempDir(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'library-'))
  return Promise.resolve(fn(dir)).finally(() => fs.rmSync(dir, { recursive: true, force: true }))
}

function metrics({ started, detector = 'mediapipe', smoother = 'savgol', options = null, resume = false, totalS = 200 }) {
  return {
    run: {
      started,
      finished: started,
      status: 'done',
      videos: ['C:\\takes\\Live Video Recordings 2\\IMG_1.MOV', 'C:\\takes\\Live Video Recordings 2\\IMG_2.MOV'],
      detector,
      detector_options: options,
      smoother,
      resume,
    },
    stage1: { IMG_1: { frames: 3221 }, IMG_2: { frames: 3242 } },
    calibrate: { reprojection_error_px: { IMG_1: 2.5, IMG_2: 7.7 } },
    triangulate: { mean_reprojection_px: 4.98 },
    pose_final: { frames: 669, missing_fraction: 0.064, jitter_mm: 6.2 },
    rig: { bone_lengths: { mean_std_m: 0.0254 } },
    timing: { detect_total_s: totalS - 12, total_s: totalS },
  }
}

function writeRun(folder, m) {
  fs.mkdirSync(folder, { recursive: true })
  fs.writeFileSync(path.join(folder, 'out3d.metrics.json'), JSON.stringify(m))
  fs.writeFileSync(path.join(folder, 'out3d.bvh'), `HIERARCHY ${m.run.started}`)
}

test('snapshot names sort by time and are safe as folder names', () => {
  assert.equal(snapshotName('2026-11-07T14:25:17-08:00'), '20261107-142517')
  assert.equal(snapshotName('weird:value'), 'weird_value')
})

test('a rerun into the same folder no longer erases the first run', () =>
  withTempDir(async (root) => {
    const folder = path.join(root, 'output', 'take-20261107-1410')
    writeRun(folder, metrics({ started: '2026-11-07T14:10:35-08:00', detector: 'rtmpose', options: { mode: 'balanced', detect_every: 5 }, totalS: 560 }))
    await snapshotRun(folder)
    writeRun(folder, metrics({ started: '2026-11-07T14:25:17-08:00', smoother: 'butterworth', resume: true, totalS: 9 }))
    await snapshotRun(folder)

    const runs = await listRuns([path.join(root, 'output')])
    assert.equal(runs.length, 2) // the live files and the newest snapshot are one run, not two
    const [newer, older] = runs
    assert.equal(newer.started, '2026-11-07T14:25:17-08:00')
    assert.equal(newer.resumed, true)
    assert.equal(older.detector, 'rtmpose')
    assert.deepEqual([older.rtmposeMode, older.rtmposeDetectEvery], ['balanced', 5])
    assert.equal(older.summary.totalS, 560)
    // each row's skeleton is its own run's, from its snapshot
    assert.equal(fs.readFileSync(older.bvhPath, 'utf8'), 'HIERARCHY 2026-11-07T14:10:35-08:00')
    assert.ok(older.bvhPath.includes(path.join('runs', '20261107-141035')))
  }))

test('rows carry the take, the accuracy and the times', () =>
  withTempDir(async (root) => {
    writeRun(path.join(root, 'output', 'a'), metrics({ started: '2026-11-06T22:54:00-08:00' }))
    const [run] = await listRuns([path.join(root, 'output')])
    assert.equal(run.take, 'Live Video Recordings 2')
    assert.equal(run.cameras, 2)
    assert.equal(run.frames, 669)
    assert.equal(run.videoFrames, 3221 + 3242)
    assert.equal(run.detectS, 188)
    assert.equal(run.summary.calibrationWorstPx, 7.7)
    assert.equal(run.summary.reprojectionPx, 4.98)
    assert.ok(Math.abs(run.summary.boneSpreadMm - 25.4) < 1e-9)
    assert.ok(Math.abs(run.summary.missingPercent - 6.4) < 1e-9)
    assert.equal(run.detector, 'mediapipe')
    assert.equal(run.rtmposeMode, null)
  }))

test('folders outside backend/output are listed when named; junk and missing folders are skipped', () =>
  withTempDir(async (root) => {
    const elsewhere = path.join(root, 'chosen by hand')
    writeRun(elsewhere, metrics({ started: '2026-11-07T09:00:00-08:00' }))
    fs.mkdirSync(path.join(root, 'output', 'broken'), { recursive: true })
    fs.writeFileSync(path.join(root, 'output', 'broken', 'out3d.metrics.json'), '{ not json')
    fs.mkdirSync(path.join(root, 'output', 'empty'))
    const runs = await listRuns([path.join(root, 'output'), path.join(root, 'missing')], [elsewhere])
    assert.deepEqual(runs.map((r) => r.folder), [path.resolve(elsewhere)])
  }))

test('a run with no metrics leaves no snapshot', () =>
  withTempDir(async (root) => {
    assert.deepEqual(await snapshotRun(root), [])
    assert.ok(!fs.existsSync(path.join(root, 'runs')))
  }))
