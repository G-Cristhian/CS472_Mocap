import { Link } from 'react-router-dom'
import type { Clip } from '@/types'
import { Badge } from './Badge'
import { StickFigure } from './StickFigure'
import './cards.css'

export function ClipCard({ clip }: { clip: Clip }) {
  return (
    <Link className="ccard" to={`/projects/${clip.projectId}?clip=${clip.id}`}>
      <div className={`ccard__thumb tint--${clip.accent}`}>
        <span className="ccard__badge">
          <Badge source={clip.source} />
        </span>
        <StickFigure pose={clip.pose} color={`var(--${clip.accent})`} size={92} />
        <span className="ccard__time">{clip.duration}</span>
      </div>
      <p className="ccard__name">{clip.name}</p>
      <p className="ccard__project">{clip.projectName}</p>
    </Link>
  )
}
