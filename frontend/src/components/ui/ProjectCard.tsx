import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import type { Accent, Motion, Project } from '@/types'
import { StickFigure } from './StickFigure'
import './cards.css'

/** The first motion's colour and pose stand in for the project's cover. */
function cover(motions: Motion[]): { accent: Accent; pose: Motion['pose'] } {
  return { accent: motions[0]?.accent ?? 'purple', pose: motions[0]?.pose ?? 'stand' }
}

/** Passes the accent to the stylesheet as --accent, so the card itself stays neutral. */
function accentStyle(accent: Accent) {
  return { '--accent': `var(--${accent})` } as CSSProperties
}

function countLabel(count: number) {
  return `${count} ${count === 1 ? 'motion' : 'motions'}`
}

export function ProjectCard({ project, motions }: { project: Project; motions: Motion[] }) {
  const { accent, pose } = cover(motions)

  return (
    <Link className="pcard" to={`/projects/${project.id}`} style={accentStyle(accent)}>
      <div className="pcard__thumb">
        <StickFigure pose={pose} color={`var(--${accent})`} size={104} />
      </div>
      <div className="pcard__title">
        <h3>{project.name}</h3>
      </div>
      <p className="pcard__meta">
        {project.category} · {countLabel(motions.length)}
      </p>
      <p className="pcard__meta">Updated {project.updated.toLowerCase()}</p>
    </Link>
  )
}
