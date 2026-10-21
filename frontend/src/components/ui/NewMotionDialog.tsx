import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import { Modal } from './Modal'

/**
 * A motion can go into a project or into none. Opened from a project (projectId given), the motion goes
 * into that project; otherwise the user may pick one or leave it out.
 */
export function NewMotionDialog({ projectId, onClose }: { projectId?: string; onClose: () => void }) {
  const { createMotion, projects } = useStudio()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [chosen, setChosen] = useState(projectId ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    try {
      const motion = await createMotion({ name: name.trim(), projectId: chosen || null })
      onClose()
      navigate(`/motions/${motion.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the motion.')
      setSaving(false)
    }
  }

  return (
    <Modal
      title="New motion"
      subtitle="A motion is one skeleton, built from two to four recordings of the same performance."
      onClose={onClose}
    >
      <form onSubmit={onSubmit}>
        {!projectId && (
          <label className="field">
            <span className="field__label">Project (optional)</span>
            <select className="select" value={chosen} onChange={(e) => setChosen(e.target.value)}>
              <option value="">No project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="field" style={{ marginTop: projectId ? 0 : 18 }}>
          <span className="field__label">Motion name</span>
          <input
            className="input"
            value={name}
            autoFocus
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Mario jumping"
          />
        </label>

        {error && (
          <p role="alert" style={{ color: 'var(--pink)', fontSize: 14, marginTop: 14 }}>
            {error}
          </p>
        )}

        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--primary" disabled={!name.trim() || saving}>
            {saving ? 'Creating…' : 'Create motion'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
