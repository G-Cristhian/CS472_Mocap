import { useEffect, useState, type FormEvent } from 'react'
import { CheckIcon } from '@/components/ui/Icons'
import { Modal } from '@/components/ui/Modal'
import { setMotionRecordings } from '@/lib/motions'
import { listRecordings, recordingThumbnailUrl } from '@/lib/recordings'
import type { Recording } from '@/types'
import './AddRecordingDialog.css'

// a motion uses two to four cameras (the server checks the same limits)
const MIN = 2
const MAX = 4

/** A recording's preview image, or a film frame when it has none or the image fails to load. */
function Preview({ recording }: { recording: Recording }) {
  const [broken, setBroken] = useState(false)

  if (!recording.hasThumbnail || broken) return <span className="rcard__play" aria-hidden="true" />

  return (
    <img
      className="rcard__image"
      src={recordingThumbnailUrl(recording.id)}
      crossOrigin="use-credentials"
      loading="lazy"
      alt=""
      onError={() => setBroken(true)}
    />
  )
}

/**
 * Chooses which of the user's recordings the motion uses: tap a preview to select or unselect it.
 * Two to four must be selected to save. Saving sets the motion's recordings as a whole; the parent reloads.
 */
export function AddRecordingDialog({
  motionId,
  inMotion,
  onSaved,
  onClose,
}: {
  motionId: string
  /** The recordings (by uuid) the motion uses now; they start selected */
  inMotion: string[]
  onSaved: () => void
  onClose: () => void
}) {
  const [recordings, setRecordings] = useState<Recording[] | null>(null)
  const [chosen, setChosen] = useState<string[]>(inMotion)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listRecordings()
      .then(setRecordings)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Could not load your recordings.'))
  }, [])

  const count = chosen.length
  const full = count >= MAX
  const valid = count >= MIN && count <= MAX

  function toggle(id: string) {
    setChosen((list) => {
      if (list.includes(id)) return list.filter((x) => x !== id)

      return list.length >= MAX ? list : [...list, id]
    })
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!valid) return
    setSaving(true)
    setError(null)
    try {
      await setMotionRecordings(motionId, chosen)
      onSaved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the recordings.')
      setSaving(false)
    }
  }

  return (
    <Modal
      title="Recordings in this motion"
      subtitle={`Select the cameras of this motion: at least ${MIN}, at most ${MAX}.`}
      onClose={onClose}
      wide
    >
      <form onSubmit={onSubmit}>
        {recordings === null && !error && <p style={{ color: 'var(--muted)' }}>Loading your recordings…</p>}

        {recordings !== null && recordings.length === 0 && (
          <p style={{ color: 'var(--muted)', fontSize: 14 }}>
            You have no recordings yet. Upload one or record a new one first.
          </p>
        )}

        {recordings !== null && recordings.length > 0 && (
          <div className="pick-grid">
            {recordings.map((r) => {
              const on = chosen.includes(r.id)

              return (
                <button
                  key={r.id}
                  type="button"
                  className={on ? 'pick pick--on' : 'pick'}
                  aria-pressed={on}
                  disabled={saving || (!on && full)}
                  onClick={() => toggle(r.id)}
                >
                  <span className="rcard__frame pick__frame">
                    <Preview recording={r} />
                    {on && (
                      <span className="pick__check">
                        <CheckIcon size={14} />
                      </span>
                    )}
                    <span className="rcard__time">{r.duration}</span>
                  </span>
                  <span className="pick__name">{r.name}</span>
                </button>
              )
            })}
          </div>
        )}

        <p className="pick-hint">
          {count} of {MAX} selected
          {count < MIN ? ` · choose at least ${MIN}` : full ? ' · that is the maximum' : ''}
        </p>

        {error && (
          <p role="alert" style={{ color: 'var(--pink)', fontSize: 14, marginTop: 14 }}>
            {error}
          </p>
        )}

        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--primary" disabled={!valid || saving}>
            {saving ? 'Adding…' : 'Add recordings'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
