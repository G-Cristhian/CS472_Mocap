import { useEffect, useState } from 'react'
import { useAuth } from '@/app/AuthProvider'
import { Modal } from '@/components/ui/Modal'
import { displayName } from '@/lib/auth'
import { getRecording } from '@/lib/recordings'
import type { Recording } from '@/types'
import { PerformerPanel } from '@/features/recordings/PerformerPanel'
// the performer form's styles live with the recording page
import '@/features/recordings/recordings.css'

interface Props {
  /** The recording's own uuid (not the motion link's) */
  recordingId: string
  /** "Cam 1" and so on, for the title */
  cameraLabel: string
  onSaved: () => void
  onClose: () => void
}

/**
 * Sets who is in one camera's recording without leaving the motion: the recording page's
 * Performer panel inside a dialog. It loads the recording first, because the motion only
 * lists the height a recording counts with, not the recording's own height the form edits.
 */
export function PerformerDialog({ recordingId, cameraLabel, onSaved, onClose }: Props) {
  const { user } = useAuth()
  const [recording, setRecording] = useState<Recording | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getRecording(recordingId)
      .then((r) => {
        if (!cancelled) setRecording(r)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load the recording.')
      })
    return () => {
      cancelled = true
    }
  }, [recordingId])

  return (
    <Modal
      title={`Performer for ${cameraLabel}`}
      subtitle="Pick who is in this recording, or set its own height."
      onClose={onClose}
    >
      {error && (
        <p role="alert" style={{ color: 'var(--pink)', fontSize: 14 }}>
          {error}
        </p>
      )}
      {!recording && !error && <p style={{ color: 'var(--muted)', fontSize: 14 }}>Loading…</p>}
      {recording && (
        <PerformerPanel
          recordingId={recording.id}
          performerId={recording.performerId ?? null}
          performerHeight={recording.performerHeight ?? null}
          accountName={user ? displayName(user) : ''}
          onSaved={(saved) => {
            setRecording(saved)
            onSaved()
          }}
        />
      )}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onClose}>
          Done
        </button>
      </div>
    </Modal>
  )
}
