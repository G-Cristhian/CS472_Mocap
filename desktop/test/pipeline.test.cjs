// The command line the app runs and where it finds Python (src/main/pipeline.ts).
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { BACKEND_DIR, REPO_ROOT, pipelineArgs, resolvePython } = require('../dist/main/main/pipeline.js')

const OUT_DIR = path.resolve('/out/t1')
const OPTIONS = {
  videos: [path.resolve('/takes/t1/cam0.mp4'), path.resolve('/takes/t1/cam1.MOV')],
  heightM: 1.78,
  outDir: OUT_DIR,
  detector: 'rtmpose',
  smoother: 'butterworth',
  fov: 75,
  clapThreshold: 1,
  clapTimes: null,
  jobs: 0,
  recalibrate: true,
  resume: true,
}

test('the repo root and backend folder are found from the compiled file', () => {
  assert.ok(fs.existsSync(path.join(REPO_ROOT, 'desktop', 'package.json')), REPO_ROOT)
  assert.equal(BACKEND_DIR, path.join(REPO_ROOT, 'backend'))
  assert.ok(fs.existsSync(path.join(BACKEND_DIR, 'mocap_pipeline', 'run_pipeline.py')))
})

test('pipelineArgs is the command processing-a-take.md gives, with every file next to --out', () => {
  assert.deepEqual(pipelineArgs(OPTIONS), [
    '-u',
    '-m',
    'mocap_pipeline.run_pipeline',
    OPTIONS.videos[0],
    OPTIONS.videos[1],
    '--height-m',
    '1.78',
    '--out',
    path.join(OUT_DIR, 'out3d.json'),
    '--calibration',
    path.join(OUT_DIR, 'calibration.json'),
    '--detector',
    'rtmpose',
    '--smoother',
    'butterworth',
    '--fov',
    '75',
    '--jobs',
    '0',
    '--recalibrate',
    '--resume',
  ])
})

test('a changed clap threshold and hand-typed clap times become --clap-threshold and --sync', () => {
  const args = pipelineArgs({ ...OPTIONS, clapThreshold: 0.5, clapTimes: [1.25, 0.8] })
  const i = args.indexOf('--clap-threshold')
  assert.deepEqual(args.slice(i, i + 5), ['--clap-threshold', '0.5', '--sync', '1.25', '0.8'])
  assert.ok(args.indexOf('--jobs') < i && i < args.indexOf('--recalibrate'))
})

test('the flags are left out when unticked', () => {
  const args = pipelineArgs({ ...OPTIONS, recalibrate: false, resume: false })
  assert.ok(!args.includes('--recalibrate') && !args.includes('--resume'))
  assert.deepEqual(args.slice(-2), ['--jobs', '0'])
})

test('resolvePython prefers the backend venv', () => {
  const python = resolvePython()
  const venv = [
    path.join(BACKEND_DIR, '.venv', 'Scripts', 'python.exe'),
    path.join(BACKEND_DIR, '.venv', 'bin', 'python'),
  ].find((p) => fs.existsSync(p))
  if (venv) assert.equal(python, venv)
  else assert.ok(python === 'python' || python === 'python3', python)
})
