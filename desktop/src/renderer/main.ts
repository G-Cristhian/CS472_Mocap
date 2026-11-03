/** The page: pick videos, check them, run, watch the bar, then play the result and read the numbers. */
import { parseClapTimes } from '../shared/clapTimes'
import { metricSections, summarise, type RunSummary } from '../shared/metrics'
import type { Backend, CheckResult, Progress, RunOptions, Smoother, VideoFile } from '../shared/types'
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
const runsBox = $('runs-box')
const runsTable = $<HTMLTableElement>('runs')
const rerunButton = $<HTMLButtonElement>('rerun-smoother')

if (!inElectron) $('python-note').textContent = 'browser preview with a mocked pipeline'

interface Picked extends VideoFile {
  use: boolean
}
interface PastRun {
  summary: RunSummary
  outDir: string
}
let videoDir: string | null = null
let picked: Picked[] = []
let chosenKey = '[]' // the chosen videos in camera order, as the clap times and the check result were made for
let chooseSeq = 0 // the latest folder choice; an older one that finishes late is dropped
let checkSeq = 0 // the latest check; a check whose selection has changed since is dropped
let checking = false
let outDir = ''
let viewer: BvhViewer | null = null
let lastOptions: RunOptions | null = null
let runs: PastRun[] = []

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
    $<HTMLInputElement>('outdir').value = outDir
  }
  renderVideos()
})

$('clap-times').addEventListener('input', () => {
  clapNote.textContent = ''
})
$('clap-threshold').addEventListener('input', () => {
  // a check result was made with the old threshold
  checkBox.hidden = true
})

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
  return {
    videos,
    heightM,
    fov,
    outDir,
    detector: $<HTMLSelectElement>('detector').value as RunOptions['detector'],
    smoother: $<HTMLSelectElement>('smoother').value as RunOptions['smoother'],
    clapThreshold,
    clapTimes,
    jobs,
    recalibrate: $<HTMLInputElement>('recalibrate').checked,
    resume: $<HTMLInputElement>('resume').checked,
  }
}

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

async function startRun(options: RunOptions): Promise<void> {
  setupError.textContent = ''
  clapNote.textContent = ''
  setup.hidden = true
  preview.hidden = true
  progressPanel.hidden = false
  log.textContent = ''
  showProgress({ stage: 'starting', fraction: 0, detail: 'Starting the pipeline', videos: [] })
  $<HTMLButtonElement>('cancel').disabled = false
  lastOptions = options

  const offLog = backend.onLog(appendLog)
  const offProgress = backend.onProgress(showProgress)
  let result
  try {
    result = await backend.run(options)
  } catch (e) {
    result = { ok: false, exitCode: null, error: e instanceof Error ? e.message : String(e) }
  } finally {
    offLog()
    offProgress()
  }
  $<HTMLButtonElement>('cancel').disabled = true

  if (!result.ok) {
    showProgress({ ...currentProgress(), stage: 'failed', detail: result.error ?? 'Failed' })
    preview.hidden = false
    resultError.textContent = result.error ?? 'The pipeline failed. The log above has the details.'
    $<HTMLDetailsElement>('log-box').open = true
    metricsBox.replaceChildren()
    rerunButton.disabled = true
    return
  }
  showProgress({ ...currentProgress(), stage: 'done', fraction: 1, detail: 'Finished' })
  await showResult(result.bvhPath, result.metricsPath)
}

let latestProgress: Progress = { stage: 'starting', fraction: 0, detail: '', videos: [] }
function currentProgress(): Progress {
  return latestProgress
}
backend.onProgress((p) => {
  latestProgress = p
})

runButton.addEventListener('click', () => {
  const options = readOptions()
  if (typeof options === 'string') {
    setupError.textContent = options
    return
  }
  void startRun(options)
})

$('cancel').addEventListener('click', () => void backend.cancel())

// ---- 3. preview -----------------------------------------------------------------------------

function fmt(t: number): string {
  return t.toFixed(2)
}

async function showResult(bvhPath?: string, metricsPath?: string): Promise<void> {
  preview.hidden = false
  resultError.textContent = ''
  rerunButton.disabled = false
  if (!viewer) {
    viewer = new BvhViewer($('viewer'))
    if (!inElectron) (window as unknown as { viewer?: BvhViewer }).viewer = viewer   // for poking at it in the browser preview
    viewer.onTime = (t) => {
      timeSlider.value = String(Math.round((t / viewer!.duration) * 1000))
      clockLabel.textContent = `${fmt(t)} / ${fmt(viewer!.duration)} s`
    }
  }
  if (!bvhPath) {
    resultError.textContent = 'The run finished but printed no BVH path (was --no-bvh used?).'
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
  await showMetrics(metricsPath)
}

async function showMetrics(metricsPath?: string): Promise<void> {
  metricsBox.replaceChildren()
  if (!metricsPath) return
  let m: Record<string, unknown>
  try {
    m = JSON.parse(await backend.readText(metricsPath))
  } catch {
    return
  }
  for (const section of metricSections(m)) {
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
      dl.append(div)
    }
    const wrap = document.createElement('div')
    wrap.append(h, dl)
    metricsBox.append(wrap)
  }
  if (lastOptions) {
    // a new take (another output folder) starts the comparison afresh
    if (runs.length && runs[0].outDir !== lastOptions.outDir) runs = []
    runs.push({ summary: summarise(m), outDir: lastOptions.outDir })
  }
  renderRuns()
}

function renderRuns(): void {
  runsBox.hidden = runs.length < 2
  runsTable.replaceChildren()
  if (runs.length < 2) return
  const columns: [string, (s: RunSummary) => string][] = [
    ['Run', () => ''],
    ['Smoother', (s) => s.smoother],
    ['Detector', (s) => s.detector],
    ['Jitter raw → smoothed (mm/frame²)', (s) => `${s.jitterRawMm?.toFixed(1) ?? '–'} → ${s.jitterFinalMm?.toFixed(1) ?? '–'}`],
    ['Bone spread (mm)', (s) => s.boneSpreadMm?.toFixed(1) ?? '–'],
    ['Calibration worst (px)', (s) => s.calibrationWorstPx?.toFixed(2) ?? '–'],
    ['Missing (%)', (s) => s.missingPercent?.toFixed(1) ?? '–'],
    ['Time (s)', (s) => s.totalS?.toFixed(0) ?? '–'],
  ]
  const head = document.createElement('tr')
  for (const [title] of columns) {
    const th = document.createElement('th')
    th.textContent = title
    head.append(th)
  }
  runsTable.append(head)
  runs.forEach((r, i) => {
    const tr = document.createElement('tr')
    if (i === runs.length - 1) tr.className = 'current'
    columns.forEach(([, cell], c) => {
      const td = document.createElement('td')
      td.textContent = c === 0 ? String(i + 1) : cell(r.summary)
      tr.append(td)
    })
    runsTable.append(tr)
  })
}

rerunButton.addEventListener('click', () => {
  if (!lastOptions) return
  const other: Smoother = lastOptions.smoother === 'savgol' ? 'butterworth' : 'savgol'
  // resume reuses the joints, clap times, calibration and 3D points; only smoothing and the rig rerun
  const options: RunOptions = { ...lastOptions, smoother: other, resume: true, recalibrate: false }
  $<HTMLSelectElement>('smoother').value = other
  $<HTMLInputElement>('resume').checked = true
  $<HTMLInputElement>('recalibrate').checked = false
  updateHeightNote()
  viewer?.pause()
  void startRun(options)
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
  viewer.pause()
  playButton.textContent = 'Play'
  const t = (Number(timeSlider.value) / 1000) * viewer.duration
  viewer.setTime(t)
  clockLabel.textContent = `${fmt(t)} / ${fmt(viewer.duration)} s`
})

$('open-folder').addEventListener('click', () => {
  if (lastOptions) void backend.openFolder(lastOptions.outDir)
})

$('again').addEventListener('click', () => {
  viewer?.pause()
  preview.hidden = true
  progressPanel.hidden = true
  setup.hidden = false
  if (videoDir) renderVideos()
})
