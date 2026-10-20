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

