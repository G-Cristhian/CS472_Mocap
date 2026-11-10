import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useAuth } from '@/app/AuthProvider'
import { createMotion as apiCreateMotion, listMotions } from '@/lib/motions'
import { createProject as apiCreateProject, listProjects } from '@/lib/projects'
import { listRecordings } from '@/lib/recordings'
import type { Motion, Project, Recording } from '@/types'

interface NewProjectInput {
  name: string
  category: string
}

interface NewMotionInput {
  name: string
  /** The project to put the motion in, or null for none */
  projectId: string | null
}

interface Ctx {
  projects: Project[]
  motions: Motion[]
  recordings: Recording[]
  recordingsLoading: boolean
  recordingsError: string | null
  refreshRecordings: () => Promise<void>
  createProject: (input: NewProjectInput) => Promise<Project>
  createMotion: (input: NewMotionInput) => Promise<Motion>
  /** Reloads the motion list, e.g. after a motion is added to a project */
  refreshMotions: () => Promise<void>
}

const StudioContext = createContext<Ctx | null>(null)

export function StudioProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [projects, setProjects] = useState<Project[]>([])
  const [motions, setMotions] = useState<Motion[]>([])
  const [recordings, setRecordings] = useState<Recording[]>([])
  const [recordingsLoading, setRecordingsLoading] = useState(false)
  const [recordingsError, setRecordingsError] = useState<string | null>(null)
  const recordingsRequest = useRef(0)

  const refreshRecordings = useCallback(async () => {
    const request = ++recordingsRequest.current
    setRecordingsError(null)
    if (!user) {
      setRecordings([])
      setRecordingsLoading(false)
      return
    }

    setRecordingsLoading(true)
    try {
      const list = await listRecordings()
      if (request === recordingsRequest.current) setRecordings(list)
    } catch {
      if (request === recordingsRequest.current) setRecordingsError("Couldn't load your recordings.")
    } finally {
      if (request === recordingsRequest.current) setRecordingsLoading(false)
    }
  }, [user])

  useEffect(() => {
    setRecordings([])
    void refreshRecordings()
    // Ignore requests from a previous user, an older refresh, or an unmounted provider.
    return () => { recordingsRequest.current += 1 }
  }, [refreshRecordings])

  // Projects and motions belong to the logged-in user: load them after login, clear them on logout
  useEffect(() => {
    if (!user) {
      setProjects([])
      setMotions([])
      return
    }

    Promise.all([listProjects(), listMotions()])
      .then(([projectList, motionList]) => {
        setProjects(projectList)
        setMotions(motionList)
      })
      .catch((e) => console.error("Couldn't load projects and motions:", e))
  }, [user])

  const value = useMemo<Ctx>(
    () => ({
      projects,
      motions,
      recordings,
      recordingsLoading,
      recordingsError,
      refreshRecordings,
      createProject: async (input) => {
        const project = await apiCreateProject(input)
        setProjects((list) => [project, ...list])
        return project
      },
      createMotion: async (input) => {
        const motion = await apiCreateMotion(input)
        setMotions((list) => [motion, ...list])
        return motion
      },
      refreshMotions: async () => {
        try {
          setMotions(await listMotions())
        } catch (e) {
          console.error("Couldn't reload motions:", e)
        }
      },
    }),
    [projects, motions, recordings, recordingsLoading, recordingsError, refreshRecordings],
  )

  return <StudioContext.Provider value={value}>{children}</StudioContext.Provider>
}

export function useStudio() {
  const ctx = useContext(StudioContext)
  if (!ctx) throw new Error('useStudio must be used inside <StudioProvider>')
  return ctx
}
