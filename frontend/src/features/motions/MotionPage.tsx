import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useSettings } from '@/app/SettingsProvider'
import {
  ExportIcon,
  InfoIcon,
  PauseIcon,
  PlayIcon,
} from '@/components/ui/Icons'
import { rigParts } from '@/lib/data'
import {
  getMotion,
  loadVersionBvh,
  MOTION_STATUS_LABEL,
  POSE_LABEL,
  startRendering,
  type ApiMotion,
  type ApiMotionRecording,
} from '@/lib/motions'
import { AddRecordingDialog } from './AddRecordingDialog'
import { VersionPicker } from './VersionPicker'
import type { Source } from '@/types'
import { SOURCE_COLOR } from '@/features/projects/SkeletonViewport'
import type { MotionInfo } from '@/features/viewer/MotionViewport'
import type { ViewerState } from '@/features/viewer/viewerState'
import '@/features/projects/projects.css'

// the 3D viewer pulls in three.js, so it loads only when a motion is opened
const MotionViewport = lazy(() =>
  import('@/features/viewer/MotionViewport').then((m) => ({ default: m.MotionViewport })),
)

const LEGEND: { source: Source; label: string }[] = [
  { source: 'suit', label: 'Suit-driven' },
  { source: 'ai', label: 'AI-inferred' },
  { source: 'review', label: 'Needs review' },
]

/** One camera's device line under its recording: its size and frame rate, as far as the recording knows them. */
function cameraSpec(r: ApiMotionRecording) {
  const size = r.width && r.height ? `${r.width}×${r.height}` : 'size unknown'
  const rate = r.fps ? ` · ${Math.round(r.fps)} fps` : ''

  return `${size}${rate}`
}

export function MotionPage() {
  const { motionId } = useParams()
  const { settings } = useSettings()

  const [detail, setDetail] = useState<ApiMotion | null>(null)
  const [missing, setMissing] = useState(false)
  const [addingRecording, setAddingRecording] = useState(false)
  // processing settings for the next version; not wired to the pipeline yet
  const [source, setSource] = useState<'pipeline' | 'manual'>('pipeline')
  const [poseModel, setPoseModel] = useState('mediapipe')
  // manual edits need a processed version to edit
  const hasOutput = detail?.versions.some((v) => v.status === 'done') ?? false
  // once a version exists, the motion's recordings are fixed
  const locked = (detail?.versions.length ?? 0) > 0
  const [recordingError, setRecordingError] = useState<string | null>(null)
  // the versions, and the one the viewer shows: the newest until another is picked
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null)
  const [rendering, setRendering] = useState(false)
  const [renderError, setRenderError] = useState<string | null>(null)
  const versions = detail?.versions ?? []
  const current = versions.find((v) => v.uuid === selectedVersion) ?? versions[versions.length - 1] ?? null
  // a render is running while any version is queued or running; the server runs one at a time
  const busy = versions.some((v) => v.status === 'queued' || v.status === 'running')
  // a render needs at least two cameras, and no other render going
  const canRender = !busy && !rendering && (detail?.recordings.length ?? 0) >= 2
  const motionName = detail?.name ?? ''
  // the transport's clock: the motion's length until a file loads
  const take = { name: motionName, duration: '0:24' }
  const [viewer, setViewer] = useState<ViewerState>({ message: 'Loading motion…' })
  const [tab, setTab] = useState<'rig' | 'cameras' | 'streaming' | 'export'>('rig')
  const [selectedPart, setSelectedPart] = useState('left-forearm')
  const [hidden, setHidden] = useState<Source[]>([])
  const [playing, setPlaying] = useState(false)
  const [frozen, setFrozen] = useState(settings.freezeViewport)
  const [position, setPosition] = useState(0)
  const [motion, setMotion] = useState<MotionInfo | null>(null)
  const [rotation, setRotation] = useState(0)

  const takeName = take.name

  // the motion itself, with its project and the recordings it uses
  useEffect(() => {
    if (!motionId) return
    setDetail(null)
    setMissing(false)
    getMotion(motionId)
      .then(setDetail)
      .catch(() => setMissing(true))
  }, [motionId])

  // reloads the motion after it changes; the page stays up meanwhile
  async function reloadDetail() {
    if (!motionId) return
    try {
      setDetail(await getMotion(motionId))
    } catch (err) {
      setRecordingError(err instanceof Error ? err.message : 'Could not reload the motion.')
    }
  }

  // the viewer shows the chosen version: its skeleton once rendered, otherwise its status
  const currentNumber = current?.number
  const currentStatus = current?.status
  const currentError = current?.error
  useEffect(() => {
    if (!motionId) return
    if (currentNumber === undefined || currentStatus === undefined) {
      setViewer({ message: 'Start rendering to see the skeleton here.' })
      return
    }
    if (currentStatus === 'failed') {
      setViewer({ message: `The render failed: ${currentError || 'unknown error'}` })
      return
    }
    if (currentStatus !== 'done') {
      setViewer({ message: currentStatus === 'running' ? 'Rendering…' : 'Queued…' })
      return
    }

    let url: string | null = null
    let cancelled = false
    setViewer({ message: 'Loading the skeleton…' })
    loadVersionBvh(motionId, currentNumber)
      .then((objectUrl) => {
        if (cancelled) {
          URL.revokeObjectURL(objectUrl)
          return
        }
        url = objectUrl
        setViewer({ src: { url: objectUrl, name: `${motionName}-v${currentNumber}.bvh` } })
      })
      .catch((err: unknown) => {
        if (!cancelled) setViewer({ message: err instanceof Error ? err.message : 'Could not load the skeleton.' })
      })

    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [motionId, currentNumber, currentStatus, currentError, motionName])

  // while a render runs, the motion is asked for again until it has finished
  useEffect(() => {
    if (!busy) return
    const id = window.setInterval(() => {
      void reloadDetail()
    }, 2000)

    return () => window.clearInterval(id)
  }, [busy])

  // "New version" renders nothing by itself: the pose model and the start button are in the processing panel
  function showProcessing() {
    document.getElementById('processing')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  async function onStartRendering() {
    if (!motionId) return
    setRendering(true)
    setRenderError(null)
    try {
      await startRendering(motionId, poseModel)
      setSelectedVersion(null)
      await reloadDetail()
    } catch (err) {
      setRenderError(err instanceof Error ? err.message : 'Could not start the render.')
    } finally {
      setRendering(false)
    }
  }
  const length = useMemo(() => {
    // the loaded file's length; the mocked take length until one loads
    if (motion) return motion.duration
    const [m, s] = (take?.duration ?? '0:24').split(':').map(Number)
    return m * 60 + s
  }, [take, motion])

  useEffect(() => setFrozen(settings.freezeViewport), [settings.freezeViewport])

  // with a file loaded the 3D viewport runs the clock; this is only the fallback
  useEffect(() => {
    if (!playing || motion) return
    const id = window.setInterval(() => {
      setPosition((p) => (p + 1 > length ? 0 : p + 1))
    }, 1000)
    return () => window.clearInterval(id)
  }, [playing, length, motion])

  if (!detail && !missing) {
    return (
      <div className="page">
        <p className="page-sub">Loading motion…</p>
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="page">
        <h1 className="page-title">Motion not found</h1>
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
          {/* the first project it is in, or none */}
          {detail.projects[0] ? (
            <>
              <Link to="/projects">Projects</Link>
              <span style={{ color: 'var(--muted-2)' }}>/</span>
              <Link to={`/projects/${detail.projects[0].uuid}`}>{detail.projects[0].name}</Link>
            </>
          ) : (
            <>
              <Link to="/motions">Motions</Link>
            </>
          )}
          <span style={{ color: 'var(--muted-2)' }}>/</span>
          <b>{detail.name}</b>
        </nav>
        <span className="spacer" />
        <VersionPicker
          versions={versions}
          current={current}
          onSelect={setSelectedVersion}
          onNewVersion={showProcessing}
        />
      </div>

      <div className="ws">
        {/* ---------------- recordings / performer / devices ---------------- */}
        <aside className="ws__left">
          <section>
            <p className="eyebrow">Recordings</p>
            <p style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 8 }}>
              {MOTION_STATUS_LABEL[detail.status] ?? detail.status} · {detail.recording_count}{' '}
              {detail.recording_count === 1 ? 'recording' : 'recordings'}
            </p>
            <div className="takelist">
              {detail.recordings.map((r) => (
                <div key={r.uuid} className="takelist__row">
                  <p className="takelist__specs">
                    Cam {r.camera_slot + 1} · {cameraSpec(r)}
                  </p>
                  <p className="takelist__name">{r.name || 'Untitled recording'}</p>
                </div>
              ))}
            </div>
            {motion && detail.recordings.length > 0 && (
              <p className="takelist__specs">
                Processed at {Math.round(motion.fps)} fps · {motion.frames.toLocaleString()} frames
              </p>
            )}
            {detail.recordings.length === 0 && (
              <p style={{ color: 'var(--muted-2)', fontSize: 13, marginTop: 10 }}>
                No recordings in this motion yet.
              </p>
            )}
            {recordingError && (
              <p role="alert" style={{ color: 'var(--pink)', fontSize: 13, marginTop: 10 }}>
                {recordingError}
              </p>
            )}
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              style={{ marginTop: 12 }}
              disabled={locked}
              onClick={() => setAddingRecording(true)}
            >
              Choose recordings
            </button>
            {locked && (
              <p style={{ color: 'var(--muted-2)', fontSize: 13, marginTop: 10 }}>
                Locked: this motion has versions, so its recordings can no longer change.
              </p>
            )}
          </section>

          <section className="ws__performers">
            <p className="eyebrow">Performers</p>
            {detail.performers.length === 0 && (
              <p style={{ color: 'var(--muted-2)', fontSize: 13, marginTop: 10 }}>
                No performer yet. Set one on a recording and add it here.
              </p>
            )}
            <div className="takelist">
              {detail.performers.map((p) => (
                <div key={p.id} className="takelist__row">
                  <p className="takelist__name">{p.full_name}</p>
                  <p className="takelist__specs">{p.height_m ? `${p.height_m.toFixed(2)} m` : 'height not set'}</p>
                </div>
              ))}
            </div>
          </section>

          <section id="processing">
            <p className="eyebrow">Processing</p>
            <div className="stack" style={{ gap: 12, marginTop: 10 }}>
              <label className="field">
                <span className="field__label">Source</span>
                <select
                  className="select"
                  value={source}
                  onChange={(e) => setSource(e.target.value as 'pipeline' | 'manual')}
                >
                  <option value="pipeline">Pipeline</option>
                  <option value="manual" disabled={!hasOutput}>
                    Manual edit
                  </option>
                </select>
              </label>

              {source === 'pipeline' ? (
                <>
                  <label className="field">
                    <span className="field__label">Pose model</span>
                    <select className="select" value={poseModel} onChange={(e) => setPoseModel(e.target.value)}>
                      {Object.entries(POSE_LABEL).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button type="button" className="btn btn--primary" disabled={!canRender} onClick={onStartRendering}>
                    {rendering ? 'Starting…' : 'Start rendering'}
                  </button>
                  {(detail.recordings.length < 2) && (
                    <p style={{ color: 'var(--muted-2)', fontSize: 13 }}>Add at least 2 recordings to render.</p>
                  )}
                  {busy && <p style={{ color: 'var(--muted-2)', fontSize: 13 }}>A render is running.</p>}
                  {renderError && (
                    <p role="alert" style={{ color: 'var(--pink)', fontSize: 13 }}>
                      {renderError}
                    </p>
                  )}
                </>
              ) : (
                <button type="button" className="btn btn--primary" disabled title="Manual editing is not connected yet">
                  Start editing
                </button>
              )}

              {!hasOutput && (
                <p style={{ color: 'var(--muted-2)', fontSize: 13 }}>
                  Manual edit becomes available once a pipeline run has finished.
                </p>
              )}
            </div>
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
          </div>
        </section>

        {/* ---------------- inspector ---------------- */}
        <aside className="ws__right">
          <div className="tabs" role="tablist" aria-label="Inspector">
            <button role="tab" aria-selected={tab === 'rig'} onClick={() => setTab('rig')}>
              Rig
            </button>
            <button role="tab" aria-selected={tab === 'cameras'} onClick={() => setTab('cameras')}>
              Cameras
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

          {tab === 'cameras' && (
            <div className="stack" style={{ gap: 14 }}>
              <h3 style={{ fontSize: 17 }}>What each camera saw</h3>
              <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
                The 2D joints the detector found in every video, at the time the transport shows. Faint bones
                mean low confidence; a missing figure means no person was found in that frame.
              </p>
              <p style={{ color: 'var(--muted-2)', fontSize: 13 }}>
                The 2D view of each camera is not connected to motion versions yet.
              </p>
            </div>
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
              <button className="btn btn--primary">
                Start streaming
              </button>
            </div>
          )}

          {tab === 'export' && (
            <div className="stack" style={{ gap: 18 }}>
              <h3 style={{ fontSize: 17 }}>Export take</h3>
              <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
                {take?.name} · {take?.duration} · 60 fps
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
              <button className="btn btn--primary">
                <ExportIcon />
                Export take
              </button>
            </div>
          )}
        </aside>
      </div>

      {addingRecording && motionId && (
        <AddRecordingDialog
          motionId={motionId}
          inMotion={detail.recordings.map((r) => r.recording)}
          onSaved={reloadDetail}
          onClose={() => setAddingRecording(false)}
        />
      )}
    </>
  )
}
