import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import { ClipCard } from '@/components/ui/ClipCard'
import { StickFigure } from '@/components/ui/StickFigure'
import { Badge } from '@/components/ui/Badge'
import { GridIcon, ListIcon, SearchIcon } from '@/components/ui/Icons'
import type { Source } from '@/types'
import './library.css'

type Filter = 'all' | Source

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'suit', label: 'Suit-driven' },
  { id: 'ai', label: 'AI-inferred' },
  { id: 'review', label: 'Needs review' },
]

export function MotionLibraryPage() {
  const { clips } = useStudio()
  const [params, setParams] = useSearchParams()
  const [filter, setFilter] = useState<Filter>('all')
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const query = params.get('q') ?? ''

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return clips.filter((c) => {
      const matches =
        !q || c.name.toLowerCase().includes(q) || c.projectName.toLowerCase().includes(q)
      return matches && (filter === 'all' || c.source === filter)
    })
  }, [clips, query, filter])

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Motion Library</h1>
          <p className="page-sub">Every take you have recorded, across all projects.</p>
        </div>
        <Link className="btn btn--primary" to="/record">
          <span className="dot" style={{ background: '#fff' }} />
          New recording
        </Link>
      </div>

      <div className="library__filters">
        <label className="field library__find">
          <span className="field__label">Find a clip</span>
          <span className="search" style={{ display: 'block', marginTop: 10 }}>
            <SearchIcon />
            <input
              type="search"
              value={query}
              placeholder="Search by clip, project or tag"
              onChange={(e) => {
                const next = new URLSearchParams(params)
                if (e.target.value) next.set('q', e.target.value)
                else next.delete('q')
                setParams(next, { replace: true })
              }}
            />
          </span>
        </label>

        <div className="library__chips">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              className="chip"
              aria-pressed={filter === f.id}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <span className="spacer" />
        <span className="library__count">
          {shown.length} clip{shown.length === 1 ? '' : 's'}
        </span>
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
        <div className="empty">No clips match this search yet.</div>
      ) : view === 'grid' ? (
        <div className="clipgrid">
          {shown.map((clip) => (
            <ClipCard key={clip.id} clip={clip} />
          ))}
        </div>
      ) : (
        <div>
          {shown.map((clip) => (
            <Link
              key={clip.id}
              className="cliprow"
              to={`/projects/${clip.projectId}?clip=${clip.id}`}
            >
              <span className={`cliprow__thumb tint--${clip.accent}`}>
                <StickFigure pose={clip.pose} color={`var(--${clip.accent})`} size={38} strokeWidth={6} />
              </span>
              <span className="stack">
                <span className="cliprow__name">{clip.name}</span>
                <span className="cliprow__project">{clip.projectName}</span>
              </span>
              <span className="spacer" />
              <span className="mono" style={{ color: 'var(--muted)' }}>
                {clip.duration}
              </span>
              <Badge source={clip.source} />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
