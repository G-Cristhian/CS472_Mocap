import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import { NewProjectDialog } from '@/components/ui/NewProjectDialog'
import { ProjectCard } from '@/components/ui/ProjectCard'
import { PlusIcon } from '@/components/ui/Icons'
import { useAuth } from '@/app/AuthProvider'
import { firstName } from '@/lib/auth'
import { currentUser } from '@/lib/data'
import './home.css'

export function HomePage() {
  const { projects, motions } = useStudio()
  const { user } = useAuth()
  const [dialog, setDialog] = useState(false)
  const navigate = useNavigate()
  const greetingName = user ? firstName(user) : ''
  const recent = projects.slice(0, 4)

  return (
    <>
      <div className="page">
        <div className="homeA__top">
          <div>
            <h1 className="homeA__title">Welcome back, {greetingName}</h1>
            <p className="homeA__sub">
              Pick up a project, or calibrate the suit once and let the cameras carry the rest of the
              session.
            </p>
            <div className="homeA__actions">
              <button type="button" className="btn btn-recording" onClick={() => navigate('/recordings/new')}>
                <span className="dot dot--rec" />
                New recording
              </button>
              <button className="btn btn-project" onClick={() => setDialog(true)}>
                <PlusIcon />
                New project
              </button>
            </div>
          </div>

          <div className="pill">
            <span className="dot dot--live" />
            <span>
              Skeleton calibrated from <b>{currentUser.suit}</b> · 4 cameras online
            </span>
            <Link className="btn btn--sm btn--white" to="/settings/calibration">
              Recalibrate
            </Link>
          </div>
        </div>

        <div className="section-head">
          <h2 className="section-title">Recent projects</h2>
          <Link to="/projects">View all projects</Link>
        </div>
        <div className="grid-cards">
          {recent.map((p) => (
            <ProjectCard key={p.id} project={p} motions={motions.filter((m) => m.projectId === p.id)} />
          ))}
        </div>
      </div>

      {dialog && <NewProjectDialog onClose={() => setDialog(false)} />}
    </>
  )
}
