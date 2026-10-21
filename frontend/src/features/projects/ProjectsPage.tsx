import { useState } from 'react'
import { useStudio } from '@/app/StudioProvider'
import { NewProjectDialog } from '@/components/ui/NewProjectDialog'
import { ProjectCard } from '@/components/ui/ProjectCard'
import { PlusIcon } from '@/components/ui/Icons'
import { motionsInProject } from '@/lib/motions'

export function ProjectsPage() {
  const { projects, motions } = useStudio()
  const [dialog, setDialog] = useState(false)

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Projects</h1>
          <p className="page-sub">Folders that group the motions for one subject or goal.</p>
        </div>
        <button className="btn btn-project" onClick={() => setDialog(true)}>
          <PlusIcon />
          New project
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="no-cards">No projects yet.</div>
      ) : (
        <div className="grid-cards">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} motions={motionsInProject(motions, p.id)} />
          ))}
        </div>
      )}

      {dialog && <NewProjectDialog onClose={() => setDialog(false)} />}
    </div>
  )
}
