import { useNavigate } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import { RecordingCard } from '@/components/ui/RecordingCard'

export function RecordingsPage() {
  const navigate = useNavigate()
  const { recordings, motions } = useStudio()

  const motionName = (motionId: string | null) => motions.find((m) => m.id === motionId)?.name ?? null

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Recordings</h1>
          <p className="page-sub">Single-camera videos. Two to four of them make a motion.</p>
        </div>
        <button type="button" className="btn btn-recording" onClick={() => navigate('/recordings/new')}>
          <span className="dot dot--rec" />
          New recording
        </button>
      </div>

      {recordings.length === 0 ? (
        <div className="empty">No recordings yet.</div>
      ) : (
        <div className="grid-cards">
          {recordings.map((recording) => (
            <RecordingCard key={recording.id} recording={recording} motionName={motionName(recording.motionId)} />
          ))}
        </div>
      )}
    </div>
  )
}
