import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { motions as seedMotions, projects as seedProjects, recordings as seedRecordings } from '@/lib/data'
import type { Accent, Motion, Project, Recording } from '@/types'

interface NewProjectInput {
  name: string
  category: string
}

interface NewMotionInput {
  name: string
  projectId: string
}

interface Ctx {
  projects: Project[]
  motions: Motion[]
  recordings: Recording[]
  createProject: (input: NewProjectInput) => Project
  createMotion: (input: NewMotionInput) => Motion
}

const StudioContext = createContext<Ctx | null>(null)

const ACCENTS: Accent[] = ['purple', 'blue', 'pink', 'orange', 'amber']

function slugify(name: string) {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '') || `item-${Date.now()}`
  )
}

export function StudioProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>(seedProjects)
  const [motions, setMotions] = useState<Motion[]>(seedMotions)
  const [recordings] = useState<Recording[]>(seedRecordings)

  const value = useMemo<Ctx>(
    () => ({
      projects,
      motions,
      recordings,
      createProject: ({ name, category }) => {
        const project: Project = {
          id: slugify(name),
          name,
          category: category || 'Other',
          updated: 'Just now',
        }
        setProjects((list) => [project, ...list])
        return project
      },
      createMotion: ({ name, projectId }) => {
        const project = projects.find((p) => p.id === projectId)
        const motion: Motion = {
          id: slugify(name),
          name,
          projectId,
          projectName: project?.name ?? '',
          duration: '0:00',
          source: 'ai',
          accent: ACCENTS[motions.length % ACCENTS.length],
          pose: 'stand',
        }
        setMotions((list) => [motion, ...list])
        return motion
      },
    }),
    [projects, motions, recordings],
  )

  return <StudioContext.Provider value={value}>{children}</StudioContext.Provider>
}

export function useStudio() {
  const ctx = useContext(StudioContext)
  if (!ctx) throw new Error('useStudio must be used inside <StudioProvider>')
  return ctx
}
