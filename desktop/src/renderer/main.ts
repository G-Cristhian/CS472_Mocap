/**
 * The page: pick videos, check them, queue runs (one, or a matrix of settings), watch the bar,
 * play a result and read its numbers, and compare every run in the library.
 */
import { parseClapTimes } from '../shared/clapTimes'
import { COLUMNS, DEFAULT_VIEW, takes, viewRows, type LibraryView } from '../shared/library'
import { metricSections, type MmScale } from '../shared/metrics'
import { expandMatrix, parseDetectEvery, settingsLabel, type Matrix } from '../shared/queue'
import type { Backend, CheckResult, LibraryRun, Progress, RunOptions, RunResult, Smoother, VideoFile } from '../shared/types'
import { cameraLines, frameAt, mmScale, parseReport, rigState, STATE_COLOURS, type Report } from '../shared/report'
import { cameraColour, ReportPanel } from './runReport'
import { BvhViewer } from './viewer'

const backend: Backend = (window as unknown as { backend?: Backend }).backend ?? (await import('./mock')).mock
const inElectron = 'backend' in window

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T
const setup = $('setup')
const progressPanel = $('progress')
const preview = $('preview')
const videoList = $<HTMLUListElement>('videos')
const folderLabel = $('folder')
const checkButton = $<HTMLButtonElement>('check')
const checkBox = $('check-result')
const runButton = $<HTMLButtonElement>('run')
const setupError = $('setup-error')
const folderError = $('folder-error')
const clapNote = $('clap-note')
const heightNote = $('height-note')
const bar = $<HTMLProgressElement>('bar')
const stageLabel = $('stage')
const detailLabel = $('detail')
const videoProgress = $<HTMLUListElement>('video-progress')
const log = $<HTMLPreElement>('log')
const resultError = $('result-error')
const timeSlider = $<HTMLInputElement>('time')
const clockLabel = $('clock')
const playButton = $<HTMLButtonElement>('play')
const metricsBox = $('metrics')
const rerunButton = $<HTMLButtonElement>('rerun-smoother')
const matrixButton = $<HTMLButtonElement>('queue-matrix')
const matrixCount = $('matrix-count')
const matrixError = $('matrix-error')
const queueList = $<HTMLUListElement>('queue')
const queueCount = $('queue-count')
const currentTitle = $('current-title')
const resultTitle = $('result-title')
const libTable = $<HTMLTableElement>('lib-table')
const libTake = $<HTMLSelectElement>('lib-take')
const libDone = $<HTMLInputElement>('lib-done')

if (!inElectron) $('python-note').textContent = 'browser preview with a mocked pipeline'

interface Picked extends VideoFile {
  use: boolean
}
let videoDir: string | null = null
/** the output folder made up when the take was chosen; while the box still holds it, it is renewed at queue time */
let autoOutDir = ''
let picked: Picked[] = []
let chosenKey = '[]' // the chosen videos in camera order, as the clap times and the check result were made for
let chooseSeq = 0 // the latest folder choice; an older one that finishes late is dropped
let checkSeq = 0 // the latest check; a check whose selection has changed since is dropped
let checking = false
let outDir = ''
let viewer: BvhViewer | null = null

// ---- 1. setup --------------------------------------------------------------------------

function chosenVideos(): string[] {
  return picked.filter((p) => p.use).map((p) => p.path)
}

function renderVideos(): void {
  videoList.replaceChildren()
  picked.forEach((v, i) => {
    const li = document.createElement('li')
    const check = document.createElement('input')
    check.type = 'checkbox'
    check.checked = v.use
    check.addEventListener('change', () => {
      v.use = check.checked
      renderVideos()
    })
    const order = document.createElement('span')
    order.className = 'order'
    order.textContent = v.use ? `cam${picked.filter((p, j) => p.use && j < i).length}` : '—'
    const name = document.createElement('span')
    name.className = 'name mono'
    name.textContent = v.name
    const size = document.createElement('span')
    size.className = 'muted small'
    size.textContent = `${v.sizeMb} MB`
    const up = document.createElement('button')
    up.className = 'btn'
    up.textContent = '↑'
    up.title = 'Earlier camera'
    up.disabled = i === 0
    up.addEventListener('click', () => {
      ;[picked[i - 1], picked[i]] = [picked[i], picked[i - 1]]
      renderVideos()
    })
    const down = document.createElement('button')
    down.className = 'btn'
    down.textContent = '↓'
    down.title = 'Later camera'
    down.disabled = i === picked.length - 1
    down.addEventListener('click', () => {
      ;[picked[i + 1], picked[i]] = [picked[i], picked[i + 1]]
      renderVideos()
    })
    li.append(check, order, name, size, up, down)
    videoList.append(li)
  })
  const chosen = picked.filter((p) => p.use).length
  runButton.disabled = chosen < 2
  matrixButton.disabled = chosen < 2
  checkButton.disabled = chosen < 1 || checking
  setupError.textContent = picked.length && chosen < 2 ? 'Pick at least two videos.' : ''
  selectionChanged()
}

/**
 * Typed clap times and a check result belong to one set of videos in one order: the times go to the
 * videos by position. When the ticks, the order or the folder's files change, both are cleared,
 * the times with a note, so no time silently moves to another camera.
 */
function selectionChanged(): void {
  const key = JSON.stringify(chosenVideos())
  if (key === chosenKey) return
  chosenKey = key
  checkBox.hidden = true
  const box = $<HTMLInputElement>('clap-times')
  // a note left from an earlier change would describe a clearing that did not happen now
  clapNote.textContent = box.value.trim()
    ? 'Clap times cleared: the videos or their order changed. Type them again, camera 0 first.'
    : ''
  box.value = ''
}

$('choose').addEventListener('click', async () => {
  const dir = await backend.chooseDirectory()
  if (!dir) return
  const seq = ++chooseSeq
  folderError.textContent = ''
  // read the new folder before touching the page, so a folder that cannot be read, or holds no
  // videos (the folder above the take, say), leaves the last take as it was
  let videos: VideoFile[]
  let newOutDir: string
  try {
    videos = await backend.listVideos(dir)
    newOutDir = await backend.defaultOutDir(dir)
  } catch (e) {
    if (seq === chooseSeq) folderError.textContent = `Could not read ${dir}: ${e instanceof Error ? e.message : String(e)}`
    return
  }
  if (seq !== chooseSeq) return
  if (!videos.length) {
    folderError.textContent = `No .mov or .mp4 files in ${dir}.${videoDir ? ' The take below is unchanged.' : ''}`
    return
  }
  if (dir === videoDir) {
    // choosing the same folder again refreshes the list: files still there keep their tick and place,
    // new ones go at the end, and a typed output folder stays
    const byPath = new Map(videos.map((v) => [v.path, v]))
    const kept = picked.filter((p) => byPath.has(p.path)).map((p) => ({ ...byPath.get(p.path)!, use: p.use }))
    const added = videos.filter((v) => !picked.some((p) => p.path === v.path)).map((v) => ({ ...v, use: true }))
    const nameOrder = (a: VideoFile, b: VideoFile) => a.name.localeCompare(b.name, undefined, { numeric: true })
    const reordered = kept.some((p, i) => i > 0 && nameOrder(kept[i - 1], p) > 0)
    if (!reordered) {
      // name order is camera order (filming.md section 8): a file copied in late takes its place
      picked = [...kept, ...added].sort(nameOrder)
    } else {
      // the user set the order by hand, so a new file cannot be placed for them: it goes last, said loudly
      picked = [...kept, ...added]
    }
    if (added.length) {
      folderError.textContent = `Added ${added.map((v) => v.name).join(', ')}${reordered ? ' at the end of the list: check the camera order.' : ' in name order.'}`
    }
  } else {
    videoDir = dir
    folderLabel.textContent = dir
    picked = videos.map((v) => ({ ...v, use: true }))
    outDir = newOutDir
    autoOutDir = newOutDir
    $<HTMLInputElement>('outdir').value = outDir
  }
  renderVideos()
})

$('choose-outdir').addEventListener('click', async () => {
  const box = $<HTMLInputElement>('outdir')
  const dir = await backend.chooseOutputDirectory(box.value.trim())
  if (dir) box.value = dir
})

$('clap-times').addEventListener('input', () => {
  clapNote.textContent = ''
})
$('clap-threshold').addEventListener('input', () => {
  // a check result was made with the old threshold
  checkBox.hidden = true
})

function updateRtmposeFields(): void {
  const rtm = $<HTMLSelectElement>('detector').value === 'rtmpose'
  $('rtmpose-mode-field').hidden = !rtm
  $('rtmpose-every-field').hidden = !rtm
}
$('detector').addEventListener('change', updateRtmposeFields)
updateRtmposeFields()

function updateHeightNote(): void {
  heightNote.hidden = $<HTMLInputElement>('recalibrate').checked
}
$('recalibrate').addEventListener('change', updateHeightNote)
updateHeightNote()

function readClapThreshold(): number | string {
  const t = Number($<HTMLInputElement>('clap-threshold').value)
  return t > 0 && t <= 10 ? t : 'The clap threshold must be above 0 and at most 10.'
}

function readOptions(): RunOptions | string {
  const videos = chosenVideos()
  const heightM = Number($<HTMLInputElement>('height').value)
  const fov = Number($<HTMLInputElement>('fov').value)
  const jobs = Number($<HTMLInputElement>('jobs').value)
  outDir = $<HTMLInputElement>('outdir').value.trim()
  if (videos.length < 2) return 'Pick at least two videos.'
  if (!(heightM >= 1 && heightM <= 2.5)) return 'Height must be between 1 and 2.5 metres.'
  if (!(fov >= 30 && fov <= 120)) return 'Field of view must be between 30 and 120 degrees.'
  if (!(Number.isInteger(jobs) && jobs >= 0 && jobs <= 16)) return 'Videos detected at once must be a whole number from 0 (automatic) to 16.'
  const clapThreshold = readClapThreshold()
  if (typeof clapThreshold === 'string') return clapThreshold
  const clapTimes = parseClapTimes($<HTMLInputElement>('clap-times').value, videos.length)
  if (typeof clapTimes === 'string') return clapTimes
  if (!outDir) return 'Give an output folder.'
  const detector = $<HTMLSelectElement>('detector').value as RunOptions['detector']
  const every = Number($<HTMLInputElement>('rtmpose-every').value)
  if (detector === 'rtmpose' && !(Number.isInteger(every) && every >= 1 && every <= 100)) {
    return 'RTMPose detector every N frames must be a whole number from 1 to 100.'
  }
  return {
    videos,
    heightM,
    fov,
    outDir,
    detector,
    smoother: $<HTMLSelectElement>('smoother').value as RunOptions['smoother'],
    clapThreshold,
    clapTimes,
    jobs,
    ...(detector === 'rtmpose'
      ? { rtmposeMode: $<HTMLSelectElement>('rtmpose-mode').value as RunOptions['rtmposeMode'], rtmposeDetectEvery: every }
      : {}),
    recalibrate: $<HTMLInputElement>('recalibrate').checked,
    resume: $<HTMLInputElement>('resume').checked,
  }
}

/**
 * The form's run, with a fresh default output folder: the default is stamped with the minute the
 * take was chosen, so a second run queued later would otherwise land in the first one's folder.
 * A folder typed or chosen by hand is kept as it is.
 */
async function readFreshOptions(): Promise<RunOptions | string> {
  const box = $<HTMLInputElement>('outdir')
  if (videoDir && autoOutDir && box.value.trim() === autoOutDir) {
    const fresh = await backend.defaultOutDir(videoDir)
    // two runs queued in the same minute get -2, -3… rather than one folder
    let dir = fresh
    for (let n = 2; jobs.some((j) => j.options.outDir === dir); n++) dir = `${fresh}-${n}`
    autoOutDir = dir
    box.value = dir
  }
  return readOptions()
}

// ---- 1c. the comparison matrix -------------------------------------------------------------

function ticked(name: string): string[] {
  return [...document.querySelectorAll<HTMLInputElement>(`input[name="${name}"]:checked`)].map((i) => i.value)
}

function readMatrix(): Matrix | string {
  const every = parseDetectEvery($<HTMLInputElement>('c-every').value)
  const detectors = ticked('c-detector') as Matrix['detectors']
  if (typeof every === 'string' && detectors.includes('rtmpose')) return every
  return {
    detectors,
    smoothers: ticked('c-smoother') as Matrix['smoothers'],
    rtmposeModes: ticked('c-mode') as Matrix['rtmposeModes'],
    rtmposeDetectEvery: typeof every === 'string' ? [] : every,
  }
}

/** "6 runs: 3 detect, 3 reuse a detection" under the button, or why the ticks make no runs. */
function updateMatrixCount(): void {
  const matrix = readMatrix()
  const base = { detector: 'mediapipe', smoother: 'savgol', resume: false } as RunOptions
  const runs = typeof matrix === 'string' ? matrix : expandMatrix(base, matrix, 'x')
  matrixError.textContent = typeof runs === 'string' ? runs : ''
  if (typeof runs === 'string') {
    matrixCount.textContent = ''
    return
  }
  const detect = new Set(runs.map((r) => r.outDir)).size
  matrixCount.textContent = `${runs.length} run${runs.length === 1 ? '' : 's'}: ${detect} detect${runs.length > detect ? `, ${runs.length - detect} reuse a detection` : ''}`
}
$('compare').addEventListener('input', updateMatrixCount)
updateMatrixCount()

matrixButton.addEventListener('click', async () => {
  const matrix = readMatrix()
  const base = await readFreshOptions()
  if (typeof base === 'string' || typeof matrix === 'string') {
    matrixError.textContent = typeof base === 'string' ? base : (matrix as string)
    return
  }
  const taken = new Set(jobs.map((j) => j.options.outDir))
  const runs = expandMatrix(base, matrix, base.outDir, taken)
  if (typeof runs === 'string') {
    matrixError.textContent = runs
    return
  }
  matrixError.textContent = ''
  enqueue(runs)
})

// ---- 1b. the pre-flight check ----------------------------------------------------------------

function renderCheck(result: CheckResult): void {
  checkBox.replaceChildren()
  checkBox.hidden = false
  if (result.error && !result.videos.length) {
    const p = document.createElement('div')
    p.className = 'fail'
    p.textContent = `The check could not run: ${result.error}`
    checkBox.append(p)
    return
  }
  for (const v of result.videos) {
    const row = document.createElement('div')
    row.className = 'file'
    const name = document.createElement('span')
    name.className = 'name'
    name.textContent = v.name
    const facts = document.createElement('span')
    facts.className = 'facts'
    const parts = [v.video, v.lens, v.clapS === undefined ? undefined : `clap at ${v.clapS.toFixed(2)} s`].filter(Boolean)
    facts.textContent = parts.join(' · ') || 'could not be read'
    row.append(name, facts)
    for (const w of v.warnings) {
      const s = document.createElement('span')
      s.className = 'warn'
      s.textContent = `warning: ${w}`
      row.append(document.createElement('span'), s)
    }
    for (const f of v.failures) {
      const s = document.createElement('span')
      s.className = 'fail'
      s.textContent = `problem: ${f}`
      row.append(document.createElement('span'), s)
    }
    checkBox.append(row)
  }
  for (const a of result.across) {
    const s = document.createElement('div')
    s.className = a.startsWith('claps ') ? 'facts' : 'warn'
    s.textContent = a.startsWith('claps ') ? `across cameras: ${a.slice(6)}` : `across cameras, warning: ${a}`
    checkBox.append(s)
  }
  const verdict = document.createElement('div')
  verdict.className = `verdict ${result.ok ? 'good' : 'bad'}`
  const failed = result.videos.filter((v) => v.failures.length).length
  verdict.textContent = result.ok
    ? 'All files usable.'
    : `${failed || 'Some'} file(s) the pipeline cannot use.` +
      (result.videos.some((v) => v.failures.some((f) => f.startsWith('no clap')))
        ? ' For a faint clap, lower the clap loudness threshold or give the clap times by hand.'
        : '')
  checkBox.append(verdict)
}

checkButton.addEventListener('click', async () => {
  const threshold = readClapThreshold()
  if (typeof threshold === 'string') {
    setupError.textContent = threshold
    return
  }
  setupError.textContent = ''
  const seq = ++checkSeq
  const key = chosenKey
  const thresholdText = $<HTMLInputElement>('clap-threshold').value
  checking = true
  checkButton.disabled = true
  checkButton.textContent = 'Checking…'
  const offLog = backend.onLog(appendLog)
  let result: CheckResult
  try {
    result = await backend.checkVideos(chosenVideos(), threshold)
  } catch (e) {
    result = { ok: false, videos: [], across: [], output: '', error: e instanceof Error ? e.message : String(e) }
  } finally {
    offLog()
    checking = false
    checkButton.textContent = 'Check the videos'
    checkButton.disabled = chosenVideos().length < 1
  }
  // a result for other videos, or another threshold, would vouch for a check nobody ran
  if (seq === checkSeq && key === chosenKey && thresholdText === $<HTMLInputElement>('clap-threshold').value) renderCheck(result)
  else setupError.textContent = 'The videos or the clap threshold changed during the check: check again.'
})

// ---- 2. progress -------------------------------------------------------------------------

function showProgress(p: Progress): void {
  bar.value = Math.round(p.fraction * 1000)
  stageLabel.textContent = p.stage
  stageLabel.className = `pill ${p.stage === 'done' || p.stage === 'failed' ? p.stage : ''}`
  detailLabel.textContent = p.detail
  videoProgress.replaceChildren()
  for (const v of p.videos ?? []) {
    const li = document.createElement('li')
    const state = document.createElement('span')
    state.className = `state ${v.state}`
    state.textContent = v.state
    const name = document.createElement('span')
    name.className = 'name mono'
    name.textContent = v.name
    const detail = document.createElement('span')
    detail.className = 'vdetail'
    detail.textContent = v.detail
    li.append(state, name, detail)
    videoProgress.append(li)
  }
}

function appendLog(line: string): void {
  log.textContent += line + '\n'
  if (log.textContent.length > 200_000) log.textContent = log.textContent.slice(-150_000)
  log.scrollTop = log.scrollHeight
}

// ---- 2b. the queue: runs go one after another --------------------------------------------------

type JobState = 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
interface Job {
  id: number
  options: RunOptions
  label: string
  take: string
  state: JobState
  /** "540 s", or the first line of the failure */
  detail: string
}
let jobs: Job[] = []
let current: Job | null = null
let nextJobId = 1
let cancelRequested = false

function takeOf(options: RunOptions): string {
  return options.videos[0]?.split(/[\\/]/).slice(-2, -1)[0] ?? ''
}

function enqueue(list: RunOptions[]): void {
  for (const options of list) {
    jobs.push({ id: nextJobId++, options, label: settingsLabel(options), take: takeOf(options), state: 'queued', detail: '' })
  }
  progressPanel.hidden = false
  renderQueue()
  void pump()
}

function renderQueue(): void {
  queueList.replaceChildren()
  for (const job of jobs) {
    const li = document.createElement('li')
    const state = document.createElement('span')
    state.className = `qstate ${job.state}`
    state.textContent = job.state
    const take = document.createElement('span')
    take.textContent = job.take
    take.title = job.options.videos.join('\n')
    const what = document.createElement('span')
    what.className = 'qdetail'
    what.textContent = [job.label, job.options.resume ? 'resume' : '', job.detail].filter(Boolean).join(' · ')
    what.title = `${job.options.outDir}${job.detail ? `\n${job.detail}` : ''}`
    const remove = document.createElement('button')
    remove.className = 'btn'
    remove.textContent = '×'
    remove.title = 'Take this run off the queue'
    remove.hidden = job.state !== 'queued'
    remove.addEventListener('click', () => {
      jobs = jobs.filter((j) => j !== job)
      renderQueue()
    })
    li.append(state, take, what, remove)
    queueList.append(li)
  }
  const waiting = jobs.filter((j) => j.state === 'queued').length
  const done = jobs.filter((j) => j.state === 'done').length
  queueCount.textContent = jobs.length ? `${done} of ${jobs.length} done${waiting ? `, ${waiting} waiting` : ''}` : ''
  runButton.textContent = current ? 'Add to queue' : 'Run the pipeline'
  $<HTMLButtonElement>('stop-queue').disabled = !current && !waiting
  $<HTMLButtonElement>('clear-done').disabled = !jobs.some((j) => j.state !== 'queued' && j.state !== 'running')
}

/** Starts the next queued run when nothing is running; each finished run starts the next. */
async function pump(): Promise<void> {
  if (current) return
  const job = jobs.find((j) => j.state === 'queued')
  if (!job) return
  current = job
  job.state = 'running'
  renderQueue()
  const started = Date.now()
  const result = await runOne(job)
  const seconds = Math.round((Date.now() - started) / 1000)
  job.state = result.ok ? 'done' : cancelRequested ? 'cancelled' : 'failed'
  job.detail = result.ok ? `${seconds} s` : (result.error ?? 'Failed').split('\n')[0]
  current = null
  cancelRequested = false
  renderQueue()
  void refreshLibrary()
  if (result.ok) await showResult(result.bvhPath, result.metricsPath, job.options, `${job.take}, ${job.label}`)
  else if (!jobs.some((j) => j.state === 'queued')) showFailure(result, job)
  void pump()
}

async function runOne(job: Job): Promise<RunResult> {
  const index = jobs.indexOf(job) + 1
  currentTitle.textContent = `Run ${index} of ${jobs.length}: ${job.take}, ${job.label}`
  log.textContent = ''
  showProgress({ stage: 'starting', fraction: 0, detail: 'Starting the pipeline', videos: [] })
  $<HTMLButtonElement>('cancel').disabled = false
  const offLog = backend.onLog(appendLog)
  const offProgress = backend.onProgress(showProgress)
  let result: RunResult
  try {
    result = await backend.run(job.options)
  } catch (e) {
    result = { ok: false, exitCode: null, error: e instanceof Error ? e.message : String(e) }
  } finally {
    offLog()
    offProgress()
  }
  $<HTMLButtonElement>('cancel').disabled = true
  if (result.ok) {
    showProgress({ ...currentProgress(), stage: 'done', fraction: 1, detail: 'Finished' })
  } else {
    // the first line only: the whole message is in the result box
    // videos still detecting or queued when the run died did not finish
    const videos = currentProgress().videos.map((v) =>
      v.state === 'detecting' || v.state === 'waiting' ? { ...v, state: 'failed' as const, detail: 'stopped' } : v,
    )
    showProgress({ ...currentProgress(), videos, stage: 'failed', detail: (result.error ?? 'Failed').split('\n')[0] })
  }
  return result
}

let latestProgress: Progress = { stage: 'starting', fraction: 0, detail: '', videos: [] }
function currentProgress(): Progress {
  return latestProgress
}
backend.onProgress((p) => {
  latestProgress = p
})

runButton.addEventListener('click', async () => {
  const options = await readFreshOptions()
  if (typeof options === 'string') {
    setupError.textContent = options
    return
  }
  setupError.textContent = ''
  clapNote.textContent = ''
  enqueue([options])
})

$('cancel').addEventListener('click', () => {
  cancelRequested = true
  void backend.cancel()
})

$('stop-queue').addEventListener('click', () => {
  for (const j of jobs) if (j.state === 'queued') j.state = 'cancelled'
  if (current) {
    cancelRequested = true
    void backend.cancel()
  }
  renderQueue()
})

$('clear-done').addEventListener('click', () => {
  jobs = jobs.filter((j) => j.state === 'queued' || j.state === 'running')
  renderQueue()
})

// ---- 3. preview -----------------------------------------------------------------------------

function fmt(t: number): string {
  return t.toFixed(2)
}

/** the run in the result panel: its options when it ran this session, for "Rerun with the other smoother" */
let shownOptions: RunOptions | null = null
let shownFolder: string | null = null
let shownMetrics: string | null = null
/** bumped by every showResult, so a slow report for an earlier run is dropped */
let shownToken = 0
let shownMetricsJson: Record<string, unknown> | null = null
const reportPanel = new ReportPanel()

function seek(t: number): void {
  if (!viewer) return
  viewer.pause()
  playButton.textContent = 'Play'
  viewer.setTime(t)
  timeSlider.value = String(Math.round((t / (viewer.duration || 1)) * 1000))
  clockLabel.textContent = `${fmt(t)} / ${fmt(viewer.duration)} s`
  reportPanel.update(t)
}
reportPanel.onSeek = seek

function showFailure(result: RunResult, job: Job): void {
  preview.hidden = false
  resultTitle.textContent = `${job.take}, ${job.label}`
  resultError.textContent = result.error ?? 'The pipeline failed. The log above has the details.'
  $<HTMLDetailsElement>('log-box').open = true
  metricsBox.replaceChildren()
  shownOptions = null
  shownFolder = job.options.outDir
  shownMetrics = null
  rerunButton.disabled = true
}

async function showResult(
  bvhPath: string | null | undefined,
  metricsPath: string | null | undefined,
  options: RunOptions | null,
  title: string,
): Promise<void> {
  preview.hidden = false
  resultError.textContent = ''
  resultTitle.textContent = title
  shownOptions = options
  shownFolder = options?.outDir ?? metricsPath ?? null
  shownMetrics = metricsPath ?? null
  const token = ++shownToken
  rerunButton.disabled = !options
  renderLibrary()
  if (!viewer) {
    viewer = new BvhViewer($('viewer'))
    if (!inElectron) (window as unknown as { viewer?: BvhViewer }).viewer = viewer   // for poking at it in the browser preview
    viewer.onTime = (t) => {
      timeSlider.value = String(Math.round((t / viewer!.duration) * 1000))
      clockLabel.textContent = `${fmt(t)} / ${fmt(viewer!.duration)} s`
      reportPanel.update(t)
    }
  }
  viewer.jointColour = null
  viewer.setCameras([], null)
  reportPanel.clear(metricsPath ? 'Reading the frame-by-frame numbers…' : '')
  await showMetrics(metricsPath ?? undefined)
  if (metricsPath) void showReport(metricsPath, token)
  if (!bvhPath) {
    resultError.textContent = 'This run left no BVH (was --no-bvh used, or did it fail before the skeleton?).'
    return
  }
  try {
    viewer.load(await backend.readText(bvhPath))
  } catch (e) {
    resultError.textContent = `Could not load ${bvhPath}: ${e instanceof Error ? e.message : String(e)}`
    return
  }
  clockLabel.textContent = `0.00 / ${fmt(viewer.duration)} s`
  timeSlider.value = '0'
  playButton.textContent = 'Pause'
  viewer.play()
}

/** The run's frame-by-frame report: cameras in the 3D view, joint colours, 2D views, timelines, stories. */
async function showReport(metricsPath: string, token: number): Promise<void> {
  let report: Report
  try {
    const result = await backend.readReport(metricsPath)
    if (token !== shownToken) return
    if (!result.ok) {
      reportPanel.clear(`No frame-by-frame view for this run: ${result.error}`)
      return
    }
    report = parseReport(result.text)
  } catch (e) {
    if (token === shownToken) reportPanel.clear(`No frame-by-frame view for this run: ${e instanceof Error ? e.message : String(e)}`)
    return
  }
  if (token !== shownToken || !viewer) return
  const worst = cameraLines(report)[0]?.id
  viewer.setCameras(
    report.cameras.map((c, i) => ({
      id: c.id,
      position: c.position,
      forward: c.forward,
      up: c.up,
      halfWidth: c.width / 2 / c.focal_px,
      halfHeight: c.height / 2 / c.focal_px,
      colour: cameraColour(i),
      label: c.id + (c.id === worst && report.cameras.length > 1 ? ' (worst)' : ''),
    })),
    report.performer_centre.map((v) => v ?? NaN),
  )
  viewer.jointColour = (joint, t) => {
    const state = rigState(report, frameAt(report, t), joint, reportPanel.mode)
    return state ? STATE_COLOURS[state] : null
  }
  reportPanel.show(report, viewer.duration)
  reportPanel.update(viewer.currentTime)
  if (shownMetricsJson) renderMetrics(shownMetricsJson, mmScale(report))
}

async function showMetrics(metricsPath?: string): Promise<void> {
  metricsBox.replaceChildren()
  shownMetricsJson = null
  if (!metricsPath) return
  let m: Record<string, unknown>
  try {
    m = JSON.parse(await backend.readText(metricsPath))
  } catch {
    return
  }
  shownMetricsJson = m
  renderMetrics(m)
}

function renderMetrics(m: Record<string, unknown>, mm?: MmScale): void {
  metricsBox.replaceChildren()
  for (const section of metricSections(m, mm)) {
    const h = document.createElement('h3')
    h.textContent = section.title
    const dl = document.createElement('dl')
    dl.className = 'metrics'
    for (const row of section.rows) {
      const div = document.createElement('div')
      const dt = document.createElement('dt')
      dt.textContent = row.label
      const dd = document.createElement('dd')
      dd.textContent = row.value
      dd.className = row.grade
      div.append(dt, dd)
      if (row.scale) {
        const scale = document.createElement('small')
        scale.className = 'scale'
        scale.textContent = row.scale
        div.append(scale)
      }
      dl.append(div)
    }
    const wrap = document.createElement('div')
    wrap.append(h, dl)
    metricsBox.append(wrap)
  }
}

rerunButton.addEventListener('click', () => {
  if (!shownOptions) return
  const other: Smoother = shownOptions.smoother === 'savgol' ? 'butterworth' : 'savgol'
  // resume reuses the joints, clap times, calibration and 3D points; only smoothing and the rig rerun
  viewer?.pause()
  playButton.textContent = 'Play'
  enqueue([{ ...shownOptions, smoother: other, resume: true, recalibrate: false }])
})

playButton.addEventListener('click', () => {
  if (!viewer) return
  if (viewer.isPlaying) {
    viewer.pause()
    playButton.textContent = 'Play'
  } else {
    viewer.play()
    playButton.textContent = 'Pause'
  }
})

timeSlider.addEventListener('input', () => {
  if (!viewer) return
  seek((Number(timeSlider.value) / 1000) * viewer.duration)
})

$('open-folder').addEventListener('click', () => {
  if (shownFolder) void backend.openFolder(shownFolder)
})

$('again').addEventListener('click', () => {
  viewer?.pause()
  playButton.textContent = 'Play'
  setup.scrollIntoView({ behavior: 'smooth' })
})

// ---- 4. the library -------------------------------------------------------------------------

let library: LibraryRun[] = []
let libView: LibraryView = { ...DEFAULT_VIEW }
let libSeq = 0

async function refreshLibrary(): Promise<void> {
  const seq = ++libSeq
  try {
    const runs = await backend.listRuns()
    if (seq !== libSeq) return
    library = runs
  } catch (e) {
    $('lib-count').textContent = `Could not read the runs: ${e instanceof Error ? e.message : String(e)}`
    return
  }
  // the take filter offers the takes there are; a take that is gone falls back to all
  const names = takes(library)
  if (libView.take && !names.includes(libView.take)) libView = { ...libView, take: '' }
  libTake.replaceChildren(new Option('All takes', ''), ...names.map((t) => new Option(t, t)))
  libTake.value = libView.take
  renderLibrary()
}

function renderLibrary(): void {
  const rows = viewRows(library, libView)
  $('lib-count').textContent = library.length ? `${rows.length} of ${library.length} runs` : ''
  $('lib-empty').hidden = library.length > 0
  libTable.replaceChildren()
  if (!library.length) return
  const head = document.createElement('tr')
  for (const c of COLUMNS) {
    const th = document.createElement('th')
    const sorted = c.key === libView.sortKey
    th.textContent = c.title + (sorted ? (libView.descending ? ' ↓' : ' ↑') : '')
    th.className = sorted ? 'sorted' : ''
    if (c.note) th.title = c.note
    th.addEventListener('click', () => {
      // a new column starts with its most useful order: newest first, or smallest error and time first
      libView = sorted ? { ...libView, descending: !libView.descending } : { ...libView, sortKey: c.key, descending: c.key === 'started' || c.key === 'fps' }
      renderLibrary()
    })
    head.append(th)
  }
  head.append(document.createElement('th'))
  libTable.append(head)
  const column = (key: string) => COLUMNS.find((c) => c.key === key)!
  for (const r of rows) {
    const tr = document.createElement('tr')
    if (r.metricsPath === shownMetrics) tr.className = 'shown'
    for (const c of COLUMNS) {
      const td = document.createElement('td')
      td.textContent = c.text(r)
      td.className = c.grade?.(r) || (c.key === 'status' && r.status !== 'done' ? 'status-failed' : '')
      if (c.key === 'take') td.title = r.folder
      tr.append(td)
    }
    const actions = document.createElement('td')
    const view = document.createElement('button')
    view.className = 'btn'
    view.textContent = 'View'
    view.disabled = !r.bvhPath
    view.title = r.bvhPath ? 'Play this run and show its numbers' : 'This run left no skeleton'
    view.addEventListener('click', () => {
      const title = [r.take, column('detector').text(r), column('smoother').text(r), column('started').text(r)].join(', ')
      void showResult(r.bvhPath, r.metricsPath, null, title)
      preview.scrollIntoView({ behavior: 'smooth' })
    })
    const folder = document.createElement('button')
    folder.className = 'btn'
    folder.textContent = 'Folder'
    folder.title = r.folder
    folder.addEventListener('click', () => void backend.openFolder(r.metricsPath))
    actions.append(view, folder)
    tr.append(actions)
    libTable.append(tr)
  }
}

libTake.addEventListener('change', () => {
  libView = { ...libView, take: libTake.value }
  renderLibrary()
})
libDone.addEventListener('change', () => {
  libView = { ...libView, doneOnly: libDone.checked }
  renderLibrary()
})
$('lib-refresh').addEventListener('click', () => void refreshLibrary())
void refreshLibrary()
renderQueue()
