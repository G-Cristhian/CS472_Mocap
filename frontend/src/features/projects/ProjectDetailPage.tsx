import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import { MotionCard } from '@/components/ui/MotionCard'
import { NewMotionDialog } from '@/components/ui/NewMotionDialog'
import { PlusIcon } from '@/components/ui/Icons'
import './projects.css'

export function ProjectDetailPage() {
  const { projectId } = useParams()
  const { projects, motions } = useStudio()
  const [dialog, setDialog] = useState(false)

  const project = projects.find((p) => p.id === projectId)
  const projectMotions = motions.filter((m) => m.projectId === projectId)

  if (!project) {
    return (
      <div className="page">
        <h1 className="page-title">Project not found</h1>
        <p className="page-sub">It may have been renamed or removed.</p>
        <p style={{ marginTop: 20 }}>
          <Link className="btn btn--primary" to="/projects">
            Back to projects
          </Link>
        </p>
      </div>
    )
  }

  return (
    <div className="page">
      <nav className="ws__crumbs" aria-label="Breadcrumb">
        <Link to="/projects">Projects</Link>
        <span style={{ color: 'var(--muted-2)' }}>/</span>
        <b>{project.name}</b>
      </nav>

      <div className="page-head" style={{ marginTop: 16 }}>
        <div>
          <h1 className="page-title">{project.name}</h1>
          <p className="page-sub">
            {project.category} · {projectMotions.length} {projectMotions.length === 1 ? 'motion' : 'motions'}
          </p>
        </div>
        <button className="btn btn-project" onClick={() => setDialog(true)}>
          <PlusIcon />
          New motion
        </button>
      </div>

      {projectMotions.length === 0 ? (
        <div className="no-cards">No motions in this project yet. Create one, then add its recordings.</div>
      ) : (
        <div className="grid-cards">
          {projectMotions.map((motion) => (
            <MotionCard key={motion.id} motion={motion} />
          ))}
        </div>
      )}

      {dialog && <NewMotionDialog projectId={project.id} onClose={() => setDialog(false)} />}
    </div>
  )
}
