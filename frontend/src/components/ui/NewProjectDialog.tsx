import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStudio } from '@/app/StudioProvider'
import { Modal } from './Modal'

// Grouped the way sports-science and movement-analysis work is usually organised
const CATEGORIES: { group: string; options: string[] }[] = [
  {
    group: 'Sport',
    options: [
      'Athletics',
      'American football',
      'Basketball',
      'Fencing',
      'Football (soccer)',
      'Martial arts',
      'Swimming',
      'Table tennis',
      'Tennis',
      'Other sport',
    ],
  },
  {
    group: 'Health and rehabilitation',
    options: ['Gait analysis', 'Rehabilitation', 'Ergonomics'],
  },
  {
    group: 'Research and media',
    options: ['Animation and games', 'Biomechanics research', 'Dance and performance', 'Other'],
  },
]

export function NewProjectDialog({ onClose }: { onClose: () => void }) {
  const { createProject } = useStudio()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [category, setCategory] = useState('Athletics')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    try {
      const project = await createProject({ name: name.trim(), category })
      onClose()
      navigate(`/projects/${project.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the project.')
      setSaving(false)
    }
  }

  return (
    <Modal
      title="New project"
      subtitle="A project groups the recordings of one athlete, exercise or training block."
      onClose={onClose}
    >
      <form onSubmit={onSubmit}>
        <label className="field">
          <span className="field__label">Project name</span>
          <input
            className="input"
            value={name}
            autoFocus
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Sprint Cycle"
          />
        </label>

        <label className="field" style={{ marginTop: 18 }}>
          <span className="field__label">Category</span>
          <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((group) => (
              <optgroup key={group.group} label={group.group}>
                {group.options.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </optgroup>
            ))}
          </select>
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
            {saving ? 'Creating…' : 'Create project'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
