/**
 * The result panel's frame-by-frame parts, from the run's report
 * (src/shared/report.ts): the key for the skeleton's colours, each camera's
 * 2D view side by side, the timelines of camera error and lost joints, and the
 * camera and joint stories. update(t) follows the player; clicking a timeline
 * calls onSeek.
 */
import { LIMITS } from '../shared/metrics'
import {
  bodyStory,
  cameraLines,
  cameraStory,
  colourKey,
  findFlags,
  flagDetails,
  flagTitle,
  isMajor,
  jointState,
  type Flag,
  frameAt,
  frameCount,
  GLOSSARY,
  jointLines,
  jointStory,
  lostPerFrame,
  mmScale,
  performerBox,
  prettyJoint,
  STATE_COLOURS,
  wireIndices,
  type ColourMode,
  type Point,
  type Report,
} from '../shared/report'

const CHART_LEFT = 44
const CHART_RIGHT = 8
const JOINT_ROW = 10
const FLAG_STRIP = 14

/** "RIGHT_FOOT_INDEX" -> "R toes", for the joint chart's narrow label column */
function shortJoint(name: string): string {
  return prettyJoint(name).replace(/^left /, 'L ').replace(/^right /, 'R ').replace(' eye inner', ' eye in').replace(' eye outer', ' eye out')
}

/** One colour per camera, the same in the 3D view, the 2D views and the timeline; none is a key colour. */
export const CAMERA_COLOURS = ['#4c8dff', '#39c5cf', '#db61a2', '#e6edf3', '#bc8cff', '#f0883e']
export const cameraColour = (i: number) => CAMERA_COLOURS[i % CAMERA_COLOURS.length]

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T

function el<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string, className?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag)
  if (text !== undefined) e.textContent = text
  if (className) e.className = className
  return e
}

const pct = (f: number) => `${(f * 100).toFixed(f < 0.1 ? 1 : 0)} %`
const valid = (p: Point | undefined): p is [number, number] => !!p && p[0] !== null && p[1] !== null

function gradeOf(px: number | null): string {
  if (px === null) return ''
  return px <= LIMITS.px.good ? 'good' : px >= LIMITS.px.bad ? 'bad' : 'mid'
}

export class ReportPanel {
  report: Report | null = null
  mode: ColourMode = 'error'
  onSeek: (t: number) => void = () => {}
  onModeChange: () => void = () => {}
  private frame = -1
  private readonly modeSelect = $<HTMLSelectElement>('colour-mode')
  private readonly key = $<HTMLUListElement>('colour-key')
  private readonly note = $('report-note')
  private readonly parts = $('report-parts')
  private readonly camViews = $('cam-views')
  private readonly wholePicture = $<HTMLInputElement>('whole-picture')
  private boxes: { x: number; y: number; w: number; h: number }[] = []
  private readonly timeline = $<HTMLCanvasElement>('timeline')
  private readonly timelineLegend = $('timeline-legend')
  private readonly atNow = $('at-now')
  private readonly jointChart = $<HTMLCanvasElement>('joint-chart')
  private readonly flagBox = $('flags')
  private flags: Flag[] = []
  private flagItems: HTMLElement[] = []
  private readonly cameraStoryBox = $('camera-story')
  private readonly jointStoryBox = $('joint-story')
  private canvases: HTMLCanvasElement[] = []
  private camTitles: HTMLElement[] = []
  private lost: number[] = []
  private duration = 0

  constructor() {
    this.modeSelect.addEventListener('change', () => {
      this.mode = this.modeSelect.value as ColourMode
      this.renderKey()
      this.onModeChange()
    })
    for (const canvas of [this.timeline, this.jointChart]) {
      canvas.addEventListener('click', (e) => {
        if (!this.report) return
        const box = canvas.getBoundingClientRect()
        // both charts plot time between a 44 px label column on the left and 8 px on the right
        const x = (e.clientX - box.left - CHART_LEFT) / (box.width - CHART_LEFT - CHART_RIGHT)
        this.onSeek(Math.max(0, Math.min(1, x)) * (frameCount(this.report) - 1) / this.report.fps)
      })
    }
    new ResizeObserver(() => this.redraw()).observe(this.parts)
    this.wholePicture.addEventListener('change', () => {
      if (!this.report) return
      this.buildCameraViews()
      this.redraw()
    })
    const glossary = $('glossary-list')
    for (const g of GLOSSARY) glossary.append(el('dt', g.term), el('dd', g.text))
    this.renderKey()
  }

  clear(message: string): void {
    this.report = null
    this.frame = -1
    this.note.textContent = message
    this.parts.hidden = true
    this.renderKey()
  }

  show(r: Report, duration: number): void {
    this.report = r
    this.duration = duration || frameCount(r) / r.fps
    this.frame = -1
    this.note.textContent = ''
    this.parts.hidden = false
    this.lost = lostPerFrame(r)
    this.flags = findFlags(r)
    this.renderFlags()
    this.renderKey()
    this.buildCameraViews()
    this.renderStories()
    this.redraw()
  }

  update(t: number): void {
    if (!this.report) return
    const f = frameAt(this.report, t)
    if (f === this.frame) return
    this.frame = f
    this.drawCameraViews()
    this.drawTimeline()
    this.drawJointChart()
    this.renderNow()
  }

  private redraw(): void {
    if (!this.report) return
    this.jointChart.style.height = `${this.report.joints.length * JOINT_ROW + FLAG_STRIP + 22}px`
    this.sizeCanvases()
    this.drawCameraViews()
    this.drawTimeline()
    this.drawJointChart()
    this.renderNow()
  }

  private renderKey(): void {
    this.key.replaceChildren()
    const entries = colourKey(this.mode, this.report)
    if (!entries.length) this.key.append(el('li', 'every joint in one colour', 'muted'))
    for (const e of entries) {
      const li = el('li')
      const swatch = el('span', '', 'swatch')
      swatch.style.background = STATE_COLOURS[e.state]
      li.append(swatch, document.createTextNode(e.label))
      this.key.append(li)
    }
    if (!this.report && this.mode !== 'plain') this.key.append(el('li', 'colours need the frame-by-frame numbers, not available for this run', 'muted'))
  }

  // ---- each camera's 2D view ----

  private buildCameraViews(): void {
    const r = this.report!
    this.camViews.replaceChildren()
    this.canvases = []
    this.camTitles = []
    this.boxes = r.cameras.map((cam, i) => {
      const whole = { x: 0, y: 0, w: cam.width, h: cam.height }
      return this.wholePicture.checked ? whole : performerBox(r, i) ?? whole
    })
    r.cameras.forEach((cam, i) => {
      const box = el('figure', undefined, 'cam-view')
      const title = el('figcaption')
      title.style.color = cameraColour(i)
      const canvas = el('canvas')
      canvas.style.aspectRatio = `${this.boxes[i].w} / ${this.boxes[i].h}`
      box.append(title, canvas)
      this.camViews.append(box)
      this.canvases.push(canvas)
      this.camTitles.push(title)
    })
  }

  private sizeCanvases(): void {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    for (const c of [...this.canvases, this.timeline, this.jointChart]) {
      const w = Math.max(1, Math.round(c.clientWidth * dpr))
      const h = Math.max(1, Math.round(c.clientHeight * dpr))
      if (c.width !== w || c.height !== h) {
        c.width = w
        c.height = h
      }
    }
  }

  private drawCameraViews(): void {
    const r = this.report
    if (!r) return
    const f = Math.max(0, this.frame)
    const wires = wireIndices(r)
    r.cameras.forEach((cam, i) => {
      const canvas = this.canvases[i]
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const pc = r.per_camera[i]
      const view = this.boxes[i]
      const s = canvas.width / view.w
      ctx.fillStyle = '#0e1116'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      const seen = pc.points[f] ?? []
      const back = pc.reprojected[f] ?? []
      const xy = (p: [number, number]): [number, number] => [(p[0] - view.x) * s, (p[1] - view.y) * s]
      // the gap between what the detector saw and where the 3D joint lands: the reprojection error
      for (let j = 0; j < r.joints.length; j++) {
        const a = seen[j]
        const b = back[j]
        if (!valid(a) || !valid(b)) continue
        const px = Math.hypot(a[0] - b[0], a[1] - b[1])
        ctx.strokeStyle = STATE_COLOURS[px <= LIMITS.px.good ? 'good' : px >= LIMITS.px.bad ? 'bad' : 'mid']
        ctx.lineWidth = 2
        ctx.setLineDash([])
        ctx.beginPath()
        ctx.moveTo(...xy(a))
        ctx.lineTo(...xy(b))
        ctx.stroke()
      }
      const drawWires = (pts: Point[], colour: string, dash: number[], width: number) => {
        ctx.strokeStyle = colour
        ctx.lineWidth = width
        ctx.setLineDash(dash)
        ctx.beginPath()
        for (const [a, b] of wires) {
          const p = pts[a]
          const q = pts[b]
          if (!valid(p) || !valid(q)) continue
          ctx.moveTo(...xy(p))
          ctx.lineTo(...xy(q))
        }
        ctx.stroke()
      }
      drawWires(back, 'rgba(230,237,243,0.75)', [5, 4], 1.5)
      drawWires(seen, cameraColour(i), [], 2.5)
      ctx.setLineDash([])
      ctx.fillStyle = cameraColour(i)
      for (const p of seen) {
        if (!valid(p)) continue
        ctx.beginPath()
        ctx.arc(...xy(p), 2.5, 0, Math.PI * 2)
        ctx.fill()
      }
      const err = pc.error_px[f]
      const mm = pc.error_mm[f]
      this.camTitles[i].replaceChildren(
        document.createTextNode(cam.id + '  '),
        el(
          'span',
          pc.seen[f] === 0 ? 'no one seen' : err === null || err === undefined ? '–' : `${err.toFixed(1)} px${mm === null || mm === undefined ? '' : ` ≈ ${mm.toFixed(0)} mm`}`,
          pc.seen[f] === 0 ? 'bad' : gradeOf(err ?? null),
        ),
      )
    })
  }

  // ---- the timeline: each camera's error, and the joints with no 3D point ----

  private drawTimeline(): void {
    const r = this.report
    const canvas = this.timeline
    const ctx = canvas.getContext('2d')
    if (!r || !ctx) return
    const W = canvas.width
    const H = canvas.height
    const dpr = W / Math.max(1, canvas.clientWidth)
    const n = frameCount(r)
    const left = CHART_LEFT * dpr
    const right = CHART_RIGHT * dpr
    const topH = H * 0.58
    const gap = 22 * dpr
    const botTop = topH + gap
    const botH = H - botTop - 14 * dpr
    const x = (f: number) => left + ((W - left - right) * f) / Math.max(1, n - 1)
    ctx.clearRect(0, 0, W, H)
    ctx.font = `${11 * dpr}px system-ui, sans-serif`
    ctx.textBaseline = 'middle'
    this.drawFlagBands(ctx, x, 0, H - 14 * dpr, dpr)

    // top: millimetres apart per camera, with the guide's limits drawn at the median scale
    const scale = mmScale(r).median
    let maxMm = 0
    for (const pc of r.per_camera) for (const v of pc.error_mm) if (v !== null && v > maxMm) maxMm = v
    if (scale) maxMm = Math.max(maxMm, LIMITS.px.bad * scale * 1.15)
    maxMm = Math.max(5, Math.ceil(maxMm / 5) * 5)
    const yTop = (mm: number) => 6 * dpr + (topH - 6 * dpr) * (1 - Math.min(mm, maxMm) / maxMm)
    ctx.fillStyle = '#8b949e'
    ctx.fillText(`${maxMm} mm`, 2 * dpr, yTop(maxMm) + 5 * dpr)
    ctx.fillText('0', 2 * dpr, yTop(0))
    if (scale) {
      for (const [px, state] of [[LIMITS.px.good, 'good'], [LIMITS.px.bad, 'bad']] as const) {
        const y = yTop(px * scale)
        ctx.strokeStyle = STATE_COLOURS[state]
        ctx.globalAlpha = 0.6
        ctx.setLineDash([4 * dpr, 4 * dpr])
        ctx.lineWidth = 1 * dpr
        ctx.beginPath()
        ctx.moveTo(left, y)
        ctx.lineTo(W - right, y)
        ctx.stroke()
        ctx.globalAlpha = 1
        ctx.setLineDash([])
        ctx.fillStyle = STATE_COLOURS[state]
        ctx.fillText(`${px} px`, 2 * dpr, y)
      }
    }
    r.per_camera.forEach((pc, i) => {
      ctx.strokeStyle = cameraColour(i)
      ctx.lineWidth = 1.5 * dpr
      ctx.beginPath()
      let pen = false
      pc.error_mm.forEach((v, f) => {
        if (v === null) {
          pen = false
          return
        }
        if (pen) ctx.lineTo(x(f), yTop(v))
        else ctx.moveTo(x(f), yTop(v))
        pen = true
      })
      ctx.stroke()
    })

    // bottom: joints with no 3D point per frame (bars), and a strip per camera where it saw no one
    const maxLost = Math.max(1, ...this.lost)
    ctx.fillStyle = '#8b949e'
    ctx.fillText('lost', 2 * dpr, botTop + 4 * dpr)
    ctx.fillStyle = STATE_COLOURS.none
    const barW = Math.max(1, (W - left - right) / n)
    const stripH = 4 * dpr
    const barArea = botH - r.cameras.length * (stripH + 2 * dpr)
    this.lost.forEach((v, f) => {
      if (!v) return
      const h = (barArea * v) / maxLost
      ctx.fillRect(x(f) - barW / 2, botTop + barArea - h, barW, h)
    })
    ctx.fillStyle = '#8b949e'
    ctx.fillText(String(maxLost), 2 * dpr, botTop + 14 * dpr)
    r.per_camera.forEach((pc, i) => {
      const y = botTop + barArea + 2 * dpr + i * (stripH + 2 * dpr)
      ctx.fillStyle = '#242a33'
      ctx.fillRect(left, y, W - left - right, stripH)
      ctx.fillStyle = cameraColour(i)
      pc.seen.forEach((v, f) => {
        if (v === 0) ctx.fillRect(x(f) - barW / 2, y, barW, stripH)
      })
    })

    // the time axis and the cursor
    ctx.fillStyle = '#8b949e'
    const seconds = n / r.fps
    const step = seconds > 60 ? 10 : seconds > 20 ? 5 : seconds > 6 ? 2 : 1
    ctx.textAlign = 'center'
    for (let t = 0; t <= seconds; t += step) ctx.fillText(`${t} s`, x(t * r.fps), H - 6 * dpr)
    ctx.textAlign = 'left'
    if (this.frame >= 0) {
      ctx.strokeStyle = '#e6e8eb'
      ctx.lineWidth = 1 * dpr
      ctx.beginPath()
      ctx.moveTo(x(this.frame), 0)
      ctx.lineTo(x(this.frame), H - 14 * dpr)
      ctx.stroke()
    }
  }

  /** The flags as shaded bands behind a chart, the big ones numbered like the list. */
  private drawFlagBands(ctx: CanvasRenderingContext2D, x: (f: number) => number, top: number, bottom: number, dpr: number): void {
    let number = 0
    for (const flag of this.flags) {
      const major = isMajor(flag)
      if (major) number++
      const colour = flag.kind === 'lost' ? STATE_COLOURS.none : STATE_COLOURS.bad
      ctx.globalAlpha = major ? 0.16 : 0.07
      ctx.fillStyle = colour
      const x0 = x(flag.startFrame - 0.5)
      const x1 = x(flag.endFrame + 0.5)
      ctx.fillRect(x0, top, Math.max(1, x1 - x0), bottom - top)
      ctx.globalAlpha = 1
      if (major) {
        ctx.fillStyle = colour
        ctx.textAlign = 'center'
        ctx.fillText(String(number), (x0 + x1) / 2, top + 8 * dpr)
        ctx.textAlign = 'left'
      }
    }
  }

  /** Every tracked joint as a row over time: purple where it had no 3D position, red where the cameras were 10 px or more apart. */
  private drawJointChart(): void {
    const r = this.report
    const canvas = this.jointChart
    const ctx = canvas.getContext('2d')
    if (!r || !ctx) return
    const W = canvas.width
    const H = canvas.height
    const dpr = W / Math.max(1, canvas.clientWidth)
    const n = frameCount(r)
    const left = CHART_LEFT * dpr
    const right = CHART_RIGHT * dpr
    const row = JOINT_ROW * dpr
    const x = (f: number) => left + ((W - left - right) * f) / Math.max(1, n - 1)
    const w = Math.max(1, (W - left - right) / n)
    const strip = FLAG_STRIP * dpr
    ctx.clearRect(0, 0, W, H)
    ctx.font = `${9 * dpr}px system-ui, sans-serif`
    ctx.textBaseline = 'middle'
    // the flags as a numbered strip on top, the big ones like the list
    ctx.fillStyle = '#8b949e'
    ctx.fillText('flags', 2 * dpr, strip / 2)
    let number = 0
    for (const flag of this.flags) {
      const major = isMajor(flag)
      if (major) number++
      const x0 = x(flag.startFrame - 0.5)
      const x1 = x(flag.endFrame + 0.5)
      ctx.fillStyle = flag.kind === 'lost' ? STATE_COLOURS.none : STATE_COLOURS.bad
      ctx.globalAlpha = major ? 0.9 : 0.35
      ctx.fillRect(x0, major ? 1 * dpr : strip * 0.6, Math.max(1, x1 - x0), major ? strip - 3 * dpr : strip * 0.25)
      ctx.globalAlpha = 1
      if (major && x1 - x0 > 8 * dpr) {
        ctx.fillStyle = '#0e1116'
        ctx.textAlign = 'center'
        ctx.fillText(String(number), (x0 + x1) / 2, strip / 2 - 1 * dpr)
        ctx.textAlign = 'left'
      }
    }
    // one row per joint: only the trouble, so it stands out
    r.joints.forEach((name, j) => {
      const y = strip + j * row
      ctx.fillStyle = j % 2 ? '#14181d' : '#181c22'
      ctx.fillRect(left, y, W - left - right, row)
      ctx.fillStyle = '#8b949e'
      ctx.fillText(shortJoint(name), 2 * dpr, y + row / 2)
      for (let f = 0; f < n; f++) {
        const state = jointState(r, f, j, 'error')
        if (state !== 'none' && state !== 'bad') continue
        ctx.fillStyle = STATE_COLOURS[state]
        ctx.fillRect(x(f) - w / 2, y + 1 * dpr, w, row - 2 * dpr)
      }
    })
    ctx.fillStyle = '#8b949e'
    const seconds = n / r.fps
    const step = seconds > 60 ? 10 : seconds > 20 ? 5 : seconds > 6 ? 2 : 1
    ctx.font = `${11 * dpr}px system-ui, sans-serif`
    ctx.textAlign = 'center'
    for (let t = 0; t <= seconds; t += step) ctx.fillText(`${t} s`, x(t * r.fps), H - 8 * dpr)
    ctx.textAlign = 'left'
    if (this.frame >= 0) {
      ctx.strokeStyle = '#e6e8eb'
      ctx.lineWidth = 1 * dpr
      ctx.beginPath()
      ctx.moveTo(x(this.frame), 0)
      ctx.lineTo(x(this.frame), strip + r.joints.length * row)
      ctx.stroke()
    }
    // the flag the cursor is in, highlighted in the list
    this.flagItems.forEach((item, k) => {
      const flag = this.flags[Number(item.dataset.flag)]
      item.classList.toggle('current', !!flag && this.frame >= flag.startFrame && this.frame <= flag.endFrame)
      void k
    })
  }

  private renderFlags(): void {
    const r = this.report!
    this.flagBox.replaceChildren()
    this.flagItems = []
    const major = this.flags.filter(isMajor)
    const minor = this.flags.filter((f) => !isMajor(f))
    const jump = (flag: Flag) => this.onSeek(flag.start)
    if (!this.flags.length) {
      this.flagBox.append(el('p', 'No flags: no joint was lost, or had the cameras 10 px or more apart, for 0.1 s or longer.'))
      return
    }
    this.flagBox.append(
      el('p', `${major.length} flag${major.length === 1 ? '' : 's'} worth reading, ${minor.length} smaller. `
        + 'A flag is a stretch where joints had no 3D position or the cameras were 10 px or more apart on them, for 0.1 s or longer. Click one to jump there.', 'note'),
    )
    const list = el('ol', undefined, 'flags')
    for (const flag of major) {
      const li = el('li')
      li.dataset.flag = String(this.flags.indexOf(flag))
      const title = el('button', flagTitle(flag, r), 'link ' + (flag.kind === 'lost' ? 'lost' : 'spike'))
      title.addEventListener('click', () => jump(flag))
      const details = el('ul')
      for (const d of flagDetails(flag)) details.append(el('li', d))
      li.append(title, details)
      list.append(li)
      this.flagItems.push(li)
    }
    this.flagBox.append(list)
    if (minor.length) {
      const more = el('details')
      more.append(el('summary', `${minor.length} smaller flag${minor.length === 1 ? '' : 's'}`))
      const small = el('ul', undefined, 'flags small')
      for (const flag of minor) {
        const li = el('li')
        li.dataset.flag = String(this.flags.indexOf(flag))
        const title = el('button', flagTitle(flag, r), 'link ' + (flag.kind === 'lost' ? 'lost' : 'spike'))
        title.title = flagDetails(flag).join(' ')
        title.addEventListener('click', () => jump(flag))
        li.append(title)
        small.append(li)
        this.flagItems.push(li)
      }
      more.append(small)
      this.flagBox.append(more)
    }
  }

  private renderNow(): void {
    const r = this.report
    if (!r) return
    const f = Math.max(0, this.frame)
    const t = r.times[f] ?? f / r.fps
    const lostNames = r.joints.filter((_, j) => (r.joint_views[f]?.[j] ?? 0) === 0).map(prettyJoint)
    const cams = r.per_camera.map((pc) =>
      pc.seen[f] === 0 ? `${pc.id} saw no one` : `${pc.id} ${pc.error_mm[f] === null ? '–' : `${pc.error_mm[f]!.toFixed(0)} mm`}`,
    )
    this.atNow.textContent =
      `At ${t.toFixed(2)} s: ${cams.join(', ')}; `
      + (lostNames.length ? `no 3D position for ${lostNames.join(', ')}.` : 'every joint has a 3D position.')
  }

  // ---- the stories ----

  private renderStories(): void {
    const r = this.report!
    this.timelineLegend.replaceChildren()
    r.cameras.forEach((cam, i) => {
      const li = el('li')
      const sw = el('span', '', 'swatch line')
      sw.style.background = cameraColour(i)
      li.append(sw, document.createTextNode(cam.id))
      this.timelineLegend.append(li)
    })
    const lostLi = el('li')
    const lostSw = el('span', '', 'swatch')
    lostSw.style.background = STATE_COLOURS.none
    lostLi.append(lostSw, document.createTextNode('joints with no 3D position (bars); a camera’s strip lights where it saw no one'))
    this.timelineLegend.append(lostLi)

    // cameras
    this.cameraStoryBox.replaceChildren()
    for (const s of cameraStory(r)) this.cameraStoryBox.append(el('p', s))
    const table = el('table', undefined, 'runs')
    const head = el('tr')
    for (const h of ['Camera', 'From the 3D skeleton', 'Calibration error', 'Saw no one', 'Distance', 'Worst joints']) head.append(el('th', h))
    table.append(head)
    const lines = cameraLines(r)
    for (const line of lines) {
      const tr = el('tr')
      const i = r.cameras.findIndex((c) => c.id === line.id)
      const name = el('td', line.id)
      name.style.color = cameraColour(i)
      const mm = (px: number | null) => (px !== null && line.mmPerPx ? ` ≈ ${(px * line.mmPerPx).toFixed(0)} mm` : '')
      tr.append(
        name,
        el('td', line.errorPx === null ? '–' : `${line.errorPx.toFixed(1)} px${line.errorMm === null ? '' : ` ≈ ${line.errorMm.toFixed(0)} mm`}`, gradeOf(line.errorPx)),
        el('td', line.calibrationPx === null ? '–' : `${line.calibrationPx.toFixed(1)} px${mm(line.calibrationPx)}`, gradeOf(line.calibrationPx)),
        el('td', pct(line.lostFraction)),
        el('td', line.distanceM === null ? '–' : `${line.distanceM.toFixed(1)} m`),
        el('td', line.worstJoints.map((w) => `${prettyJoint(w.joint)} ${w.px.toFixed(0)} px`).join(', ')),
      )
      table.append(tr)
    }
    const wrap = el('div', undefined, 'table-wrap')
    wrap.append(table)
    this.cameraStoryBox.append(wrap)

    // joints
    this.jointStoryBox.replaceChildren()
    const joints = jointLines(r)
    const body = bodyStory(joints)
    if (body) this.jointStoryBox.append(el('p', body))
    const list = el('ol', undefined, 'stories')
    for (const line of joints.slice(0, 4)) list.append(el('li', jointStory(line, frameCount(r))))
    this.jointStoryBox.append(list)
    const all = el('details')
    all.append(el('summary', `Every joint (${joints.length})`))
    const jt = el('table', undefined, 'runs')
    const jh = el('tr')
    for (const h of ['Joint', 'No 3D position', 'Longest stretch', 'Cameras apart', 'Missed most by']) jh.append(el('th', h))
    jt.append(jh)
    for (const line of joints) {
      const tr = el('tr')
      const gapText = line.longestGap && line.longestGap.frames > 1
        ? `${(line.longestGap.end - line.longestGap.start).toFixed(1)} s at ${line.longestGap.start.toFixed(1)} s`
        : '–'
      const missed = line.missedBy[0]
      tr.append(
        el('td', prettyJoint(line.joint)),
        el('td', pct(line.lostFraction), line.lostFraction >= LIMITS.missingPercent.bad / 100 ? 'bad' : line.lostFraction <= LIMITS.missingPercent.good / 100 ? 'good' : 'mid'),
        el('td', gapText),
        el('td', line.errorPx === null ? '–' : `${line.errorPx.toFixed(1)} px${line.errorMm === null ? '' : ` ≈ ${line.errorMm.toFixed(0)} mm`}`, gradeOf(line.errorPx)),
        el('td', missed && missed.fraction > 0 ? `${missed.camera}, ${pct(missed.fraction)}` : '–'),
      )
      jt.append(tr)
    }
    const jwrap = el('div', undefined, 'table-wrap')
    jwrap.append(jt)
    all.append(jwrap)
    this.jointStoryBox.append(all)
  }
}
