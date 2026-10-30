import { useState } from 'react'
import { useStudio } from '@/app/StudioProvider'
import { NewProjectDialog } from '@/components/ui/NewProjectDialog'
import { ProjectCard } from '@/components/ui/ProjectCard'
import { PlusIcon, SearchIcon } from '@/components/ui/Icons'
import { motionsInProject } from '@/lib/motions'

export function ProjectsPage() {
  const { projects, motions } = useStudio()
  const [dialog, setDialog] = useState(false)
  const [searchBox, setSearchBox] = useState('')

  const searchText = searchBox.trim()
  const searchDisplay = searchText
    ? projects.filter((project) => project.name.toLowerCase().includes(searchText.toLowerCase())
    || (project.category ?? '').toLowerCase().startsWith(searchText.toLowerCase())) : projects

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

      <div className = "page-search-bar">
        <label className = "search page-search">
          <SearchIcon />
          <input
            type = "search"
            placeholder = "Search by name or category."
            aria-label = "Search box for projects"
            value = {searchBox}
            onChange = {(event) => setSearchBox(event.target.value)}
            onKeyDown = {(event) => {
              if(event.key === 'Escape')
                setSearchBox('')
            }}
          />
        </label>
      </div>

      {projects.length === 0 ? (
        <div className="no-cards">No projects yet.</div>
      ) : searchDisplay.length === 0 ? (
        <div className = "no-cards">
          <p>
            No match found for "{searchText}".
          </p>
          <button
            type = "button"
            className = "btn btn-project"
            style = {{marginTop: 16}}
            onClick = {() => setSearchBox('')}>
            Clear search
          </button>
        </div>
      ) : (
        <div className="grid-cards">
          {searchDisplay.map((p) => (
            <ProjectCard key={p.id} project={p} motions={motionsInProject(motions, p.id)} />
          ))}
        </div>
      )}

      {dialog && <NewProjectDialog onClose={() => setDialog(false)} />}
    </div>
  )
}
