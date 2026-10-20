// Raw camera videos waiting to be synced, stored in Supabase (schema in supabase/footage.sql).

import { supabase } from './clips'
import { createTake, type Take } from './api'

const BUCKET = 'footage'

export interface Footage {
  id: string
  name: string
  file_path: string
  size_bytes: number
  /** the take it was processed into; null while it is still waiting */
  take_id: string | null
  /** the project that take went into */
  project_id: string | null
  created_at: string
}

function client() {
  if (!supabase) throw new Error('Supabase is not set up: add its URL and key to frontend/.env')
  return supabase
}

/** Every uploaded video, newest first. */
export async function listFootage(): Promise<Footage[]> {
  if (!supabase) return []
  const { data, error } = await supabase.from('footage').select('*').order('created_at', { ascending: false })
  if (error) throw new Error(error.message)
  return data as Footage[]
}

/** Stores the video in the bucket, then records it in the footage table. */
export async function uploadFootage(file: File): Promise<Footage> {
  const db = client()
  const path = `${crypto.randomUUID()}-${file.name.replace(/[^\w.-]+/g, '_')}`
  const stored = await db.storage.from(BUCKET).upload(path, file, { contentType: file.type || 'video/mp4' })
  if (stored.error) throw new Error(stored.error.message)

  const row = { name: file.name, file_path: path, size_bytes: file.size }
  const { data, error } = await db.from('footage').insert(row).select().single()
  if (error) throw new Error(error.message)
  return data as Footage
}

export interface ProcessInput {
  /** one video per camera, in camera order (cam0 first) */
  videos: Footage[]
  heightM: number
  name: string
  projectId: string
}

/** Pulls the videos back down, sends them to the pipeline as one take, and marks them processed. */
export async function processFootage({ videos, heightM, name, projectId }: ProcessInput): Promise<Take> {
  const db = client()
  const files = await Promise.all(
    videos.map(async (v) => {
      const { data, error } = await db.storage.from(BUCKET).download(v.file_path)
      if (error) throw new Error(`${v.name}: ${error.message}`)
      return new File([data], v.name)
    }),
  )
  const take = await createTake({ videos: files, heightM, name, projectId })

  const { error } = await db.from('footage').update({ take_id: take.id, project_id: projectId }).in('id', videos.map((v) => v.id))
  if (error) console.error("Couldn't mark the footage processed:", error.message)
  return take
}
