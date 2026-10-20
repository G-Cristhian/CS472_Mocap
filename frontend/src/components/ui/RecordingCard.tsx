import { Link } from 'react-router-dom'
import type { Recording } from '@/types'
import './cards.css'

/** One camera's video: a film frame with a play button, the camera label and the length. */
export function RecordingCard({ recording, motionName }: { recording: Recording; motionName: string | null }) {
  return (
    <Link className="rcard" to={`/recordings/${recording.id}`}>
      <div className="rcard__frame">
        <span className="rcard__cam">{recording.camera}</span>
        <span className="rcard__play" aria-hidden="true" />
        <span className="rcard__time">{recording.duration}</span>
      </div>
      <p className="rcard__name">{recording.name}</p>
      <p className="rcard__project">{motionName ?? 'Not in a motion yet'}</p>
    </Link>
  )
}
