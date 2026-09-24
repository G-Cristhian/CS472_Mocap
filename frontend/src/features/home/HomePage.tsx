import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useSettings, type HomeVariant } from '@/app/SettingsProvider'
import { useStudio } from '@/app/StudioProvider'
import { NewProjectDialog } from '@/components/ui/NewProjectDialog'
import { ProjectCard, ProjectRow } from '@/components/ui/ProjectCard'
import { StickFigure } from '@/components/ui/StickFigure'
import { PlusIcon } from '@/components/ui/Icons'
import { currentUser } from '@/lib/data'
import type { Project } from '@/types'
import './home.css'

const VARIANTS: { id: HomeVariant; label: string }[] = [
  { id: 'a', label: 'A — Cards' },
  { id: 'b', label: 'B — Hero' },
  { id: 'c', label: 'C — Minimal' },
]

export function HomePage() {
  const { settings, update } = useSettings()
  const { projects } = useStudio()
  const [params, setParams] = useSearchParams()
  const [dialog, setDialog] = useState(false)
  const recent = projects.slice(0, 4)
  const variant = settings.homeVariant

  // ?layout=a|b|c makes a single home concept shareable with the team.
  const requested = params.get('layout') as HomeVariant | null
  useEffect(() => {
    if (requested && requested !== variant && VARIANTS.some((v) => v.id === requested)) {
      update({ homeVariant: requested })
    }
  }, [requested, variant, update])

  function pick(id: HomeVariant) {
    update({ homeVariant: id })
    const next = new URLSearchParams(params)
    next.set('layout', id)
    setParams(next, { replace: true })
  }

  return (
    <>
      <div className="variants">
        <div className="variants__inner">
          <span className="variants__label">Home layout</span>
          <div className="segmented">
            {VARIANTS.map((v) => (
              <button
                key={v.id}
                aria-pressed={variant === v.id}
                onClick={() => pick(v.id)}
              >
                {v.label}
              </button>
            ))}
          </div>
          <span className="variants__note">
            All three home concepts from the screens deck — pick one and the rest of the app stays
            the same.
          </span>
        </div>
      </div>

      {variant === 'a' && <HomeCards projects={recent} onNewProject={() => setDialog(true)} />}
      {variant === 'b' && (
        <HomeHero projects={projects.slice(0, 3)} onNewProject={() => setDialog(true)} />
      )}
      {variant === 'c' && <HomeMinimal projects={recent} onNewProject={() => setDialog(true)} />}

      {dialog && <NewProjectDialog onClose={() => setDialog(false)} />}
    </>
  )
}

interface VariantProps {
  projects: Project[]
  onNewProject: () => void
}

/* ---------------- Variant A — card grid ---------------- */
function HomeCards({ projects, onNewProject }: VariantProps) {
  return (
    <div className="page">
      <div className="homeA__top">
        <div>
          <h1 className="homeA__title">Welcome back, {currentUser.name}</h1>
          <p className="homeA__sub">
            Pick up a project, or calibrate the suit once and let the cameras carry the rest of the
            session.
          </p>
          <div className="homeA__actions">
            <Link className="btn btn--primary" to="/record">
              <span className="dot" style={{ background: '#fff' }} />
              New recording
            </Link>
            <button className="btn btn--ghost" onClick={onNewProject}>
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
        {projects.map((p) => (
          <ProjectCard key={p.id} project={p} />
        ))}
      </div>
    </div>
  )
}

/* ---------------- Variant B — purple hero ---------------- */
function HomeHero({ projects, onNewProject }: VariantProps) {
  return (
    <>
      <section className="homeB__hero">
        <div className="homeB__heroInner">
          <div>
            <h1>Welcome back, {currentUser.name}</h1>
            <p>
              {currentUser.suit} is calibrated and four cameras are online. You are ready to record.
            </p>
            <div className="homeB__heroActions">
              <Link className="btn btn--white" to="/record">
                <span className="dot dot--rec" />
                New recording
              </Link>
              <button className="btn btn--outline-white" onClick={onNewProject}>
                New project
              </button>
            </div>
          </div>
          <div className="homeB__art">
            <StickFigure pose="arms-up" color="#fff" headColor="var(--amber)" size={190} strokeWidth={4.5} />
          </div>
        </div>
      </section>

      <div className="page" style={{ paddingTop: 34 }}>
        <div className="section-head" style={{ marginTop: 0 }}>
          <h2 className="section-title">Recent projects</h2>
          <Link to="/projects">View all projects</Link>
        </div>
        <div className="homeB__rows">
          {projects.map((p) => (
            <ProjectRow key={p.id} project={p} />
          ))}
        </div>
      </div>
    </>
  )
}

/* ---------------- Variant C — minimal list ---------------- */
function HomeMinimal({ projects, onNewProject }: VariantProps) {
  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })

  return (
    <div className="homeC">
      <div className="homeC__head">
        <div>
          <p className="eyebrow">{today}</p>
          <h1 className="homeC__title">
            Welcome back, <b>{currentUser.name}</b>
          </h1>
          <p className="homeC__status">
            {currentUser.suit} calibrated · 4 cameras online ·{' '}
            <Link to="/settings/calibration">recalibrate</Link>
          </p>
        </div>
        <div className="homeC__actions">
          <Link className="btn btn--blue" to="/record">
            <span className="dot" style={{ background: 'var(--ink)' }} />
            New recording
          </Link>
          <button className="btn btn--ghost" onClick={onNewProject}>
            New project
          </button>
        </div>
      </div>

      <div className="section-head">
        <p className="eyebrow">Recent projects</p>
        <Link to="/projects">All projects</Link>
      </div>

      <div className="ctable">
        {projects.map((p) => (
          <Link key={p.id} className="ctable__row" to={`/projects/${p.id}`}>
            <StickFigure pose={p.pose} color="var(--ink)" size={40} strokeWidth={6} />
            <span className="ctable__name">{p.name}</span>
            <span className="ctable__cell">{p.sport}</span>
            <span className="ctable__cell">{p.clips} clips</span>
            <span className="ctable__cell">{p.updated}</span>
            <span className={`ctable__tag ${p.source === 'suit' ? 'fg--blue' : 'fg--purple'}`}>
              {p.source === 'suit' ? 'Suit' : p.source === 'ai' ? 'AI' : 'Review'}
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}
