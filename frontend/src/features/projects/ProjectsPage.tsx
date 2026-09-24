import { useMemo, useState } from 'react'
import { useStudio } from '@/app/StudioProvider'
import { NewProjectDialog } from '@/components/ui/NewProjectDialog'
import { ProjectCard, ProjectRow } from '@/components/ui/ProjectCard'
import { GridIcon, ListIcon, PlusIcon, SearchIcon } from '@/components/ui/Icons'
import './projects.css'

type Sort = 'updated' | 'name' | 'clips'

export function ProjectsPage() {
  const { projects } = useStudio()
  const [query, setQuery] = useState('')
  const [mine, setMine] = useState(false)
  const [sort, setSort] = useState<Sort>('updated')
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const [dialog, setDialog] = useState(false)

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = projects.filter((p) => {
      const matches =
        !q ||
        p.name.toLowerCase().includes(q) ||
        p.sport.toLowerCase().includes(q) ||
        p.updatedBy.toLowerCase().includes(q)
      return matches && (!mine || p.updatedBy === 'you')
    })
    return [...list].sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name)
      if (sort === 'clips') return b.clips - a.clips
      return 0
    })
  }, [projects, query, mine, sort])

  return (
    <div className="page">
      <div className="page-head">
        <h1 className="page-title">Projects</h1>
        <button className="btn btn--primary" onClick={() => setDialog(true)}>
          <PlusIcon />
          New project
        </button>
      </div>

      <div className="projects__filters">
        <label className="field projects__find">
          <span className="field__label">Find a project</span>
          <span className="search search--focusring" style={{ display: 'block', marginTop: 10 }}>
            <SearchIcon />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, sport or performer"
            />
          </span>
        </label>

        <span className="spacer" />

        <label className="check">
          <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
          Only my projects
        </label>

        <span className="projects__count">
          {shown.length} project{shown.length === 1 ? '' : 's'}
        </span>

        <label className="field" style={{ width: 200 }}>
          <span className="field__label">Sort by</span>
          <select
            className="select"
            value={sort}
            onChange={(e) => setSort(e.target.value as Sort)}
          >
            <option value="updated">Last updated</option>
            <option value="name">Name</option>
            <option value="clips">Most clips</option>
          </select>
        </label>

        <div className="viewtoggle">
          <button aria-pressed={view === 'grid'} aria-label="Grid view" onClick={() => setView('grid')}>
            <GridIcon />
          </button>
          <button aria-pressed={view === 'list'} aria-label="List view" onClick={() => setView('list')}>
            <ListIcon />
          </button>
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="empty">
          No projects match “{query}”. Try a different name, sport or performer.
        </div>
      ) : view === 'grid' ? (
        <div className="grid-cards">
          {shown.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      ) : (
        <div className="projects__rows">
          {shown.map((p) => (
            <ProjectRow key={p.id} project={p} />
          ))}
        </div>
      )}

      {dialog && <NewProjectDialog onClose={() => setDialog(false)} />}
    </div>
  )
}
