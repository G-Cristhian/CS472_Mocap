// The comparison matrix and its folders (src/shared/queue.ts; node --test, after tsc -p tsconfig.main.json).
const test = require('node:test')
const assert = require('node:assert/strict')
const { detectionName, expandMatrix, parseDetectEvery, settingsLabel } = require('../dist/main/shared/queue.js')

const BASE = {
  videos: ['/t/cam0.mov', '/t/cam1.mov'],
  heightM: 1.7,
  outDir: '/out/take-20261107-1400',
  detector: 'mediapipe',
  smoother: 'savgol',
  fov: 65,
  clapThreshold: 1,
  clapTimes: null,
  jobs: 0,
  recalibrate: true,
  resume: false,
}
const BASE_DIR = '/out/take-20261107-1400'

test('detect-every values: commas or spaces, repeats dropped, nonsense refused', () => {
  assert.deepEqual(parseDetectEvery('1, 5'), [1, 5])
  assert.deepEqual(parseDetectEvery(' 5 1 5 '), [5, 1])
  assert.match(parseDetectEvery(''), /at least one/)
  assert.match(parseDetectEvery('1, 0'), /"0"/)
  assert.match(parseDetectEvery('2.5'), /"2.5"/)
  assert.match(parseDetectEvery('101'), /"101"/)
})

test('MediaPipe x two smoothers: one folder, the second smoother resumes in it', () => {
  const runs = expandMatrix(BASE, { detectors: ['mediapipe'], smoothers: ['savgol', 'butterworth'], rtmposeModes: [], rtmposeDetectEvery: [] }, BASE_DIR)
  assert.equal(runs.length, 2)
  assert.deepEqual(runs.map((r) => r.outDir), [`${BASE_DIR}-mediapipe`, `${BASE_DIR}-mediapipe`])
  assert.deepEqual(runs.map((r) => [r.smoother, r.resume, r.recalibrate]), [['savgol', false, true], ['butterworth', true, false]])
  assert.equal(runs[0].rtmposeMode, undefined) // RTMPose options never reach a MediaPipe run
})

test('RTMPose modes x detect-every each get a folder; MediaPipe needs no RTMPose ticks', () => {
  const runs = expandMatrix(
    { ...BASE, rtmposeMode: 'performance', rtmposeDetectEvery: 9 },
    { detectors: ['mediapipe', 'rtmpose'], smoothers: ['savgol'], rtmposeModes: ['lightweight', 'balanced'], rtmposeDetectEvery: [1, 5] },
    BASE_DIR,
  )
  assert.deepEqual(runs.map((r) => r.outDir.slice(BASE_DIR.length + 1)), [
    'mediapipe',
    'rtmpose-lightweight-every1',
    'rtmpose-lightweight-every5',
    'rtmpose-balanced-every1',
    'rtmpose-balanced-every5',
  ])
  assert.deepEqual([runs[4].rtmposeMode, runs[4].rtmposeDetectEvery], ['balanced', 5])
  assert.equal(runs[0].rtmposeMode, undefined) // the form's RTMPose settings do not leak into MediaPipe
  assert.ok(runs.every((r) => r.resume === false && r.recalibrate === true))
})

test('empty ticks are refused with a reason', () => {
  const m = { detectors: ['rtmpose'], smoothers: ['savgol'], rtmposeModes: ['balanced'], rtmposeDetectEvery: [1] }
  assert.match(expandMatrix(BASE, { ...m, detectors: [] }, BASE_DIR), /detector/)
  assert.match(expandMatrix(BASE, { ...m, smoothers: [] }, BASE_DIR), /smoother/)
  assert.match(expandMatrix(BASE, { ...m, rtmposeModes: [] }, BASE_DIR), /RTMPose mode/)
  assert.match(expandMatrix(BASE, { ...m, rtmposeDetectEvery: [] }, BASE_DIR), /detect-every/)
  assert.equal(expandMatrix(BASE, { ...m, detectors: ['mediapipe'], rtmposeModes: [] }, BASE_DIR).length, 1)
})

test('a second batch of the same take moves to -2 instead of sharing folders', () => {
  const m = { detectors: ['mediapipe', 'rtmpose'], smoothers: ['savgol', 'butterworth'], rtmposeModes: ['balanced'], rtmposeDetectEvery: [1] }
  const first = expandMatrix(BASE, m, BASE_DIR)
  const second = expandMatrix(BASE, m, BASE_DIR, new Set(first.map((r) => r.outDir)))
  assert.deepEqual([...new Set(second.map((r) => r.outDir))], [`${BASE_DIR}-2-mediapipe`, `${BASE_DIR}-2-rtmpose-balanced-every1`])
})

test('names and labels', () => {
  assert.equal(detectionName({ detector: 'mediapipe' }), 'mediapipe')
  assert.equal(detectionName({ detector: 'rtmpose' }), 'rtmpose-balanced-every1')
  assert.equal(settingsLabel({ detector: 'rtmpose', rtmposeMode: 'lightweight', rtmposeDetectEvery: 5, smoother: 'butterworth' }),
    'RTMPose lightweight, detector every 5, Butterworth')
  assert.equal(settingsLabel({ detector: 'mediapipe', smoother: 'savgol' }), 'MediaPipe, Savitzky-Golay')
})
