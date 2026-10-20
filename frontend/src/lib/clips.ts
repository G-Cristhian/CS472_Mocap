// Uploaded clips, stored in Supabase (schema in supabase/clips.sql).

import { createClient } from '@supabase/supabase-js'
import type { Accent, Clip, Pose, Source } from '@/types'

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const supabase = url && key ? createClient(url, key) : null

const BUCKET = 'clips'
const ACCENTS: Accent[] = ['purple', 'blue', 'pink', 'orange', 'amber']
const POSE: Record<Source, Pose> = { ai: 'run', suit: 'walk', review: 'lunge' }

interface ClipRow {
  id: string
  name: string
  project_id: string
  project_name: string
  source: Source
  duration: string
  file_path: string
}

function toClip(row: ClipRow, index: number): Clip {
  return {
    id: row.id,
    name: row.name,
    projectId: row.project_id,
    projectName: row.project_name,
    duration: row.duration,
    source: row.source,
    accent: ACCENTS[index % ACCENTS.length],
    pose: POSE[row.source],
    fileUrl: supabase!.storage.from(BUCKET).getPublicUrl(row.file_path).data.publicUrl,
  }
}

export async function listClips(): Promise<Clip[]> {
  if (!supabase) return []
  const { data, error } = await supabase.from('clips').select('*').order('created_at', { ascending: false })
  if (error) throw new Error(error.message)
  return (data as ClipRow[]).map(toClip)
}

/** idk claude did this frfr "m:ss" from a BVH header (Frames × Frame Time); "0:00" if the header can't be read. */
async function bvhDuration(file: File): Promise<string> {
  const head = await file.slice(0, 64 * 1024).text()
  const frames = Number(/Frames:\s*(\d+)/.exec(head)?.[1])
  const frameTime = Number(/Frame Time:\s*([\d.eE+-]+)/.exec(head)?.[1])
  const seconds = Math.round(frames * frameTime) || 0
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export interface UploadClipInput {
  file: File
  name: string
  projectId: string
  projectName: string
  source: Source
}

// Stores the file in the bucket
export async function uploadClip({ file, name, projectId, projectName, source }: UploadClipInput): Promise<Clip> {
  if (!supabase) throw new Error('Supabase is not set up: add its URL and key to frontend/.env.local')
  const path = `${projectId}/${crypto.randomUUID()}-${file.name.replace(/[^\w.-]+/g, '_')}`
  const stored = await supabase.storage.from(BUCKET).upload(path, file, { contentType: 'text/plain' })
  if (stored.error) throw new Error(stored.error.message)

  const row = { name, project_id: projectId, project_name: projectName, source, duration: await bvhDuration(file), file_path: path }
  const { data, error } = await supabase.from('clips').insert(row).select().single()
  if (error) throw new Error(error.message)
  return toClip(data as ClipRow, 0)
}
