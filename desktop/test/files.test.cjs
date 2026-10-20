// The folder listing, the default output folder and the read-back whitelist (src/main/files.ts).
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { listVideos, defaultOutDir, isResultFile } = require('../dist/main/main/files.js')

function withTempDir(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tester-'))
  return Promise.resolve(fn(dir)).finally(() => fs.rmSync(dir, { recursive: true, force: true }))
}

test('listVideos keeps only video files, in numeric camera order, with sizes in MB', () =>
  withTempDir(async (dir) => {
    fs.writeFileSync(path.join(dir, 'cam10.MP4'), Buffer.alloc(1024 * 1024 * 2.5))
    fs.writeFileSync(path.join(dir, 'cam2.mov'), 'b')
    fs.writeFileSync(path.join(dir, 'cam1.mp4'), 'a')
    fs.writeFileSync(path.join(dir, 'notes.txt'), 'not a video')
    fs.writeFileSync(path.join(dir, 'board.png'), 'not a video')
    fs.mkdirSync(path.join(dir, 'cam0.mp4')) // a folder with a video's name is not a video
    const videos = await listVideos(dir)
    assert.deepEqual(
      videos.map((v) => v.name),
      ['cam1.mp4', 'cam2.mov', 'cam10.MP4'],
    )
    assert.equal(videos[2].sizeMb, 2.5)
    assert.equal(videos[0].sizeMb, 0)
    for (const v of videos) assert.equal(v.path, path.join(dir, v.name))
  }))

test('listVideos of an empty folder is an empty list', () =>
  withTempDir(async (dir) => {
    assert.deepEqual(await listVideos(dir), [])
  }))

test('defaultOutDir is backend/output/<take folder>-<date-time>', () => {
  const when = new Date(Date.UTC(2026, 9, 19, 18, 30, 45))
  const backend = path.resolve('/repo/backend')
  const out = defaultOutDir(backend, path.resolve('/session/take01'), when)
  assert.equal(out, path.join(backend, 'output', 'take01-20261019-1830'))
})

test('isResultFile allows absolute result files only', () => {
  const abs = path.resolve('/out/take01')
  assert.ok(isResultFile(path.join(abs, 'out3d.bvh')))
  assert.ok(isResultFile(path.join(abs, 'out3d.metrics.JSON')))
  assert.ok(isResultFile(path.join(abs, 'out3d.log')))
  assert.ok(!isResultFile(path.join('out', 'out3d.bvh'))) // relative
  assert.ok(!isResultFile(path.join(abs, 'cam0.mp4'))) // not a result
  assert.ok(!isResultFile(path.join(abs, 'calibration.json.exe')))
})
