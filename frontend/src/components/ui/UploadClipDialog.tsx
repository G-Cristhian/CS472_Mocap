import { useState } from 'react'
import { useStudio } from '@/app/StudioProvider'
import { supabase } from '@/lib/clips'
import type { Source } from '@/types'
import { Modal } from './Modal'

export function UploadClipDialog({ onClose, onUploaded }: { onClose: () => void; onUploaded: (name: string) => void }) {
  const { projects, uploadClip } = useStudio()
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [projectId, setProjectId] = useState(projects[0]?.id ?? '')
  const [source, setSource] = useState<Source>('ai')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const project = projects.find((p) => p.id === projectId)
  const ready = !!file && !!name.trim() && !!project && !busy

  return (
    <Modal
      title="Upload a clip"
      subtitle="Add a BVH file to the library. It is saved to the shared database."
      onClose={onClose}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault()
          if (!ready) return
          setBusy(true)
          setError(null)
          try {
            await uploadClip({ file, name: name.trim(), projectId: project.id, projectName: project.name, source })
            onUploaded(name.trim())
            onClose()
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err))
            setBusy(false)
          }
        }}
      >
        {!supabase && (
          <p className="field__hint">Uploads are off: add the Supabase URL and key to frontend/.env.local.</p>
        )}

        <label className="field">
          <span className="field__label">Motion file</span>
          <input
            className="input"
            type="file"
            accept=".bvh"
            onChange={(e) => {
              const picked = e.target.files?.[0] ?? null
              setFile(picked)
              if (picked && !name) setName(picked.name.replace(/\.bvh$/i, ''))
            }}
          />
        </label>

        <label className="field" style={{ marginTop: 18 }}>
          <span className="field__label">Clip name</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Take 05" />
        </label>

        <label className="field" style={{ marginTop: 18 }}>
          <span className="field__label">Project</span>
          <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <label className="field" style={{ marginTop: 18 }}>
          <span className="field__label">Motion source</span>
          <select className="select" value={source} onChange={(e) => setSource(e.target.value as Source)}>
            <option value="ai">AI-inferred</option>
            <option value="suit">Suit-driven</option>
            <option value="review">Needs review</option>
          </select>
        </label>

        {error && (
          <p className="field__hint" role="alert" style={{ color: 'var(--pink)', marginTop: 12 }}>
            Upload failed: {error}
          </p>
        )}

        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--primary" disabled={!ready || !supabase}>
            {busy ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
