// The frame-by-frame report's stories, key, colours and timelines (src/shared/report.ts),
// against the synthetic run in test/fixtures and a small hand-made report.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const R = require('../dist/main/shared/report.js')

const fixture = R.parseReport(fs.readFileSync(path.join(__dirname, 'fixtures', 'synthetic.report.json'), 'utf8'))

/** 3 cameras, 2 joints, 4 frames; cam2 puts the right wrist 12 px off and misses it in frame 2. */
function tiny() {
  const P = (x, y) => [x, y]
  const N = [null, null]
  const cam = (id, x) => ({
    id, width: 100, height: 200, position: [x, 1, 3], forward: [0, 0, -1], up: [0, 1, 0], focal_px: 100,
    centre_px: [50, 100], calibration_error_px: id === 'cam2' ? 6 : 2, distance_m: 3, mm_per_px: 30,
  })
  const pc = (id, off, miss) => ({
    id, error_px: [1, 1, 1, 1], error_mm: [30, 30, 30, 30], seen: [2, 2, miss ? 1 : 2, 2],
    mean_error_px: off ? 6 : 1, mean_error_mm: off ? 180 : 30, lost_fraction: 0,
    points: [0, 1, 2, 3].map((f) => [P(10, 10), miss && f === 2 ? N : P(20 + off, 20)]),
    reprojected: [0, 1, 2, 3].map(() => [P(10, 10), P(20, 20)]),
  })
  return {
    version: 2, fps: 30, times: [0, 1 / 30, 2 / 30, 3 / 30], joints: ['NOSE', 'RIGHT_WRIST'],
    thresholds: { min_confidence: 0.5, max_reprojection_px: 15 },
    cameras: [cam('cam0', -2), cam('cam1', -1.8), cam('cam2', 2)],
    performer_centre: [0, 1, 0],
    per_camera: [pc('cam0', 0, false), pc('cam1', 0, false), pc('cam2', 12, true)],
    joint_views: [[3, 3], [3, 0], [3, 0], [3, 2]],
    joint_error_px: [[1, 2], [1, null], [1, null], [1, 12]],
    joint_error_mm: [[30, 60], [30, null], [30, null], [30, 360]],
  }
}

test('frames follow the 30 fps clock and stay inside the take', () => {
  assert.equal(R.frameAt(fixture, 0), 0)
  assert.equal(R.frameAt(fixture, 1), 30)
  assert.equal(R.frameAt(fixture, 1e6), fixture.times.length - 1)
})

test('a report from another version is refused', () => {
  assert.throws(() => R.parseReport(JSON.stringify({ version: 99 })), /version 99/)
})

test('joint colours: error grades, cameras seen, and no 3D point', () => {
  const r = tiny()
  assert.equal(R.jointState(r, 0, 0, 'error'), 'good')
  assert.equal(R.jointState(r, 1, 1, 'error'), 'none')
  assert.equal(R.jointState(r, 3, 1, 'error'), 'bad')
  assert.equal(R.jointState(r, 3, 1, 'views'), 'mid')
  assert.equal(R.jointState(r, 0, 1, 'views'), 'good')
  // a BVH joint takes the worst of the joints it is built from; Neck's shoulders and ears are not tracked here
  assert.equal(R.rigState(r, 3, 'RightWrist', 'error'), 'bad')
  assert.equal(R.rigState(r, 3, 'Neck', 'error'), null)
  assert.equal(R.rigState(r, 3, 'RightWrist', 'plain'), null)
})

test('the key carries the scale, in pixels and millimetres', () => {
  const key = R.colourKey('error', tiny())
  assert.deepEqual(key.map((k) => k.state), ['good', 'mid', 'bad', 'none'])
  assert.equal(key[0].label, 'cameras agree within 3 px (about 90 mm)')
  assert.equal(key[2].label, '10 px or more (about 300 mm)')
  assert.equal(R.colourKey('views', tiny())[0].label, 'seen by all 3 cameras')
  assert.equal(R.colourKey('views', tiny())[1].label, 'seen by 2 cameras')
  assert.deepEqual(R.colourKey('plain', tiny()), [])
})

test('the worst camera is named, with millimetres, its worst joint and the narrow pair', () => {
  const r = tiny()
  const lines = R.cameraLines(r)
  assert.equal(lines[0].id, 'cam2')
  assert.equal(lines[0].worstJoints[0].joint, 'RIGHT_WRIST')
  const story = R.cameraStory(r).join(' ')
  assert.match(story, /^cam2 is the worst camera: .* 6\.0 px \(about 180 mm at the performer\)/)
  assert.match(story, /right wrist \(12 px\)/)
  assert.match(story, /calibration error is 6\.0 px \(about 180 mm\)/)
  // cam0 and cam1 stand 0.2 m apart, 3 m away: a few degrees
  assert.match(story, /cam0 and cam1 look at the performer from nearly the same direction \(\d° apart\)/)
})

test('joint stories: how often lost, the longest stretch, who missed it, how far apart', () => {
  const r = tiny()
  const lines = R.jointLines(r)
  assert.equal(lines[0].joint, 'RIGHT_WRIST')
  assert.equal(lines[0].lostFrames, 2)
  assert.equal(lines[0].longestGap.frames, 2)
  assert.equal(lines[0].missedBy[0].camera, 'cam2')
  const story = R.jointStory(lines[0], 4)
  assert.match(story, /^Right wrist had no 3D position in 50 % of frames \(2 of 4\), the longest stretch 0\.1 s from 0\.0 s to 0\.1 s\./)
  assert.match(story, /cam2 did not see it confidently in 25 %/)
  assert.match(story, /disagreed by 7\.0 px \(about 210 mm\), cam2 most \(12 px\)/)
  assert.match(R.jointStory(lines[1], 4), /^Nose had a 3D position in every frame\./)
  assert.match(R.bodyStory(lines), /^The right arm was the hardest to track .*the head the easiest/)
})

test('the synthetic run: three cameras, every story and series fills in', () => {
  assert.equal(fixture.cameras.length, 3)
  assert.equal(R.lostPerFrame(fixture).length, fixture.times.length)
  assert.ok(R.cameraStory(fixture).length >= 2)
  assert.equal(R.jointLines(fixture).length, fixture.joints.length)
  assert.ok(R.wireIndices(fixture).length > 20)
  const mm = R.mmScale(fixture)
  assert.ok(mm.median > 1 && mm.median < 5)
})
