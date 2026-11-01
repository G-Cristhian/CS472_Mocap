import { useEffect, useRef, useState } from 'react'
import { useLocation, useRouteError } from 'react-router-dom'
import './CrashScreen.css'

// Written out rather than imported: nothing here may depend on the settings code,
// which could be what crashed the page.
const SETTINGS_KEY = 'hybrid-mocap.settings'

const PAGE_NAMES = new Map([
  ['projects', 'Projects'],
  ['motions', 'Motions'],
  ['recordings', 'Recordings'],
  ['library', 'Recordings'],
  ['streaming', 'Streaming'],
  ['settings', 'Settings'],
])

function resetSettings() {
  try {
    localStorage.removeItem(SETTINGS_KEY)
  } catch {
    /* storage may be unavailable — reload anyway */
  }
  window.location.reload()
}

/** Replaces a page that threw while rendering. `standalone` is for when there's no top nav around it. */
export function CrashScreen({ standalone = false }: { standalone?: boolean }) {
  const error = useRouteError()
  const { pathname } = useLocation()
  const [resetOpen, setResetOpen] = useState(false)
  const headingRef = useRef<HTMLHeadingElement>(null)
  // React Router matches paths case-insensitively, so /Projects opens the same page
  const pageName = PAGE_NAMES.get(pathname.split('/')[1].toLowerCase())

  useEffect(() => {
    console.error(error)
    headingRef.current?.focus()
  }, [error])

  const Container = standalone ? 'main' : 'div'

  return (
    <Container className={`crash${standalone ? ' crash--standalone' : ''}`}>
      <div className="crash__content">
        <div className="crash__header">
          {pageName && <div className="crash__eyebrow">{pageName}</div>}
          <h1 className="crash__title" tabIndex={-1} ref={headingRef}>
            This page couldn’t load
          </h1>
          <p className="crash__message">
            Something went wrong while showing {pageName ?? 'this page'}. Your projects, motions and
            recordings are not affected.
          </p>
        </div>

        <div className="crash__actions">
          <button className="crash__btn crash__btn--primary" onClick={() => window.location.reload()}>
            Reload page
          </button>
          <button
            className="crash__btn crash__btn--secondary"
            onClick={() => window.location.assign('/projects')}
          >
            Go to projects
          </button>
        </div>

        <div className="crash__disclosure">
          <button
            className="crash__toggle"
            aria-expanded={resetOpen}
            aria-controls="crash-reset-panel"
            onClick={() => setResetOpen((open) => !open)}
          >
            <span className="crash__glyph">{resetOpen ? '−' : '+'}</span>
            Still not loading?
          </button>
          {resetOpen && (
            <div className="crash__panel" id="crash-reset-panel">
              <p className="crash__note" id="crash-reset-note">
                Saved display settings can sometimes stop a page from loading. Reset settings returns
                text size, spacing, motion and sound to their defaults, then reloads.
              </p>
              <button
                className="crash__btn crash__btn--reset"
                aria-describedby="crash-reset-note"
                onClick={resetSettings}
              >
                Reset settings
              </button>
            </div>
          )}
        </div>
      </div>
    </Container>
  )
}
