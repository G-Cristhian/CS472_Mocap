import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useSettings } from '@/app/SettingsProvider'
import { useStudio } from '@/app/StudioProvider'
import { StickFigure } from '@/components/ui/StickFigure'
import { Toast } from '@/components/ui/Modal'
import {
  AlertIcon,
  CheckIcon,
  ExportIcon,
  InfoIcon,
  PauseIcon,
  PlayIcon,
  ShareIcon,
} from '@/components/ui/Icons'
import { rigParts } from '@/lib/data'
import {
  API_URL,
  ApiUnreachableError,
  TakeFileError,
  getTake,
  getTakeFile,
  listTakes,
  takeFileUrl,
} from '@/lib/api'
import type { Take, TakeFile } from '@/lib/api'
import type { Source } from '@/types'
import { SOURCE_COLOR } from './SkeletonViewport'
import type { MotionInfo, MotionSource } from '@/features/viewer/MotionViewport'
import './projects.css'

// the 3D viewer pulls in three.js, so it loads only when a project is opened
const MotionViewport = lazy(() =>
  import('@/features/viewer/MotionViewport').then((m) => ({ default: m.MotionViewport })),
)

const LEGEND: { source: Source; label: string }[] = [
  { source: 'suit', label: 'Suit-driven' },
  { source: 'ai', label: 'AI-inferred' },
  { source: 'review', label: 'Needs review' },
]

const STATUS_LABEL: Record<Take['status'], string> = {
  queued: 'Queued',
  running: 'Processing',
  done: 'Done',
  failed: 'Failed',
}

/** How often the take list is refreshed while a take is queued or running. */
const POLL_MS = 3000

const isProcessing = (take: Take) => take.status === 'queued' || take.status === 'running'

/** The take's status in the list; a running take shows its pipeline stage. */
function statusLabel(take: Take) {
  if (take.status === 'running' && take.stage) {
    return `${take.stage[0].toUpperCase()}${take.stage.slice(1)}…`
  }
  return STATUS_LABEL[take.status]
}

const takeLabel = (take: Take) => take.name ?? take.id

/** A plain-words message for a failed API call. */
function apiErrorMessage(e: unknown, what: string) {
  return e instanceof ApiUnreachableError
    ? `Can't reach the API at ${API_URL}`
    : `Couldn't load ${what}: ${e instanceof Error ? e.message : String(e)}`
}

const EXPORT_FILES = [
  { file: 'out3d.bvh', ext: 'bvh', kind: 'BVH', label: 'Download BVH' },
  { file: 'out3d.json', ext: 'json', kind: 'JSON', label: 'Download JSON' },
] as const
type ExportFile = (typeof EXPORT_FILES)[number]

/** The saved file's name: the take's name made file-safe ("Jump Test #2" -> jump-test-2.bvh), else its id. */
function downloadName(take: Take, ext: string) {
  const base = (take.name ?? '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // é -> e
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .slice(0, 80)
    .replace(/^-+|-+$/g, '')
  return `${base || take.id}.${ext}`
}

/** A plain-words message for a failed download of one of a take's files. */
function downloadErrorMessage(e: unknown, take: Take, kind: string) {
  if (e instanceof ApiUnreachableError) return `Can't reach the API at ${API_URL}, so nothing was downloaded.`
  if (e instanceof TakeFileError && e.status === 404) {
    return `The ${kind} file for ${takeLabel(take)} is missing on the server, so it can't be downloaded.`
  }
  if (e instanceof TakeFileError && e.status === 409) {
    return `${takeLabel(take)} hasn't finished processing, so its files can't be downloaded yet.`
  }
  return `Couldn't download the ${kind} file: ${e instanceof Error ? e.message : String(e)}`
}

/** Save a blob as a file. The API is another origin, so a plain <a download> link would ignore the name. */
function saveBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.append(link)
  link.click()
  link.remove()
  // give the browser a moment to start the download before freeing the blob
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

/** Why a take's files can't be downloaded yet. */
function exportUnavailableReason(take: Take | undefined) {
  if (!take) return 'Pick a take in the list to download its files.'
  if (take.status === 'failed') {
    return 'This take failed to process, so it has no files to download.'
  }
  return 'The files can be downloaded once this take has finished processing.'
}

/** What the viewer shows for the ?clip= take: a file to play, or a message. */
interface ViewerState {
  take?: Take
  src?: MotionSource
  message?: string
}

function viewerStateFor(take: Take): ViewerState {
  switch (take.status) {
    case 'queued':
      return { take, message: 'Queued' }
    case 'running':
      return { take, message: take.stage ? `Processing: ${take.stage}…` : 'Processing…' }
    case 'failed':
      return { take, message: take.error ?? 'Processing failed' }
    case 'done': {
      // parseMotion picks the parser from the extension, so the name must end in .bvh
      const name = `${takeLabel(take)}.bvh`
      // Loads the BVH (17-joint skeleton). Consider out3d.json later: all 33 raw joints, and it shows where tracking dropped out.
      return { take, src: { url: takeFileUrl(take.id, 'out3d.bvh'), name } }
    }
  }
}

export function ProjectDetailPage() {
  const { projectId } = useParams()
  const [params, setParams] = useSearchParams()
  const clip = params.get('clip')
  const { projects } = useStudio()
  const { settings } = useSettings()

  const project = projects.find((p) => p.id === projectId)

  // the project's takes from the API; null until the first answer
  const [takes, setTakes] = useState<Take[] | null>(null)
  const [takesError, setTakesError] = useState<string | null>(null)
  const [lookup, setLookup] = useState<ViewerState>({ message: 'No take selected' })
  const [tab, setTab] = useState<'rig' | 'streaming' | 'export'>('rig')
  const [selectedPart, setSelectedPart] = useState('left-forearm')
  const [hidden, setHidden] = useState<Source[]>([])
  const [playing, setPlaying] = useState(false)
  const [frozen, setFrozen] = useState(settings.freezeViewport)
  const [position, setPosition] = useState(0)
  const [motion, setMotion] = useState<MotionInfo | null>(null)
  const [rotation, setRotation] = useState(0)
  const [toast, setToast] = useState<string | null>(null)
  // the Export tab's download in progress, and why the last one failed
  const [downloading, setDownloading] = useState<TakeFile | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  // the viewer follows ?clip=: a take in the list stays fresh while it's polled,
  // any other id (e.g. from an old link) is looked up once
  const selectedTake = takes?.find((t) => t.id === clip)
  const viewer = useMemo(
    () => (selectedTake ? viewerStateFor(selectedTake) : lookup),
    [selectedTake, lookup],
  )
  const shownTake = viewer.take ?? selectedTake
  const takeName = shownTake ? takeLabel(shownTake) : clip ?? 'No take selected'

  const selectClip = (id: string) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('clip', id)
      return next
    })
    setPosition(0)
  }

  // load the project's takes
  useEffect(() => {
    if (!projectId) return
    const controller = new AbortController()
    setTakes(null)
    setTakesError(null)
    listTakes(projectId, controller.signal)
      .then(setTakes)
      .catch((e) => {
        if (!controller.signal.aborted) setTakesError(apiErrorMessage(e, 'the takes'))
      })
    return () => controller.abort()
  }, [projectId])

  // refresh the list while any take is queued or running; stops once none is
  // (or the page closes). A failed refresh keeps the last list and tries again.
  const processing = takes?.some(isProcessing) ?? false
  useEffect(() => {
    if (!processing || !projectId) return
    const controller = new AbortController()
    let timer: number
    const poll = () => {
      timer = window.setTimeout(() => {
        listTakes(projectId, controller.signal)
          .then((latest) => {
            setTakes(latest)
            setTakesError(null)
          })
          .catch((e) => {
            if (!controller.signal.aborted) setTakesError(apiErrorMessage(e, 'the takes'))
          })
          .finally(() => {
            if (!controller.signal.aborted) poll()
          })
      }, POLL_MS)
    }
    poll()
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [processing, projectId])

  // look the ?clip= take up in the API (once; the list polling keeps it fresh)
  useEffect(() => {
    if (!clip) {
      setLookup({ message: 'No take selected' })
      return
    }
    const controller = new AbortController()
    setLookup({ message: 'Loading take…' })
    getTake(clip, controller.signal)
      .then((found) => setLookup(found ? viewerStateFor(found) : { message: 'Take not found' }))
      .catch((e) => {
        if (!controller.signal.aborted) setLookup({ message: apiErrorMessage(e, 'the take') })
      })
    return () => controller.abort()
  }, [clip])
  // the loaded file's length; nothing to play until one loads
  const length = motion?.duration ?? 0

  useEffect(() => setFrozen(settings.freezeViewport), [settings.freezeViewport])

  // a download error is about the take it was for
  useEffect(() => setDownloadError(null), [clip])

  // fetched rather than linked, so a missing file shows an error here instead of
  // sending the tab to the API's JSON error page
  const downloadFile = async (take: Take, f: ExportFile) => {
    setDownloading(f.file)
    setDownloadError(null)
    try {
      saveBlob(await getTakeFile(take.id, f.file), downloadName(take, f.ext))
    } catch (e) {
      setDownloadError(downloadErrorMessage(e, take, f.kind))
    } finally {
      setDownloading(null)
    }
  }

  // with a file loaded the 3D viewport runs the clock; this is only the fallback
  useEffect(() => {
    if (!playing || motion) return
    const id = window.setInterval(() => {
      setPosition((p) => (p + 1 > length ? 0 : p + 1))
    }, 1000)
    return () => window.clearInterval(id)
  }, [playing, length, motion])

  if (!project) {
    return (
      <div className="page">
        <h1 className="page-title">Project not found</h1>
        <p className="page-sub">It may have been renamed or removed.</p>
        <p style={{ marginTop: 20 }}>
          <Link className="btn btn--primary" to="/projects">
            Back to projects
          </Link>
        </p>
      </div>
    )
  }

  const part = rigParts.find((p) => p.id === selectedPart)!
  const clock = (seconds: number) => {
    const n = Math.floor(seconds)
    return `${Math.floor(n / 60)
      .toString()
      .padStart(2, '0')}:${(n % 60).toString().padStart(2, '0')}`
  }

  return (
    <>
      <div className="ws__bar">
        <nav className="ws__crumbs" aria-label="Breadcrumb">
          <Link to="/projects">Projects</Link>
          <span style={{ color: 'var(--muted-2)' }}>/</span>
          <b>{project.name}</b>
        </nav>
        <span className="spacer" />
        <span className="ws__saved">
          <CheckIcon size={16} />
          All changes saved
        </span>
        <button className="btn btn--ghost" onClick={() => setToast('Share link copied to clipboard')}>
          <ShareIcon />
          Share
        </button>
        <button className="btn btn--primary" onClick={() => setTab('export')}>
          <ExportIcon />
          Export
        </button>
      </div>

      <div className="ws">
        {/* ---------------- clips / performer / devices ---------------- */}
        <aside className="ws__left">
          <section>
            <p className="eyebrow">Clips</p>
            <div className="takelist">
              {takes?.map((t) => (
                <button
                  key={t.id}
                  aria-current={t.id === clip}
                  title={t.error ?? undefined}
                  onClick={() => selectClip(t.id)}
                >
                  <span
                    className="dot"
                    style={{ background: t.id === clip ? 'var(--purple)' : 'var(--line)' }}
                  />
                  {takeLabel(t)}
                  <span className="dur">{statusLabel(t)}</span>
                </button>
              ))}
            </div>
            {(takesError || takes?.length === 0 || !takes) && (
              <p style={{ color: 'var(--muted)', fontSize: 13.5, marginTop: 10 }}>
                {takesError ?? (takes ? 'No takes in this project yet.' : 'Loading takes…')}
              </p>
            )}
          </section>

          <section>
            <p className="eyebrow">Performer</p>
            <div className="performer">
              <span className="performer__avatar">
                <StickFigure pose="stand" color="var(--blue)" size={26} strokeWidth={7} />
              </span>
              <div className="stack">
                <strong>Noah</strong>
                <span style={{ color: 'var(--muted)', fontSize: 13 }}>Suit A · calibrated</span>
              </div>
            </div>
          </section>

          <section>
            <p className="eyebrow">Capture devices</p>
            <p className="devices">
              4 cameras · 1 suit
              <br />
              {motion
                ? `${Math.round(motion.fps)} fps · ${motion.frames.toLocaleString()} frames`
                : '60 fps · 2,164 frames'}
            </p>
          </section>
        </aside>

        {/* ---------------- viewport ---------------- */}
        <section className="ws__center">
          <div className="viewport">
            <div className="viewport__legend">
              {LEGEND.map((l) => (
                <button
                  key={l.source}
                  className="legend"
                  aria-pressed={!hidden.includes(l.source)}
                  onClick={() =>
                    setHidden((h) =>
                      h.includes(l.source) ? h.filter((s) => s !== l.source) : [...h, l.source],
                    )
                  }
                >
                  <i style={{ background: SOURCE_COLOR[l.source] }} />
                  {l.label}
                </button>
              ))}
            </div>

            <Suspense fallback={<span style={{ color: 'var(--muted-2)' }}>Loading the 3D viewer…</span>}>
              <MotionViewport
                parts={rigParts}
                selectedId={selectedPart}
                onSelect={setSelectedPart}
                hidden={hidden}
                playing={playing && !frozen}
                time={position}
                onTimeChange={setPosition}
                onMotionLoaded={(info) => {
                  setMotion(info)
                  setPosition(0)
                }}
                src={viewer.src}
                message={viewer.message}
              />
            </Suspense>

            {frozen && (
              <div className="viewport__frozen">
                <span>The viewport is frozen until you press play.</span>
                <button
                  className="btn btn--white btn--sm"
                  onClick={() => {
                    setFrozen(false)
                    setPlaying(true)
                  }}
                >
                  Play the take
                </button>
              </div>
            )}
          </div>

          <div className="transport">
            <button
              className="transport__play"
              aria-label={playing ? 'Pause' : 'Play'}
              onClick={() => {
                setFrozen(false)
                setPlaying((p) => !p)
              }}
            >
              {playing ? <PauseIcon /> : <PlayIcon />}
            </button>
            <span className="transport__name">{takeName}</span>
            <input
              type="range"
              min={0}
              max={length}
              step={motion ? 0.01 : 1}
              value={position}
              aria-label="Playhead"
              onChange={(e) => setPosition(Number(e.target.value))}
              style={{ flex: 1 }}
            />
            <span className="transport__time">
              {clock(position)} / {clock(length)}
            </span>
            <Link className="btn btn--pink" to="/record">
              <span className="dot" style={{ background: '#fff' }} />
              New take
            </Link>
          </div>
        </section>

        {/* ---------------- inspector ---------------- */}
        <aside className="ws__right">
          <div className="tabs" role="tablist" aria-label="Inspector">
            <button role="tab" aria-selected={tab === 'rig'} onClick={() => setTab('rig')}>
              Rig
            </button>
            <button role="tab" aria-selected={tab === 'streaming'} onClick={() => setTab('streaming')}>
              Streaming
            </button>
            <button role="tab" aria-selected={tab === 'export'} onClick={() => setTab('export')}>
              Export
            </button>
          </div>

          {tab === 'rig' && (
            <>
              <h3 style={{ fontSize: 17 }}>Rig parts</h3>
              <p style={{ color: 'var(--muted)', fontSize: 13.5, marginTop: 4 }}>
                Pick a part to see where its motion came from.
              </p>
              <div className="rigparts">
                {rigParts.map((p) => (
                  <button
                    key={p.id}
                    aria-pressed={p.id === selectedPart}
                    onClick={() => setSelectedPart(p.id)}
                  >
                    {p.name}
                    <span className="spacer" />
                    <span className={`badge badge--${p.status}`}>
                      {p.status === 'review' ? 'Review' : p.status === 'ai' ? 'AI' : 'Suit'}
                    </span>
                  </button>
                ))}
              </div>

              <div className="partcard">
                <div className="partcard__head">
                  <h3 style={{ fontSize: 17 }}>{part.name}</h3>
                  <span className={`badge badge--${part.status}`}>
                    {part.status === 'review' ? 'Review' : part.status === 'ai' ? 'AI' : 'Suit'}
                  </span>
                </div>

                <div>
                  <p style={{ fontWeight: 700, marginBottom: 8 }}>Tracking confidence</p>
                  <div className="row">
                    <span className="meter">
                      <span style={{ width: `${part.confidence}%` }} />
                    </span>
                    <b className="mono">{part.confidence}%</b>
                  </div>
                  <p style={{ color: 'var(--muted)', fontSize: 13.5, marginTop: 8 }}>{part.origin}</p>
                </div>

                <div>
                  <p style={{ fontWeight: 700 }}>Rotation offset</p>
                  <p style={{ color: 'var(--muted)', fontSize: 13.5, marginTop: 2 }}>
                    Nudge this joint if it reads twisted against the video.
                  </p>
                  <div className="row" style={{ marginTop: 10 }}>
                    <input
                      className="numinput"
                      type="number"
                      value={rotation}
                      aria-label="Rotation offset in degrees"
                      onChange={(e) => setRotation(Number(e.target.value))}
                    />
                    <span>degrees</span>
                  </div>
                </div>

                <div className="note">
                  <InfoIcon />
                  <span>
                    <b>You can change this later</b> — edits apply to this take only and never touch
                    the raw capture.
                  </span>
                </div>
              </div>
            </>
          )}

          {tab === 'streaming' && (
            <div className="stack" style={{ gap: 18 }}>
              <h3 style={{ fontSize: 17 }}>Live streaming</h3>
              <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
                Push this rig to an engine while you record.
              </p>
              <label className="field">
                <span className="field__label">Target</span>
                <select className="select" defaultValue="unreal">
                  <option value="unreal">Unreal Engine 5 — Live Link</option>
                  <option value="unity">Unity — Mocap Relay</option>
                  <option value="blender">Blender — Rokoko bridge</option>
                </select>
              </label>
              <label className="field">
                <span className="field__label">Address</span>
                <input className="input mono" defaultValue="192.168.1.24:14043" />
              </label>
              <label className="check">
                <input type="checkbox" defaultChecked />
                Stream the AI-inferred parts too
              </label>
              <label className="check">
                <input type="checkbox" />
                Drop frames instead of buffering
              </label>
              <button className="btn btn--primary" onClick={() => setToast('Live Link connected')}>
                Start streaming
              </button>
            </div>
          )}

          {tab === 'export' && (
            <div className="stack" style={{ gap: 18 }}>
              <h3 style={{ fontSize: 17 }}>Export take</h3>
              <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
                {selectedTake ? takeLabel(selectedTake) : 'No take selected'}
              </p>
              {EXPORT_FILES.map((f) =>
                selectedTake?.status === 'done' ? (
                  <button
                    key={f.file}
                    className="btn btn--primary"
                    disabled={downloading !== null}
                    onClick={() => downloadFile(selectedTake, f)}
                  >
                    <ExportIcon />
                    {downloading === f.file ? 'Downloading…' : f.label}
                  </button>
                ) : (
                  <button key={f.file} className="btn btn--primary" disabled>
                    <ExportIcon />
                    {f.label}
                  </button>
                ),
              )}
              {downloadError && (
                <div className="alert" role="alert">
                  <AlertIcon />
                  <span>{downloadError}</span>
                </div>
              )}
              {selectedTake?.status === 'done' ? (
                <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
                  BVH is the animated skeleton for Blender, Maya or a game engine. JSON has every
                  tracked joint's 3D position per frame.
                </p>
              ) : (
                <div className="note">
                  <InfoIcon />
                  <span>{exportUnavailableReason(selectedTake)}</span>
                </div>
              )}
            </div>
          )}
        </aside>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </>
  )
}
