// Where a run's report lives, when it is rebuilt, and when a copied run gets none (src/main/reportFile.ts).
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { runFiles, reportIsFresh, loadReport } = require('../dist/main/main/reportFile.js')

function folder() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'report-'))
  for (const f of ['out3d.pose.npz', 'out3d.sync.json', 'calibration.json', 'out3d.keypoints.cam0.npz']) fs.writeFileSync(path.join(dir, f), 'x')
  fs.writeFileSync(path.join(dir, 'out3d.metrics.json'), JSON.stringify({ run: { started: '2026-11-07T10:00:00' } }))
  return dir
}

function age(file, seconds) {
  const t = new Date(Date.now() - seconds * 1000)
  fs.utimesSync(file, t, t)
}

test('a copied run in runs/<time>/ maps back to its folder', () => {
  const take = path.join(os.tmpdir(), 'take')
  const f = runFiles(path.join(take, 'runs', '20261107-100000', 'out3d.metrics.json'))
  assert.equal(f.folder, take)
  assert.equal(f.snapshot, true)
  assert.equal(f.report, path.join(take, 'out3d.report.json'))
  assert.equal(f.out, path.join(take, 'out3d.json'))
  assert.equal(runFiles(path.join(take, 'out3d.metrics.json')).snapshot, false)
})

test('a saved report is reused until a file it was built from is newer', async () => {
  const dir = folder()
  const files = runFiles(path.join(dir, 'out3d.metrics.json'))
  assert.equal(await reportIsFresh(files), false)
  fs.writeFileSync(files.report, JSON.stringify({ version: 3 }))
  for (const f of fs.readdirSync(dir)) if (!f.endsWith('report.json')) age(path.join(dir, f), 60)
  assert.equal(await reportIsFresh(files), true)
  // a report this app cannot read is built again
  fs.writeFileSync(files.report, JSON.stringify({ version: 2 }))
  assert.equal(await reportIsFresh(files), false)
  fs.writeFileSync(files.report, JSON.stringify({ version: 3 }))
  fs.writeFileSync(path.join(dir, 'out3d.keypoints.cam0.npz'), 'newer')
  age(files.report, 30)
  assert.equal(await reportIsFresh(files), false)
})

test('a fresh report is read without starting Python', async () => {
  const dir = folder()
  for (const f of fs.readdirSync(dir)) age(path.join(dir, f), 60)
  fs.writeFileSync(path.join(dir, 'out3d.report.json'), JSON.stringify({ version: 3, ok: 'yes' }))
  const result = await loadReport(path.join(dir, 'out3d.metrics.json'), 'no-such-python', dir)
  assert.equal(result.ok, true)
  assert.match(result.text, /"ok":"yes"/)
})

test('a copy of an earlier run gets no report once its folder has been run again', async () => {
  const dir = folder()
  const copy = path.join(dir, 'runs', '20261107-090000')
  fs.mkdirSync(copy, { recursive: true })
  fs.writeFileSync(path.join(copy, 'out3d.metrics.json'), JSON.stringify({ run: { started: '2026-11-07T09:00:00' } }))
  const result = await loadReport(path.join(copy, 'out3d.metrics.json'), 'no-such-python', dir)
  assert.equal(result.ok, false)
  assert.match(result.error, /run again since/)
})

test('a run that stopped before triangulating says which file is missing', async () => {
  const dir = folder()
  fs.rmSync(path.join(dir, 'out3d.pose.npz'))
  const result = await loadReport(path.join(dir, 'out3d.metrics.json'), 'no-such-python', dir)
  assert.equal(result.ok, false)
  assert.match(result.error, /out3d\.pose\.npz is not in the run's folder/)
})
