import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import { StickFigure } from '@/components/ui/StickFigure'
import { Toast } from '@/components/ui/Modal'
import { cameras } from '@/lib/data'
import './recordings.css'

function clock(seconds: number) {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0')
  const s = (seconds % 60).toString().padStart(2, '0')

  return `${m}:${s}`
}

/**
 * One video from one camera. Opened as /recordings/new it records from that camera;
 * opened as /recordings/:id it previews a stored video. Trim and crop are mock controls for now.
 */
export function RecordingPage() {
  const { recordingId } = useParams()
  const { recordings, motions } = useStudio()
  const isNew = recordingId === 'new'
  const recording = isNew ? undefined : recordings.find((r) => r.id === recordingId)
  const motion = motions.find((m) => m.id === recording?.motionId)
  const camera = cameras[0]

  const [live, setLive] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [inPoint, setInPoint] = useState(0)
  const [outPoint, setOutPoint] = useState(100)
  const [cropping, setCropping] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    if (!live) return
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => window.clearInterval(id)
  }, [live])

  if (!isNew && !recording) {
    return (
      <div className="page">
        <h1 className="page-title">Recording not found</h1>
        <p className="page-sub">It may have been removed.</p>
        <p style={{ marginTop: 20 }}>
          <Link className="btn btn--primary" to="/recordings">
            Back to recordings
          </Link>
        </p>
      </div>
    )
  }

  const title = isNew ? 'New recording' : recording?.name ?? ''

  return (
    <div className="page">
      <nav className="recording__crumbs" aria-label="Breadcrumb">
        <Link to="/recordings">Recordings</Link>
        <span style={{ color: 'var(--muted-2)' }}>/</span>
        {motion ? <Link to={`/motions/${motion.id}`}>{motion.name}</Link> : <span>Not in a motion yet</span>}
      </nav>

      <div className="page-head" style={{ marginTop: 16 }}>
        <div>
          <h1 className="page-title">{title}</h1>
          <p className="page-sub">
            {isNew ? 'One camera. Trim and crop after recording.' : `${recording?.duration} · ${recording?.origin === 'stream' ? 'Streamed' : 'Uploaded'}`}
          </p>
        </div>
      </div>

      <div className="recording__layout">
        <section>
          <div className={`recording__screen${cropping ? ' is-cropping' : ''}`}>
            <StickFigure pose="stand" color="rgba(255, 255, 255, 0.85)" size={220} strokeWidth={5} />
            {cropping && <div className="recording__cropbox" aria-hidden="true" />}
            {live && (
              <span className="recording__rec">
                <span className="dot dot--rec" /> REC {clock(elapsed)}
              </span>
            )}
            <span className="recording__label">
              {camera.label} · {camera.resolution} · {camera.fps} fps
            </span>
          </div>

          <div className="recording__timeline">
            <label>
              In
              <input
                type="range"
                min={0}
                max={100}
                value={inPoint}
                aria-label="Cut start"
                onChange={(e) => setInPoint(Math.min(Number(e.target.value), outPoint - 1))}
              />
            </label>
            <label>
              Out
              <input
                type="range"
                min={0}
                max={100}
                value={outPoint}
                aria-label="Cut end"
                onChange={(e) => setOutPoint(Math.max(Number(e.target.value), inPoint + 1))}
              />
            </label>
            <div className="recording__bar">
              <span style={{ left: `${inPoint}%`, width: `${outPoint - inPoint}%` }} />
            </div>
          </div>

          <div className="recording__tools">
            <button className="btn btn--ghost btn--sm" aria-pressed={cropping} onClick={() => setCropping((c) => !c)}>
              Crop
            </button>
            <button
              className="btn btn--ghost btn--sm"
              onClick={() => setToast('Cut preview only — trimming is not built yet')}
            >
              Apply cut
            </button>
            <button
              className="btn btn--ghost btn--sm"
              onClick={() => {
                setInPoint(0)
                setOutPoint(100)
                setCropping(false)
              }}
            >
              Reset
            </button>
          </div>
        </section>

        <aside className="recording__side">
          <dl>
            <dt>Camera</dt>
            <dd>{camera.label}</dd>
            <dt>Resolution</dt>
            <dd>{camera.resolution}</dd>
            <dt>Frame rate</dt>
            <dd>{camera.fps} fps</dd>
            <dt>Duration</dt>
            <dd>{isNew ? '—' : recording?.duration}</dd>
            <dt>Motion</dt>
            <dd>{motion ? <Link to={`/motions/${motion.id}`}>{motion.name}</Link> : 'Not in a motion yet'}</dd>
          </dl>

          {isNew && (
            <button
              className={`btn btn--block ${live ? 'btn--ghost' : 'btn--pink'}`}
              onClick={() => {
                if (live) {
                  setLive(false)
                  setToast('Recording saved — preview only for now')
                } else {
                  setElapsed(0)
                  setLive(true)
                }
              }}
            >
              {live ? `Stop · ${clock(elapsed)}` : 'Start recording'}
            </button>
          )}
        </aside>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  )
}
