import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { RecordingCard } from '@/components/ui/RecordingCard'
import { listRecordings, uploadRecording } from '@/lib/recordings'
import type { Recording } from '@/types'

export function RecordingsPage() {
  const fileInput = useRef<HTMLInputElement>(null)
  // null while the list is loading; the user's own recordings after that
  const [recordings, setRecordings] = useState<Recording[] | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listRecordings()
      .then(setRecordings)
      .catch((err: unknown) => {
        setRecordings([])
        setError(err instanceof Error ? err.message : 'Could not load your recordings.')
      })
  }, [])

  async function onFileChosen(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = '' // so choosing the same file again still fires onChange
    if (!file) return

    setUploading(true)
    setError(null)
    try {
      const uploaded = await uploadRecording(file)
      setRecordings((list) => [uploaded, ...(list ?? [])])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed. Try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Recordings</h1>
          <p className="page-sub">Single-camera videos. Two to four of them make a motion.</p>
        </div>
        <button
          type="button"
          className="btn btn-recording"
          disabled={uploading}
          onClick={() => fileInput.current?.click()}
        >
          <span className="dot dot--rec" />
          {uploading ? 'Uploading…' : 'New recording'}
        </button>
        <input ref={fileInput} type="file" accept="video/*" hidden onChange={onFileChosen} />
      </div>

      {error && (
        <p className="page-sub" role="alert" style={{ color: 'var(--pink)', marginTop: 16 }}>
          {error}
        </p>
      )}

      {recordings === null ? null : recordings.length === 0 ? (
        <div className="no-cards">No recordings yet.</div>
      ) : (
        <div className="grid-cards">
          {recordings.map((recording) => (
            <RecordingCard key={recording.id} recording={recording} motionName={null} />
          ))}
        </div>
      )}
    </div>
  )
}
