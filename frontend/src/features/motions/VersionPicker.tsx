import { useEffect, useRef, useState } from 'react'
import { POSE_LABEL, SOURCE_LABEL, type ApiMotionVersion } from '@/lib/motions'
import './versions.css'

/** "v2 · Pipeline · MediaPipe", with the status when the version is not finished yet. */
function versionName(v: ApiMotionVersion) {
  const pose = v.source === 'pipeline' && POSE_LABEL[v.pose_model] ? ` · ${POSE_LABEL[v.pose_model]}` : ''
  const status = v.status === 'done' ? '' : ` · ${v.status}`

  return `v${v.number} · ${SOURCE_LABEL[v.source] ?? v.source}${pose}${status}`
}

/**
 * The version the motion page shows. The dashed link opens the list to pick another one, or to
 * start a new version: that takes you to the processing settings, where the pose model is chosen.
 */
export function VersionPicker({
  versions,
  current,
  onSelect,
  onNewVersion,
}: {
  versions: ApiMotionVersion[]
  current: ApiMotionVersion | null
  onSelect: (uuid: string) => void
  /** shows the processing settings; nothing is rendered until Start rendering is pressed there */
  onNewVersion: () => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // a click anywhere else closes the list
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)

    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  return (
    <div className="version" ref={ref}>
      <button
        type="button"
        className="version__link"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {current ? versionName(current) : 'No version yet'}
      </button>

      {open && (
        <div className="version__menu" role="menu">
          {versions.map((v) => (
            <button
              key={v.uuid}
              type="button"
              role="menuitem"
              aria-current={v.uuid === current?.uuid}
              onClick={() => {
                onSelect(v.uuid)
                setOpen(false)
              }}
            >
              {versionName(v)}
            </button>
          ))}
          {versions.length > 0 ? (
            <button
              type="button"
              role="menuitem"
              className="version__new"
              title="Pick the pose model on the left, then press Start rendering"
              onClick={() => {
                onNewVersion()
                setOpen(false)
              }}
            >
              New version
            </button>
          ) : (
            <p className="version__note">
              Start rendering to save the first result as version 1. After that you can render again with another pose
              model, or make a manual edit of a finished version.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
