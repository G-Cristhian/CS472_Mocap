/** The page: pick videos, run, watch the bar, then play the result. */
import type { Backend, Progress, RunOptions, VideoFile } from '../shared/types'
import { BvhViewer } from './viewer'

const backend: Backend = (window as unknown as { backend?: Backend }).backend ?? (await import('./mock')).mock
const inElectron = 'backend' in window

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T
const setup = $('setup')
const progressPanel = $('progress')
const preview = $('preview')
const videoList = $<HTMLUListElement>('videos')
const folderLabel = $('folder')
const runButton = $<HTMLButtonElement>('run')
const setupError = $('setup-error')
const bar = $<HTMLProgressElement>('bar')
const stageLabel = $('stage')
const detailLabel = $('detail')
const log = $<HTMLPreElement>('log')
const resultError = $('result-error')
const timeSlider = $<HTMLInputElement>('time')
const clockLabel = $('clock')
const playButton = $<HTMLButtonElement>('play')
const metricsList = $<HTMLDListElement>('metrics')

if (!inElectron) $('python-note').textContent = 'browser preview with a mocked pipeline'

interface Picked extends VideoFile {
  use: boolean
}
let videoDir: string | null = null
let picked: Picked[] = []
let outDir = ''
let viewer: BvhViewer | null = null
let lastResultDir = ''

// ---- 1. setup --------------------------------------------------------------------------

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
  setupError.textContent = picked.length && chosen < 2 ? 'Pick at least two videos.' : ''
}

$('choose').addEventListener('click', async () => {
  const dir = await backend.chooseDirectory()
  if (!dir) return
  videoDir = dir
  folderLabel.textContent = dir
  const videos = await backend.listVideos(dir)
  picked = videos.map((v) => ({ ...v, use: true }))
  outDir = await backend.defaultOutDir(dir)
  $<HTMLInputElement>('outdir').value = outDir
  if (!videos.length) setupError.textContent = 'No .mov or .mp4 files in that folder.'
  renderVideos()
})

function readOptions(): RunOptions | string {
  const videos = picked.filter((p) => p.use).map((p) => p.path)
  const heightM = Number($<HTMLInputElement>('height').value)
  const fov = Number($<HTMLInputElement>('fov').value)
  outDir = $<HTMLInputElement>('outdir').value.trim()
  if (videos.length < 2) return 'Pick at least two videos.'
  if (!(heightM >= 1 && heightM <= 2.5)) return 'Height must be between 1 and 2.5 metres.'
  if (!(fov >= 30 && fov <= 120)) return 'Field of view must be between 30 and 120 degrees.'
  if (!outDir) return 'Give an output folder.'
  return {
    videos,
    heightM,
    fov,
    outDir,
    detector: $<HTMLSelectElement>('detector').value as RunOptions['detector'],
    smoother: $<HTMLSelectElement>('smoother').value as RunOptions['smoother'],
    recalibrate: $<HTMLInputElement>('recalibrate').checked,
    resume: $<HTMLInputElement>('resume').checked,
  }
}

// ---- 2. progress -------------------------------------------------------------------------

function showProgress(p: Progress): void {
  bar.value = Math.round(p.fraction * 1000)
  stageLabel.textContent = p.stage
  stageLabel.className = `pill ${p.stage === 'done' || p.stage === 'failed' ? p.stage : ''}`
  detailLabel.textContent = p.detail
}

function appendLog(line: string): void {
  log.textContent += line + '\n'
  if (log.textContent.length > 200_000) log.textContent = log.textContent.slice(-150_000)
  log.scrollTop = log.scrollHeight
}

runButton.addEventListener('click', async () => {
  const options = readOptions()
  if (typeof options === 'string') {
    setupError.textContent = options
    return
  }
  setupError.textContent = ''
  setup.hidden = true
  preview.hidden = true
  progressPanel.hidden = false
  log.textContent = ''
  showProgress({ stage: 'starting', fraction: 0, detail: 'Starting the pipeline' })
  $<HTMLButtonElement>('cancel').disabled = false

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
  lastResultDir = options.outDir

  if (!result.ok) {
    showProgress({ stage: 'failed', fraction: bar.value / 1000, detail: result.error ?? 'Failed' })
    preview.hidden = false
    resultError.textContent = result.error ?? 'The pipeline failed. The log above has the details.'
    $<HTMLDetailsElement>('log-box').open = true
    metricsList.replaceChildren()
    return
  }
  showProgress({ stage: 'done', fraction: 1, detail: 'Finished' })
  await showResult(result.bvhPath, result.metricsPath)
})

$('cancel').addEventListener('click', () => void backend.cancel())

// ---- 3. preview -----------------------------------------------------------------------------

function fmt(t: number): string {
  return t.toFixed(2)
}

async function showResult(bvhPath?: string, metricsPath?: string): Promise<void> {
  preview.hidden = false
  resultError.textContent = ''
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
  metricsList.replaceChildren()
  if (!metricsPath) return
  let m: Record<string, Record<string, unknown>>
  try {
    m = JSON.parse(await backend.readText(metricsPath))
  } catch {
    return
  }
  const errors = (m.calibrate?.reprojection_error_px ?? {}) as Record<string, number>
  const worst = Math.max(...Object.values(errors), 0)
  const boneStd = Number((m.rig?.bone_lengths as { mean_std_m?: number } | undefined)?.mean_std_m ?? NaN)
  const missing = Number(m.pose_final?.missing_fraction ?? NaN)
  const upright = Number(m.scale?.upright_frames ?? NaN)
  const total = Number(m.timing?.total_s ?? NaN)
  const rows: [string, string, 'good' | 'bad' | ''][] = [
    ['Calibration error, worst camera', `${worst.toFixed(2)} px`, worst < 3 ? 'good' : worst > 10 ? 'bad' : ''],
    ['Bone length spread', isNaN(boneStd) ? '–' : `${(boneStd * 1000).toFixed(1)} mm`, boneStd < 0.01 ? 'good' : boneStd > 0.02 ? 'bad' : ''],
    ['Joints missing', isNaN(missing) ? '–' : `${(missing * 100).toFixed(1)} %`, missing < 0.05 ? 'good' : missing > 0.15 ? 'bad' : ''],
    ['Upright frames for height', isNaN(upright) ? '–' : String(upright), upright >= 30 ? 'good' : upright < 10 ? 'bad' : ''],
    ['Total time', isNaN(total) ? '–' : `${total.toFixed(0)} s`, ''],
  ]
  for (const [label, value, cls] of rows) {
    const div = document.createElement('div')
    const dt = document.createElement('dt')
    dt.textContent = label
    const dd = document.createElement('dd')
    dd.textContent = value
    dd.className = cls
    div.append(dt, dd)
    metricsList.append(div)
  }
}

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
  if (lastResultDir) void backend.openFolder(lastResultDir)
})

$('again').addEventListener('click', () => {
  viewer?.pause()
  preview.hidden = true
  progressPanel.hidden = true
  setup.hidden = false
  if (videoDir) renderVideos()
})
