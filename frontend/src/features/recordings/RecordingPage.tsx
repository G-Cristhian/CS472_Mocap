import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '@/app/AuthProvider'
import { useStudio } from '@/app/StudioProvider'
import { StickFigure } from '@/components/ui/StickFigure'
import { displayName } from '@/lib/auth'
import { cameras } from '@/lib/data'
import { getRecording, recordingVideoUrl } from '@/lib/recordings'
import type { Recording } from '@/types'
import { PerformerPanel } from './PerformerPanel'
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
 * opened as /recordings/:id it plays a stored video and lets you choose its performer.
 */
export function RecordingPage() {
  const { recordingId } = useParams()
  const { user } = useAuth()
  const { recordings, motions } = useStudio()
  const isNew = recordingId === 'new'
  const found = isNew ? undefined : recordings.find((r) => r.id === recordingId)
  // Recordings uploaded from the Recordings page are not in the studio's list, so fetch them
  const [fetched, setFetched] = useState<Recording | null>(null)
  const [fetchFailed, setFetchFailed] = useState(false)
  useEffect(() => {
    if (isNew || found || !recordingId) return
    getRecording(recordingId).then(setFetched).catch(() => setFetchFailed(true))
  }, [isNew, found, recordingId])
  const recording = found ?? fetched ?? undefined
  const motion = motions.find((m) => m.id === recording?.motionId)
  const camera = cameras[0]
  const accountName = user ? displayName(user) : ''

  const [live, setLive] = useState(false)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!live) return
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => window.clearInterval(id)
  }, [live])

  if (!isNew && !recording) {
    if (!fetchFailed) return <div className="page"><p className="page-sub">Loading recording…</p></div>

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
            {isNew ? 'One camera.' : `${recording?.duration} · ${recording?.origin === 'stream' ? 'Streamed' : 'Uploaded'}`}
          </p>
        </div>
      </div>

      <div className="recording__layout">
        <section>
          <div className="recording__screen">
            {fetched ? (
              <video
                className="recording__video"
                controls
                crossOrigin="use-credentials"
                src={recordingVideoUrl(fetched.id)}
              />
            ) : (
              <StickFigure pose="stand" color="rgba(255, 255, 255, 0.85)" size={220} strokeWidth={5} />
            )}
            {live && (
              <span className="recording__rec">
                <span className="dot dot--rec" /> REC {clock(elapsed)}
              </span>
            )}
            {!fetched && (
              <span className="recording__label">
                {camera.label} · {camera.resolution} · {camera.fps} fps
              </span>
            )}
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

          {fetched && (
            <PerformerPanel
              recordingId={fetched.id}
              performerId={fetched.performerId ?? null}
              accountName={accountName}
              onSaved={(performerId) => setFetched((r) => (r ? { ...r, performerId } : r))}
            />
          )}

          {isNew && (
            <button
              className={`btn btn--block ${live ? 'btn--ghost' : 'btn--pink'}`}
              onClick={() => {
                if (live) {
                  setLive(false)
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
    </div>
  )
}
