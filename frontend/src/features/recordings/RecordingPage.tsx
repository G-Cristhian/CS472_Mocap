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
  const { recordings, recordingsLoading, recordingsError, refreshRecordings, motions } = useStudio()
  const isNew = recordingId === 'new'
  const found = isNew ? undefined : recordings.find((r) => r.id === recordingId)
  // Fetch directly if the studio list is pending, failed, or missing a recent upload.
  const [fetched, setFetched] = useState<Recording | null>(null)
  const [fetchFailed, setFetchFailed] = useState(false)
  useEffect(() => {
    setFetched(null)
    setFetchFailed(false)
    if (isNew || found || !recordingId) return
    let cancelled = false
    getRecording(recordingId)
      .then((result) => { if (!cancelled) setFetched(result) })
      .catch(() => { if (!cancelled) setFetchFailed(true) })
    return () => { cancelled = true }
  }, [isNew, found, recordingId, user])
  const recording = (fetched?.id === recordingId ? fetched : undefined) ?? found
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

  const recordingsStatus = (
    <>
      {recordingsLoading && <p className="page-sub" role="status">Loading recordings…</p>}
      {recordingsError && (
        <p className="page-sub" role="alert">
          {recordingsError}{' '}
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => void refreshRecordings()}>
            Retry recordings
          </button>
        </p>
      )}
    </>
  )

  if (!isNew && !recording) {
    if (!fetchFailed) return (
      <div className="page">
        {recordingsStatus}
        <p className="page-sub">Loading recording…</p>
      </div>
    )

    return (
      <div className="page">
        {recordingsStatus}
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
      {recordingsStatus}
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
            {recording ? (
              <video
                className="recording__video"
                controls
                crossOrigin="use-credentials"
                src={recordingVideoUrl(recording.id)}
              />
            ) : (
              <StickFigure pose="stand" color="rgba(255, 255, 255, 0.85)" size={220} strokeWidth={5} />
            )}
            {live && (
              <span className="recording__rec">
                <span className="dot dot--rec" /> REC {clock(elapsed)}
              </span>
            )}
            {!recording && (
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

          {recording && (
            <PerformerPanel
              key={recording.id}
              recordingId={recording.id}
              performerId={recording.performerId ?? null}
              performerHeight={recording.performerHeight ?? null}
              accountName={accountName}
              onSaved={setFetched}
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
