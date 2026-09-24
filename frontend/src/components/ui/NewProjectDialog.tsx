import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import type { Source } from '@/types'
import { Modal } from './Modal'

export function NewProjectDialog({ onClose }: { onClose: () => void }) {
  const { createProject } = useStudio()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [sport, setSport] = useState('Track & Field')
  const [source, setSource] = useState<Source>('suit')

  return (
    <Modal
      title="New project"
      subtitle="A project holds the takes from one session. You can rename it later."
      onClose={onClose}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (!name.trim()) return
          const project = createProject({ name: name.trim(), sport, source })
          onClose()
          navigate(`/projects/${project.id}`)
        }}
      >
        <label className="field">
          <span className="field__label">Project name</span>
          <input
            className="input"
            value={name}
            autoFocus
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Sprint Cycle"
          />
        </label>

        <label className="field" style={{ marginTop: 18 }}>
          <span className="field__label">Sport or category</span>
          <select className="select" value={sport} onChange={(e) => setSport(e.target.value)}>
            <option>Track &amp; Field</option>
            <option>Football</option>
            <option>Sport</option>
            <option>Calibration</option>
            <option>R&amp;D</option>
          </select>
        </label>

        <label className="field" style={{ marginTop: 18 }}>
          <span className="field__label">Default motion source</span>
          <span className="field__hint">How much work the AI does between suit markers.</span>
          <select
            className="select"
            value={source}
            onChange={(e) => setSource(e.target.value as Source)}
          >
            <option value="suit">Suit leads — AI fills gaps</option>
            <option value="ai">AI leads — suit corrects</option>
          </select>
        </label>

        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--primary" disabled={!name.trim()}>
            Create project
          </button>
        </div>
      </form>
    </Modal>
  )
}
