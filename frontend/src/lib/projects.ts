import { DJANGO_URL, djangoJson } from '@/lib/django'
import type { Project } from '@/types'

/** A project as the Django API returns it. */
export interface ApiProject {
  uuid: string
  name: string
  category: string
  created_at: string
  updated_at: string
}

const BASE = `${DJANGO_URL}/api/v1/projects/`

/** How long ago a project changed, for the project cards. */
function updatedText(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} ${minutes === 1 ? 'minute' : 'minutes'} ago`

  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`

  const days = Math.round(hours / 24)
  if (days < 7) return `${days} ${days === 1 ? 'day' : 'days'} ago`

  return `on ${new Date(iso).toLocaleDateString()}`
}

function toProject(api: ApiProject): Project {
  return { id: api.uuid, name: api.name, category: api.category, updated: updatedText(api.updated_at) }
}

/** The logged-in user's projects, most recently changed first. */
export async function listProjects(): Promise<Project[]> {
  const body = await djangoJson<ApiProject[]>(BASE)

  return body.map(toProject)
}

/** Creates a project in the logged-in user's list. */
export async function createProject(input: { name: string; category: string }): Promise<Project> {
  const body = await djangoJson<ApiProject>(BASE, { method: 'POST', body: JSON.stringify(input) })

  return toProject(body)
}
