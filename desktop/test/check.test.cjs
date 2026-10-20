// parseCheckOutput against what check_videos.py prints (node --test, after tsc -p tsconfig.main.json).
const test = require('node:test')
const assert = require('node:assert/strict')
const { parseCheckOutput } = require('../dist/main/shared/check.js')

const OUTPUT = `
cam0.MOV
  video   1920x1080, 59.94 fps, 1800 frames, 30.0 s
  lens    iPhone 16 Pro, Back Camera, 24 mm (35 mm equiv.) from metadata
  clap    1.196 s

cam1.mp4
  video   1280x720, 30.00 fps, 900 frames, 30.0 s
  WARNING frame rate under 50; the protocol asks for 60 (or 120 for set C)
  lens    no lens metadata (not an iPhone file): needs --fov, default 65
  FAIL    no clap: cam1.mp4: no clear clap in the first 10 s. The sharpest sound is at 1.62 s: 2.9x the background (need 4.0), 2.4x louder than just before it (need 2.0), reaching its peak in 12 ms (at most 25). If that is the clap, rerun with --clap-threshold 0.5; otherwise give the clap times with --sync.

across cameras
  WARNING frame rates differ between phones: [30, 60] (fine for the pipeline, but a take set should be recorded at one rate)

1 file(s) the pipeline cannot use.
`

test('one record per file with its facts, warnings and failures', () => {
  const r = parseCheckOutput(OUTPUT, 1)
  assert.equal(r.ok, false)
  assert.equal(r.videos.length, 2)
  assert.equal(r.videos[0].name, 'cam0.MOV')
  assert.equal(r.videos[0].video, '1920x1080, 59.94 fps, 1800 frames, 30.0 s')
  assert.match(r.videos[0].lens, /iPhone 16 Pro/)
  assert.equal(r.videos[0].clapS, 1.196)
  assert.deepEqual(r.videos[0].warnings, [])
  assert.equal(r.videos[1].clapS, undefined)
  assert.equal(r.videos[1].warnings.length, 1)
  assert.match(r.videos[1].failures[0], /^no clap: cam1\.mp4: no clear clap/)
  assert.equal(r.across.length, 1)
  assert.match(r.across[0], /^frame rates differ/)
})

test('a clean take is ok, with the cross-checked clap times', () => {
  const r = parseCheckOutput(
    'a.MOV\n  video   1920x1080, 60.00 fps, 600 frames, 10.0 s\n  clap    1.000 s\n\nb.MOV\n  video   1920x1080, 60.00 fps, 600 frames, 10.0 s\n  clap    0.900 s\n\nacross cameras\n  claps   a.MOV 1.000 s, b.MOV 0.903 s (cross-checked against camera 0)\n\nAll files usable.\n',
    0,
  )
  assert.equal(r.ok, true)
  assert.deepEqual(r.videos.map((v) => v.clapS), [1.0, 0.9])
  assert.deepEqual(r.across, ['claps a.MOV 1.000 s, b.MOV 0.903 s (cross-checked against camera 0)'])
})

test('a file that cannot be opened has a failure and no facts', () => {
  const r = parseCheckOutput('x.mp4\n  FAIL    cannot be opened as a video\n\n1 file(s) the pipeline cannot use.\n', 1)
  assert.equal(r.videos[0].video, undefined)
  assert.deepEqual(r.videos[0].failures, ['cannot be opened as a video'])
})
