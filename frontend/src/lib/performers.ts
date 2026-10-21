import { DJANGO_URL, djangoJson } from '@/lib/django'

/** A performer in the logged-in user's list, as the Django API returns it. */
export interface Performer {
  id: number
  full_name: string
  email: string
  phone: string
  height_m: number | null
  created_at: string
}

/** The details a performer is saved with. */
export interface PerformerInput {
  full_name: string
  height_m: number | null
  email: string
  phone: string
}

const BASE = `${DJANGO_URL}/api/v1/performers/`

/** The logged-in user's performers, by name. */
export function listPerformers(): Promise<Performer[]> {
  return djangoJson<Performer[]>(BASE)
}

/** Adds a performer to the logged-in user's list. */
export function createPerformer(input: PerformerInput): Promise<Performer> {
  return djangoJson<Performer>(BASE, { method: 'POST', body: JSON.stringify(input) })
}

/** Changes one of the logged-in user's performers. */
export function updatePerformer(id: number, input: PerformerInput): Promise<Performer> {
  return djangoJson<Performer>(`${BASE}${id}/`, { method: 'PATCH', body: JSON.stringify(input) })
}
