import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import { Toast } from '@/components/ui/Modal'
import { ApiUnreachableError, API_URL } from '@/lib/api'
import { supabase } from '@/lib/clips'
import { listFootage, processFootage, uploadFootage, type Footage } from '@/lib/footage'
import './footage.css'

type Filter = 'waiting' | 'processed'

function sizeLabel(bytes: number) {
  return bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : `${Math.round(bytes / 1024 ** 2)} MB`
}

function message(e: unknown) {
  if (e instanceof ApiUnreachableError) return `Can't reach the API at ${API_URL}`
  return e instanceof Error ? e.message : String(e)
}

export function FootagePage() {
  const { projects } = useStudio()
  const navigate = useNavigate()
  const fileInput = useRef<HTMLInputElement>(null)

  const [footage, setFootage] = useState<Footage[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Filter>('waiting')
  /** footage ids in camera order: the first ticked is cam0 */
  const [selected, setSelected] = useState<string[]>([])
  const [uploading, setUploading] = useState<string | null>(null)
  const [processing, setProcessing] = useState(false)
  const [name, setName] = useState('')
  const [projectId, setProjectId] = useState(projects[0]?.id ?? '')
  const [height, setHeight] = useState('1.75')
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    listFootage()
      .then(setFootage)
      .catch((e) => setToast(`Couldn't load footage: ${message(e)}`))
      .finally(() => setLoading(false))
  }, [])

  const shown = footage.filter((f) => (filter === 'waiting' ? !f.take_id : !!f.take_id))
  const heightM = Number(height)
  const heightOk = heightM >= 1 && heightM <= 2.5
  const ready = selected.length >= 2 && heightOk && !!projectId && !processing

  const toggle = (id: string) =>
    setSelected((list) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]))

  const upload = async (files: FileList | null) => {
    if (!files) return
    for (const [i, file] of [...files].entries()) {
      setUploading(`Uploading ${file.name} (${i + 1} of ${files.length})…`)
      try {
        const added = await uploadFootage(file)
        setFootage((list) => [added, ...list])
      } catch (e) {
        setToast(`${file.name} didn't upload: ${message(e)}`)
      }
    }
    setUploading(null)
    if (fileInput.current) fileInput.current.value = ''
  }

  const process = async () => {
    if (!ready) return
    setProcessing(true)
    try {
      const videos = selected.map((id) => footage.find((f) => f.id === id)!)
      const take = await processFootage({ videos, heightM, name: name.trim(), projectId })
      setFootage((list) => list.map((f) => (selected.includes(f.id) ? { ...f, take_id: take.id, project_id: projectId } : f)))
      navigate(`/projects/${projectId}?clip=${encodeURIComponent(take.id)}`)
    } catch (e) {
      setToast(`Processing didn't start: ${message(e)}`)
      setProcessing(false)
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Footage</h1>
          <p className="page-sub">
            Camera videos that haven't been synced yet. Tick one video per camera, then process them into a take.
          </p>
        </div>
        <button
          className="btn btn--primary"
          disabled={!supabase || !!uploading}
          onClick={() => fileInput.current?.click()}
        >
          Upload videos
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".mov,.mp4"
          multiple
          hidden
          onChange={(e) => upload(e.target.files)}
        />
      </div>

      {!supabase && <div className="empty">Uploads are off: add the Supabase URL and key to frontend/.env.</div>}
      {uploading && <p className="footage__status">{uploading}</p>}

      <div className="footage__chips">
        <button className="chip" aria-pressed={filter === 'waiting'} onClick={() => setFilter('waiting')}>
          Waiting
        </button>
        <button className="chip" aria-pressed={filter === 'processed'} onClick={() => setFilter('processed')}>
          Processed
        </button>
      </div>

      {loading ? (
        <div className="empty">Loading footage…</div>
      ) : shown.length === 0 ? (
        <div className="empty">
          {filter === 'waiting' ? 'No videos waiting. Upload the videos from each camera.' : 'Nothing processed yet.'}
        </div>
      ) : (
        <div>
          {shown.map((f) => {
            const camera = selected.indexOf(f.id)
            return (
              <div key={f.id} className="footrow">
                {f.take_id ? (
                  <span className="footrow__cam" />
                ) : (
                  <label className="check">
                    <input type="checkbox" checked={camera >= 0} onChange={() => toggle(f.id)} />
                    <span className="footrow__cam mono">{camera >= 0 ? `CAM ${camera + 1}` : ''}</span>
                  </label>
                )}
                <span className="footrow__name">{f.name}</span>
                <span className="spacer" />
                <span className="mono footrow__meta">{sizeLabel(f.size_bytes)}</span>
                <span className="mono footrow__meta">{new Date(f.created_at).toLocaleDateString()}</span>
                {f.take_id && (
                  <Link className="footrow__take" to={`/projects/${f.project_id ?? projectId}?clip=${encodeURIComponent(f.take_id)}`}>
                    Open take
                  </Link>
                )}
              </div>
            )
          })}
        </div>
      )}

      {selected.length > 0 && filter === 'waiting' && (
        <div className="footage__process">
          <label className="field">
            <span className="field__label">Take name</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Take 05" />
          </label>
          <label className="field">
            <span className="field__label">Project</span>
            <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Performer height (m)</span>
            <input
              className="input"
              type="number"
              step="0.01"
              min="1"
              max="2.5"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
            />
          </label>
          <button className="btn btn--primary" disabled={!ready} onClick={process}>
            {processing
              ? 'Sending videos…'
              : selected.length < 2
                ? 'Pick at least 2 cameras'
                : `Sync & process ${selected.length} videos`}
          </button>
        </div>
      )}

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  )
}
