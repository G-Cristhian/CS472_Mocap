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
    version: 3, fps: 30, times: [0, 1 / 30, 2 / 30, 3 / 30], joints: ['NOSE', 'RIGHT_WRIST'],
    thresholds: { min_confidence: 0.5, max_reprojection_px: 15 },
    cameras: [cam('cam0', -2), cam('cam1', -1.8), cam('cam2', 2)],
    performer_centre: [0, 1, 0],
    per_camera: [pc('cam0', 0, false), pc('cam1', 0, false), pc('cam2', 12, true)],
    joint_views: [[3, 3], [3, 0], [3, 0], [3, 2]],
    joint_error_px: [[1, 2], [1, null], [1, null], [1, 12]],
    joint_error_mm: [[30, 60], [30, null], [30, null], [30, 360]],
    joint_speed: [[0, 1], [0, 1], [0, 1], [0, 1]],
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

/**
 * 60 frames, 3 cameras, joints NOSE, LEFT_WRIST, RIGHT_WRIST, RIGHT_KNEE. trouble(f, j) says what
 * happens: 'lost' (no 3D point, cam2 did not see it), 'off' (cameras 14 px apart, cam1 furthest off)
 * or nothing. The left wrist moves at 3 m/s in frames 20 to 24 (8 % of the take), 0.2 m/s otherwise.
 */
function scripted(trouble) {
  const n = 60
  const joints = ['NOSE', 'LEFT_WRIST', 'RIGHT_WRIST', 'RIGHT_KNEE']
  const frames = [...Array(n).keys()]
  const per = (id, k) => ({
    id, error_px: frames.map(() => 2), error_mm: frames.map(() => 4), seen: frames.map(() => 4),
    mean_error_px: 2, mean_error_mm: 4, lost_fraction: 0,
    points: frames.map((f) => joints.map((_, j) => {
      const t = trouble(f, j)
      if (t === 'lost' && id === 'cam2') return [null, null]
      return [100 + (t === 'off' && id === 'cam1' ? 20 : 0), 100]
    })),
    reprojected: frames.map(() => joints.map(() => [100, 100])),
  })
  const cam = (id, x) => ({ id, width: 200, height: 200, position: [x, 1, 3], forward: [0, 0, -1], up: [0, 1, 0], focal_px: 100, centre_px: [100, 100], calibration_error_px: 2, distance_m: 3, mm_per_px: 2 })
  return {
    version: 3, fps: 30, times: frames.map((f) => f / 30), joints,
    thresholds: { min_confidence: 0.5, max_reprojection_px: 15 },
    cameras: [cam('cam0', -2), cam('cam1', 0), cam('cam2', 2)],
    performer_centre: [0, 1, 0],
    per_camera: [per('cam0'), per('cam1'), per('cam2')],
    joint_views: frames.map((f) => joints.map((_, j) => (trouble(f, j) === 'lost' ? 0 : 3))),
    joint_error_px: frames.map((f) => joints.map((_, j) => (trouble(f, j) === 'lost' ? null : trouble(f, j) === 'off' ? 14 : 2))),
    joint_error_mm: frames.map((f) => joints.map((_, j) => (trouble(f, j) === 'lost' ? null : 4))),
    joint_speed: frames.map((f) => joints.map((_, j) => (j === 1 && f >= 20 && f <= 24 ? 3 : 0.2))),
  }
}

test('flags: joints in trouble over the same stretch make one flag, with the camera to blame', () => {
  const r = scripted((f, j) => {
    if (j === 1 && f >= 20 && f <= 27) return 'lost'
    if (j === 2 && f >= 21 && f <= 28) return 'off'
    if (j === 3 && (f === 50 || f === 51)) return 'lost'       // 2 frames: too short to flag
    return null
  })
  const flags = R.findFlags(r)
  assert.equal(flags.length, 1)
  const [flag] = flags
  assert.equal(flag.kind, 'both')
  assert.deepEqual([flag.startFrame, flag.endFrame], [20, 28])
  assert.deepEqual(flag.joints.map((j) => j.joint).sort(), ['LEFT_WRIST', 'RIGHT_WRIST'])
  const wrist = flag.joints.find((j) => j.joint === 'LEFT_WRIST')
  assert.equal(wrist.lostFrames, 8)
  assert.deepEqual([wrist.camera.id, wrist.camera.why], ['cam2', 'missed'])
  const right = flag.joints.find((j) => j.joint === 'RIGHT_WRIST')
  assert.equal(right.spikeFrames, 8)
  assert.deepEqual([right.camera.id, right.camera.why], ['cam1', 'off'])
  assert.equal(R.isMajor(flag), true)
  assert.match(R.flagTitle(flag, r), /^0\.7–1\.0 s \(0\.3 s\): .*lost, and cameras far apart$/)
  const text = R.flagDetails(flag).join(' ')
  assert.match(text, /left wrist: no 3D position in 8 of 9 frames, cam2 did not see it in 8; it was moving fast \(3\.0 m\/s/)
  assert.match(text, /right wrist: cameras up to 14 px apart in 8, cam1 furthest off \(18 px, so triangulation mostly left its view out\); it was not moving unusually fast/)
})

test('flags: a gap of a few frames does not split a stretch, a longer one does', () => {
  const r = scripted((f, j) => (j === 0 && ((f >= 5 && f <= 9) || (f >= 12 && f <= 16) || (f >= 30 && f <= 34)) ? 'lost' : null))
  const flags = R.findFlags(r)
  assert.deepEqual(flags.map((f) => [f.startFrame, f.endFrame]), [[5, 16], [30, 34]])
  assert.equal(R.isMajor(flags[1]), false)
})

test('flags: a joint lost all take does not swallow a short problem elsewhere', () => {
  const r = scripted((f, j) => (j === 3 ? 'lost' : j === 1 && f >= 40 && f <= 45 ? 'off' : null))
  const flags = R.findFlags(r)
  assert.equal(flags.length, 2)
  assert.deepEqual(flags.map((f) => f.joints.map((j) => j.joint)), [['RIGHT_KNEE'], ['LEFT_WRIST']])
})

test('flags: a joint every camera saw but could not be placed blames the camera furthest off', () => {
  const r = scripted((f, j) => (j === 0 && f >= 10 && f <= 14 ? 'lost' : null))
  // every camera reports the nose, cam1 20 px off: triangulation rejected it
  for (const f of [10, 11, 12, 13, 14]) {
    r.per_camera[2].points[f][0] = [100, 100]
    r.per_camera[1].points[f][0] = [120, 100]
  }
  const [flag] = R.findFlags(r)
  assert.equal(flag.joints[0].camera.why, 'off')
  assert.match(R.flagDetails(flag)[0], /the cameras saw it but disagreed too much to place it, cam1 furthest off \(20 px, so triangulation mostly left its view out\)/)
})
