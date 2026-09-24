import { Link } from 'react-router-dom'
import type { Project } from '@/types'
import { Badge } from './Badge'
import { StickFigure } from './StickFigure'
import './cards.css'

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link className="pcard" to={`/projects/${project.id}`}>
      <div className={`pcard__thumb tint--${project.accent}`}>
        <StickFigure pose={project.pose} color={`var(--${project.accent})`} size={104} />
      </div>
      <div className="pcard__title">
        <h3>{project.name}</h3>
        <Badge source={project.source} />
      </div>
      <p className="pcard__meta">
        {project.sport} · {project.clips} clips
      </p>
      <p className="pcard__meta">
        Updated {project.updated.toLowerCase()} by {project.updatedBy}
      </p>
    </Link>
  )
}

export function ProjectRow({ project }: { project: Project }) {
  return (
    <Link className={`prow tint--${project.accent}`} to={`/projects/${project.id}`}>
      <div className={`prow__thumb solid--${project.accent}`}>
        <StickFigure pose={project.pose} color="#fff" size={52} strokeWidth={6} />
      </div>
      <div>
        <h3 className="prow__title">{project.name}</h3>
        <p className="prow__meta">
          {project.sport} · {project.clips} clips · updated {project.updated.toLowerCase()} by{' '}
          {project.updatedBy}
        </p>
      </div>
      <span className="spacer" />
      <Badge source={project.source} />
    </Link>
  )
}
