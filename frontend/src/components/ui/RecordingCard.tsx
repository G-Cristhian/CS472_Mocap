import { useState } from 'react'
import { Link } from 'react-router-dom'
import { recordingThumbnailUrl } from '@/lib/recordings'
import type { Recording } from '@/types'
import './cards.css'

/**
 * One camera's video: its preview image, or a film frame with a play button if no preview can be made.
 * The image is requested every time, so the server makes the preview for recordings that don't have one yet.
 */
export function RecordingCard({ recording, motionName }: { recording: Recording; motionName: string | null }) {
  const [noPreview, setNoPreview] = useState(false)

  return (
    <Link className="rcard" to={`/recordings/${recording.id}`}>
      <div className="rcard__frame">
        {noPreview ? (
          <span className="rcard__play" aria-hidden="true" />
        ) : (
          <img
            className="rcard__image"
            src={recordingThumbnailUrl(recording.id)}
            crossOrigin="use-credentials"
            loading="lazy"
            alt=""
            onError={() => setNoPreview(true)}
          />
        )}
        <span className="rcard__cam">{recording.camera}</span>
        <span className="rcard__time">{recording.duration}</span>
      </div>
      <p className="rcard__name">{recording.name}</p>
      <p className="rcard__project">{motionName ?? 'Not in a motion yet'}</p>
    </Link>
  )
}
