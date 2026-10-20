import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import { Modal } from './Modal'

/** With a projectId (opened from a project) the project is fixed; otherwise the user picks one. */
export function NewMotionDialog({ projectId, onClose }: { projectId?: string; onClose: () => void }) {
  const { createMotion, projects } = useStudio()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [chosen, setChosen] = useState(projectId ?? projects[0]?.id ?? '')

  return (
    <Modal
      title="New motion"
      subtitle="A motion is one skeleton, built from two to four recordings of the same performance."
      onClose={onClose}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (!name.trim() || !chosen) return
          const motion = createMotion({ name: name.trim(), projectId: chosen })
          onClose()
          navigate(`/motions/${motion.id}`)
        }}
      >
        {!projectId && (
          <label className="field">
            <span className="field__label">Project</span>
            <select className="select" value={chosen} onChange={(e) => setChosen(e.target.value)}>
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
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Mario jumping"
          />
        </label>

        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--primary" disabled={!name.trim() || !chosen}>
            Create motion
          </button>
        </div>
      </form>
    </Modal>
  )
}
