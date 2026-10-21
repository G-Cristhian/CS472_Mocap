import { useState, type FormEvent } from 'react'
import { useStudio } from '@/app/StudioProvider'
import { addMotionToProject } from '@/lib/motions'
import type { Motion } from '@/types'
import { Modal } from './Modal'

/** Puts a motion into one or more of the user's projects. Projects it is already in are marked, not offered again. */
export function AddToProjectDialog({ motion, onClose }: { motion: Motion; onClose: () => void }) {
  const { projects, refreshMotions } = useStudio()
  const alreadyIn = new Set(motion.projects.map((p) => p.id))
  const [chosen, setChosen] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toAdd = projects.filter((p) => !alreadyIn.has(p.id) && chosen.includes(p.id))

  function toggle(id: string) {
    setChosen((list) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]))
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (toAdd.length === 0) return
    setSaving(true)
    setError(null)

    const results = await Promise.allSettled(toAdd.map((p) => addMotionToProject(motion.id, p.id)))
    await refreshMotions()

    const failed = results.find((r): r is PromiseRejectedResult => r.status === 'rejected')
    if (failed) {
      setError(failed.reason instanceof Error ? failed.reason.message : 'Could not add the motion to every project.')
      setSaving(false)
      return
    }
    onClose()
  }

  return (
    <Modal
      title="Add to project"
      subtitle={`Choose the projects “${motion.name}” should be in. A motion can be in several.`}
      onClose={onClose}
    >
      <form onSubmit={onSubmit}>
        {projects.length === 0 ? (
          <p style={{ color: 'var(--muted)', fontSize: 14 }}>You have no projects yet. Create one first.</p>
        ) : (
          <div className="stack" style={{ gap: 12 }}>
            {projects.map((p) => {
              const already = alreadyIn.has(p.id)

              return (
                <label key={p.id} className="check">
                  <input
                    type="checkbox"
                    checked={already || chosen.includes(p.id)}
                    disabled={already || saving}
                    onChange={() => toggle(p.id)}
                  />
                  {p.name}
                  {already && <span style={{ color: 'var(--muted)', fontSize: 13 }}>· already in it</span>}
                </label>
              )
            })}
          </div>
        )}

        {error && (
          <p role="alert" style={{ color: 'var(--pink)', fontSize: 14, marginTop: 14 }}>
            {error}
          </p>
        )}

        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            {projects.length === 0 ? 'Close' : 'Cancel'}
          </button>
          {projects.length > 0 && (
            <button type="submit" className="btn btn--primary" disabled={toAdd.length === 0 || saving}>
              {saving ? 'Adding…' : 'Add to projects'}
            </button>
          )}
        </div>
      </form>
    </Modal>
  )
}
