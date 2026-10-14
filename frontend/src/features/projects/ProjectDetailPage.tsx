import { Suspense, lazy, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useSettings } from '@/app/SettingsProvider'
import { useStudio } from '@/app/StudioProvider'
import { StickFigure } from '@/components/ui/StickFigure'
import { Toast } from '@/components/ui/Modal'
import {
  CheckIcon,
  ExportIcon,
  InfoIcon,
  PauseIcon,
  PlayIcon,
  ShareIcon,
} from '@/components/ui/Icons'
import { rigParts } from '@/lib/data'
import { API_URL, ApiUnreachableError, getTake, listTakes, takeFileUrl } from '@/lib/api'
import type { Take } from '@/lib/api'
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

const takeLabel = (take: Take) => take.name ?? take.id

/** A plain-words message for a failed API call. */
function apiErrorMessage(e: unknown, what: string) {
  return e instanceof ApiUnreachableError
    ? `Can't reach the API at ${API_URL}`
    : `Couldn't load ${what}: ${e instanceof Error ? e.message : String(e)}`
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
  const [viewer, setViewer] = useState<ViewerState>({ message: 'No take selected' })
  const [tab, setTab] = useState<'rig' | 'streaming' | 'export'>('rig')
  const [selectedPart, setSelectedPart] = useState('left-forearm')
  const [hidden, setHidden] = useState<Source[]>([])
  const [playing, setPlaying] = useState(false)
  const [frozen, setFrozen] = useState(settings.freezeViewport)
  const [position, setPosition] = useState(0)
  const [motion, setMotion] = useState<MotionInfo | null>(null)
  const [rotation, setRotation] = useState(0)
  const [toast, setToast] = useState<string | null>(null)

  // the viewer follows ?clip=
  const selectedTake = takes?.find((t) => t.id === clip)
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

  // look the ?clip= take up in the API (a one-time check; live polling comes later)
  useEffect(() => {
    if (!clip) {
      setViewer({ message: 'No take selected' })
      return
    }
    const controller = new AbortController()
    setViewer({ message: 'Loading take…' })
    getTake(clip, controller.signal)
      .then((found) => setViewer(found ? viewerStateFor(found) : { message: 'Take not found' }))
      .catch((e) => {
        if (!controller.signal.aborted) setViewer({ message: apiErrorMessage(e, 'the take') })
      })
    return () => controller.abort()
  }, [clip])
  // the loaded file's length; nothing to play until one loads
  const length = motion?.duration ?? 0

  useEffect(() => setFrozen(settings.freezeViewport), [settings.freezeViewport])

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
        <button
          className="btn btn--primary"
          onClick={() => {
            setTab('export')
            setToast('Export queued — FBX at 60 fps')
          }}
        >
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
                  <span className="dur">{STATUS_LABEL[t.status]}</span>
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
              <label className="field">
                <span className="field__label">Format</span>
                <select className="select" defaultValue="fbx">
                  <option value="fbx">FBX — skeleton and animation</option>
                  <option value="bvh">BVH — animation only</option>
                  <option value="csv">CSV — joint positions per frame</option>
                  <option value="glb">glTF / GLB</option>
                </select>
              </label>
              <label className="field">
                <span className="field__label">Frame rate</span>
                <select className="select" defaultValue="60">
                  <option value="60">60 fps (native)</option>
                  <option value="30">30 fps</option>
                  <option value="24">24 fps</option>
                </select>
              </label>
              <label className="check">
                <input type="checkbox" defaultChecked />
                Bake the rotation offsets
              </label>
              <label className="check">
                <input type="checkbox" defaultChecked />
                Include parts marked “needs review”
              </label>
              <button className="btn btn--primary" onClick={() => setToast('Export queued')}>
                <ExportIcon />
                Export take
              </button>
            </div>
          )}
        </aside>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </>
  )
}
