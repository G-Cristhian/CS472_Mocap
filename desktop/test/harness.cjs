// Drives the app's compiled main-process code from the command line, so the backend's
// pytest can check the app against the real pipeline (backend/tests/test_desktop_tester.py).
// Needs `tsc -p tsconfig.main.json` first (npm test and the pytest fixture both run it).
//
//   node test/harness.cjs replay < doc.json
//       doc = {videos: [...], lines: [{text, stderr}], exitCode}
//       Feeds the lines through the ProgressTracker as runPipeline would and prints
//       {progress: [...], result: {...}}.
//
//   node test/harness.cjs run options.json [--cancel-on TEXT]
//       Runs the pipeline exactly as the window does (runPipeline with a RunOptions
//       object), cancelling when a log line contains TEXT, and prints
//       {python, log: [...], progress: [...], result: {...}}.
const { readFileSync } = require('node:fs')
const { ProgressTracker } = require('../dist/main/shared/progress.js')
const { resolvePython, runPipeline } = require('../dist/main/main/pipeline.js')

function replay() {
  const doc = JSON.parse(readFileSync(0, 'utf8'))
  const tracker = new ProgressTracker(doc.videos)
  const progress = []
  for (const { text, stderr } of doc.lines) {
    const p = tracker.feed(text, Boolean(stderr))
    if (p) progress.push(p)
  }
  return { progress, result: tracker.result(doc.exitCode ?? 0) }
}

async function run(optionsPath, cancelOn) {
  const options = JSON.parse(readFileSync(optionsPath, 'utf8'))
  const log = []
  const progress = []
  let handle = null
  handle = runPipeline(
    options,
    (line) => {
      log.push(line)
      if (cancelOn && line.includes(cancelOn)) handle.cancel()
    },
    (p) => progress.push(p),
  )
  const result = await handle.done
  return { python: resolvePython(), log, progress, result }
}

async function main(argv) {
  const [mode, ...rest] = argv
  let out
  if (mode === 'replay') out = replay()
  else if (mode === 'run') {
    const i = rest.indexOf('--cancel-on')
    out = await run(rest[0], i >= 0 ? rest[i + 1] : null)
  } else throw new Error('usage: harness.cjs replay | run options.json [--cancel-on TEXT]')
  process.stdout.write(JSON.stringify(out))
}

main(process.argv.slice(2)).catch((e) => {
  process.stderr.write(`${e.stack || e}\n`)
  process.exit(2)
})
