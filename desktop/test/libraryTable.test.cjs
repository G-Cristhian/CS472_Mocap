// The results library's table: columns, sort, filter, colours (src/shared/library.ts).
const test = require('node:test')
const assert = require('node:assert/strict')
const { COLUMNS, DEFAULT_VIEW, detectFps, detectorText, startedText, takes, viewRows } = require('../dist/main/shared/library.js')

function row(over) {
  const summary = {
    detector: 'mediapipe', smoother: 'savgol', clapSource: 'audio',
    calibrationWorstPx: 2, reprojectionPx: 2, jitterRawMm: 15, jitterFinalMm: 6,
    boneSpreadMm: 8, missingPercent: 3, totalS: 200, ...(over.summary ?? {}),
  }
  return {
    metricsPath: '/o/out3d.metrics.json', bvhPath: '/o/out3d.bvh', folder: '/o', take: 'Take A',
    started: '2026-11-07T14:00:00-08:00', finished: null, status: 'done', detector: 'mediapipe',
    rtmposeMode: null, rtmposeDetectEvery: null, cameras: 3, resumed: false, frames: 669,
    videoFrames: 9690, detectS: 199, ...over, summary,
  }
}
const col = (key) => COLUMNS.find((c) => c.key === key)

test('the detector cell names the RTMPose settings', () => {
  assert.equal(detectorText(row({})), 'MediaPipe')
  assert.equal(detectorText(row({ detector: 'rtmpose', rtmposeMode: 'balanced', rtmposeDetectEvery: 1 })), 'RTMPose balanced')
  assert.equal(detectorText(row({ detector: 'rtmpose', rtmposeMode: 'lightweight', rtmposeDetectEvery: 5 })), 'RTMPose lightweight, every 5')
})

test('detection speed is video frames per second, and blank for a resumed run', () => {
  assert.ok(Math.abs(detectFps(row({})) - 9690 / 199) < 1e-9)
  assert.equal(detectFps(row({ resumed: true })), null)
  assert.equal(col('total').text(row({ resumed: true, summary: { totalS: 9.4 } })), '9 (resumed)')
  assert.equal(col('detect').text(row({ resumed: true })), '–')
})

test('numbers are coloured by the processing guide thresholds', () => {
  assert.equal(col('calibration').grade(row({ summary: { calibrationWorstPx: 2 } })), 'good')
  assert.equal(col('calibration').grade(row({ summary: { calibrationWorstPx: 10.6 } })), 'bad')
  assert.equal(col('missing').grade(row({ summary: { missingPercent: 6.4 } })), 'mid')
  assert.equal(col('bones').grade(row({ summary: { boneSpreadMm: 25.4 } })), 'bad')
})

test('filter by take and status; sort any column, blanks last both ways', () => {
  const runs = [
    row({ take: 'Take B', started: '2026-11-07T10:00:00-08:00', summary: { totalS: 540 } }),
    row({ take: 'Take A', started: '2026-11-07T12:00:00-08:00', summary: { totalS: null }, status: 'failed' }),
    row({ take: 'Take A', started: '2026-11-07T11:00:00-08:00', summary: { totalS: 197 } }),
  ]
  assert.deepEqual(takes(runs), ['Take A', 'Take B'])
  assert.deepEqual(viewRows(runs, DEFAULT_VIEW).map((r) => r.started.slice(11, 13)), ['12', '11', '10'])
  assert.deepEqual(viewRows(runs, { ...DEFAULT_VIEW, take: 'Take A' }).length, 2)
  assert.deepEqual(viewRows(runs, { ...DEFAULT_VIEW, doneOnly: true }).length, 2)
  const asc = viewRows(runs, { ...DEFAULT_VIEW, sortKey: 'total', descending: false })
  assert.deepEqual(asc.map((r) => r.summary.totalS), [197, 540, null])
  const desc = viewRows(runs, { ...DEFAULT_VIEW, sortKey: 'total', descending: true })
  assert.deepEqual(desc.map((r) => r.summary.totalS), [540, 197, null])
})

test('the start time shows as the clock the pipeline wrote', () => {
  assert.equal(startedText('2026-11-07T14:25:17-08:00'), '2026-11-07 14:25')
  assert.equal(startedText(null), '–')
})
