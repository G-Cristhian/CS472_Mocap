import { Link } from 'react-router-dom'
import type { Motion } from '@/types'
import { Badge } from './Badge'
import { StickFigure } from './StickFigure'
import './cards.css'

export function MotionCard({ motion }: { motion: Motion }) {
  return (
    <Link className="mcard" to={`/motions/${motion.id}`}>
      <div className="mcard__stage">
        <span className="mcard__chip">Skeleton</span>
        <span className="mcard__badge">
          <Badge source={motion.source} />
        </span>
        <StickFigure pose={motion.pose} color={`var(--${motion.accent})`} size={112} strokeWidth={6} />
        <span className="mcard__time">{motion.duration}</span>
      </div>
      <p className="mcard__name">{motion.name}</p>
      <p className="mcard__project">{motion.projectName}</p>
    </Link>
  )
}
