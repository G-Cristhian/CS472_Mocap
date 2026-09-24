import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { clips as seedClips, projects as seedProjects } from '@/lib/data'
import type { Accent, Clip, Project, Source } from '@/types'

interface NewProjectInput {
  name: string
  sport: string
  source: Source
}

interface Ctx {
  projects: Project[]
  clips: Clip[]
  createProject: (input: NewProjectInput) => Project
}

const StudioContext = createContext<Ctx | null>(null)

const ACCENTS: Accent[] = ['purple', 'blue', 'pink', 'orange', 'amber']

function slugify(name: string) {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '') || `project-${Date.now()}`
  )
}

export function StudioProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>(seedProjects)
  const [clips] = useState<Clip[]>(seedClips)

  const value = useMemo<Ctx>(
    () => ({
      projects,
      clips,
      createProject: ({ name, sport, source }) => {
        const project: Project = {
          id: slugify(name),
          name,
          sport: sport || 'Uncategorised',
          clips: 0,
          updated: 'Just now',
          updatedBy: 'you',
          source,
          accent: ACCENTS[projects.length % ACCENTS.length],
          pose: 'stand',
        }
        setProjects((list) => [project, ...list])
        return project
      },
    }),
    [projects, clips],
  )

  return <StudioContext.Provider value={value}>{children}</StudioContext.Provider>
}

export function useStudio() {
  const ctx = useContext(StudioContext)
  if (!ctx) throw new Error('useStudio must be used inside <StudioProvider>')
  return ctx
}
