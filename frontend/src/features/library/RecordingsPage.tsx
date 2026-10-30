import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { RecordingCard } from '@/components/ui/RecordingCard'
import { listRecordings, uploadRecording } from '@/lib/recordings'
import { SearchIcon } from '@/components/ui/Icons'
import type { Recording } from '@/types'

export function RecordingsPage() {
  const fileInput = useRef<HTMLInputElement>(null)
  // null while the list is loading; the user's own recordings after that
  const [recordings, setRecordings] = useState<Recording[] | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // for a search bar!
  const [searchBox, setSearchBox] = useState('') // creates the list
  const searchText = searchBox.trim()            // excludes space before and after typed text
  const recList = recordings ?? []            // if recordings null, use empty list instead
  const searchDisplay = searchText ? recList.filter((rec) =>
    rec.name.toLowerCase().includes(searchText.toLowerCase())): recList


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

      <div className = "page-search-bar">
        <label className = "search page-search">
          <SearchIcon />
          <input
            type = "search"
            placeholder = "Type here to find your recording!"
            aria-label = "Search box for recordings"
            value = {searchBox}
            onChange = {(event) => setSearchBox(event.target.value)}
            onKeyDown = {(event) =>
              {if (event.key == 'Escape')
                setSearchBox('')}}
          />
        </label>
      </div>

      {recordings === null ? null : recordings.length === 0 ? (
        <div className="no-cards">No recordings yet.</div>
      ) : searchDisplay.length === 0 ? (
        <div className = "no-cards">
          <p> No match found for "{searchText}". </p>
          <button
            type = "button"
            className = "btn btn-project"
            style = {{ marginTop: 16 }}
            onClick = {() => setSearchBox('')}>
              Clear search
            </button>
        </div>
      ) : (
        <div className="grid-cards">
          {searchDisplay.map((recording) => (
            <RecordingCard key={recording.id} recording={recording} motionName={null} />
          ))}
        </div>
      )}
    </div>
  )
}
