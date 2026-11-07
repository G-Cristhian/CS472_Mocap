import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { CloseIcon, GearIcon, HelpIcon, LogoMark, MoreIcon } from '@/components/ui/Icons'
import { useAuth } from '@/app/AuthProvider'
import './TopNav.css'

const LINKS = [
  { to: '/projects', label: 'Projects' },
  { to: '/motions', label: 'Motions' },
  { to: '/recordings', label: 'Recordings' },
  { to: '/streaming', label: 'Streaming' },
]

const FINE_POINTER = '(any-pointer: fine)'

// Leaving sheet mode needs this much spare width. The bar is shorter in sheet mode, so a page
// scrollbar can come and go with the mode, and without this the two could keep flipping each other.
const SHEET_EXIT_SLACK = 20

interface Layout {
  /** null until the first measurement; the CSS falls back to a media query until then */
  mode: 'full' | 'compact' | 'sheet' | null
  wordmark: boolean
}

function ShortcutList() {
  return (
    <dl className="topnav__shortcuts">
      <dt>R</dt>
      <dd>Start / stop a take</dd>
      <dt>Space</dt>
      <dd>Play or pause the viewport</dd>
      <dt>C</dt>
      <dd>Recalibrate the suit</dd>
    </dl>
  )
}

export function TopNav() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { user, loading, logout } = useAuth()
  const [layout, setLayout] = useState<Layout>({ mode: null, wordmark: true })
  const [sheetOpen, setSheetOpen] = useState(false)
  const [popover, setPopover] = useState<'help' | 'account' | null>(null)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [hasFinePointer, setHasFinePointer] = useState(() => window.matchMedia(FINE_POINTER).matches)

  const barRef = useRef<HTMLElement>(null)
  const fullRowRef = useRef<HTMLDivElement>(null)
  const compactRowRef = useRef<HTMLDivElement>(null)
  const sheetRowRef = useRef<HTMLDivElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const helpButtonRef = useRef<HTMLButtonElement>(null)
  const accountButtonRef = useRef<HTMLButtonElement>(null)
  const sheetRef = useRef<HTMLDivElement>(null)
  const firstSheetLinkRef = useRef<HTMLAnchorElement>(null)

  const displayName = user ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email : ''
  const initial = (user?.first_name || user?.email || '?').charAt(0).toUpperCase()

  const closeSheet = () => {
    setSheetOpen(false)
    menuButtonRef.current?.focus()
  }

  const signOut = async () => {
    setPopover(null)
    closeSheet()
    await logout()
    navigate('/')
  }

  // Font scale and spacing settings change how wide the links are, so pick the mode by what fits.
  // Observing the rows as well as the bar picks up font loading and settings changes.
  useLayoutEffect(() => {
    const bar = barRef.current
    const rows = [fullRowRef.current, compactRowRef.current, sheetRowRef.current]
    if (!bar || rows.some((row) => !row)) return
    const needed = (row: Element | null) => Math.ceil(row?.getBoundingClientRect().width ?? 0)

    const measure = () => {
      const [full, compact, sheet] = rows.map(needed)
      const width = bar.clientWidth
      document.documentElement.style.setProperty('--topnav-height', `${bar.offsetHeight}px`)
      setLayout((previous) => {
        const available = previous.mode === 'sheet' ? width - SHEET_EXIT_SLACK : width
        const mode = available >= full ? 'full' : available >= compact ? 'compact' : 'sheet'
        const wordmark = mode === 'full' || (mode === 'sheet' && width >= sheet)
        return previous.mode === mode && previous.wordmark === wordmark ? previous : { mode, wordmark }
      })
    }

    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(bar)
    rows.forEach((row) => row && observer.observe(row))
    return () => {
      observer.disconnect()
      document.documentElement.style.removeProperty('--topnav-height')
    }
  }, [])

  useEffect(() => {
    const query = window.matchMedia(FINE_POINTER)
    const onChange = (event: MediaQueryListEvent) => setHasFinePointer(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  // The sheet and the popovers belong to different modes, so a mode change closes whichever is open
  useEffect(() => {
    if (layout.mode === 'sheet') setPopover(null)
    else setSheetOpen(false)
  }, [layout.mode])

  useEffect(() => {
    if (sheetOpen) closeSheet()
  }, [pathname])

  // While the sheet is open: move focus into it, freeze the page behind it, and keep the
  // scrollbar's width as padding so the bar doesn't shift when the scrollbar goes away
  useEffect(() => {
    if (!sheetOpen) return
    const { body, documentElement } = document
    const main = document.getElementById('main')
    const scrollbarWidth = window.innerWidth - documentElement.clientWidth
    main?.setAttribute('inert', '')
    body.style.overflow = 'hidden'
    if (scrollbarWidth > 0) body.style.paddingRight = `${scrollbarWidth}px`
    firstSheetLinkRef.current?.focus()
    return () => {
      main?.removeAttribute('inert')
      body.style.overflow = ''
      body.style.paddingRight = ''
    }
  }, [sheetOpen])

  useEffect(() => {
    if (!sheetOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeSheet()
        return
      }
      if (event.key !== 'Tab') return

      // Inert only covers <main>. This keeps Tab off the brand link, the skip link and the browser's own UI.
      const inside = sheetRef.current?.querySelectorAll<HTMLElement>('a[href], button') ?? []
      const focusable = [menuButtonRef.current, ...inside].filter((element): element is HTMLElement => !!element)
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement as HTMLElement | null
      if (!active || !focusable.includes(active)) {
        event.preventDefault()
        first.focus()
      } else if (event.shiftKey && active === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [sheetOpen])

  useEffect(() => {
    if (!popover) return
    const trigger = popover === 'help' ? helpButtonRef : accountButtonRef
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setPopover(null)
      trigger.current?.focus()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [popover])

  // The active link is bold, so measure them all that way or the bar could come up a few px short
  const measuredLinksAndActions = (
    <>
      <div className="topnav__links">
        {LINKS.map((link) => (
          <span key={link.to} className="topnav__link is-active">
            {link.label}
          </span>
        ))}
      </div>
      <div className="topnav__actions">
        <span className="iconbtn" />
        <span className="iconbtn" />
        {user || loading ? <span className="avatar" /> : <span className="btn btn--ghost btn--sm">Log in</span>}
      </div>
    </>
  )

  return (
    <header className="topnav" ref={barRef} data-mode={layout.mode ?? undefined}>
      <div className="topnav__measure" aria-hidden="true">
        <div className="topnav__measure-row" ref={fullRowRef}>
          <span className="topnav__brand">
            <span className="topnav__measure-logo" />
            <span>MotionBoxPro</span>
          </span>
          {measuredLinksAndActions}
        </div>
        <div className="topnav__measure-row" ref={compactRowRef}>
          <span className="topnav__brand">
            <span className="topnav__measure-logo" />
          </span>
          {measuredLinksAndActions}
        </div>
        <div className="topnav__measure-row topnav__measure-row--sheet" ref={sheetRowRef}>
          <span className="topnav__brand">
            <span className="topnav__measure-logo" />
            <span className="topnav__wordmark">MotionBoxPro</span>
          </span>
          <span className="topnav__toggle" />
        </div>
      </div>

      <Link to="/" className="topnav__brand" aria-label={layout.wordmark ? undefined : 'MotionBoxPro home'}>
        <LogoMark size={50} />
        {layout.wordmark && <span className="topnav__wordmark">MotionBoxPro</span>}
      </Link>

      <nav className="topnav__links" aria-label="Main">
        {LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) => `topnav__link${isActive ? ' is-active' : ''}`}
          >
            {link.label}
          </NavLink>
        ))}
      </nav>

      <div className="topnav__actions">
        <button
          ref={helpButtonRef}
          className="iconbtn"
          aria-label="Help"
          aria-expanded={popover === 'help'}
          aria-controls="topnav-help"
          onClick={() => setPopover(popover === 'help' ? null : 'help')}
        >
          <HelpIcon />
        </button>
        <NavLink
          to="/settings"
          className="iconbtn"
          aria-label="Settings"
          onClick={() => setPopover(null)}
        >
          <GearIcon />
        </NavLink>
        {!loading &&
          (user ? (
            <button
              ref={accountButtonRef}
              className="avatar"
              aria-label={`Account — ${displayName}`}
              aria-expanded={popover === 'account'}
              aria-controls="topnav-account"
              onClick={() => setPopover(popover === 'account' ? null : 'account')}
            >
              {initial}
            </button>
          ) : (
            <Link className="btn btn--ghost btn--sm" to="/login">
              Log in
            </Link>
          ))}
      </div>

      <button
        ref={menuButtonRef}
        type="button"
        className="topnav__toggle"
        aria-label={sheetOpen ? 'Close menu' : 'Menu'}
        aria-expanded={sheetOpen}
        aria-controls="topnav-sheet"
        onClick={() => (sheetOpen ? closeSheet() : setSheetOpen(true))}
      >
        {sheetOpen ? <CloseIcon size={22} /> : <MoreIcon size={26} />}
      </button>

      {popover === 'help' && (
        <div id="topnav-help" className="topnav__menu" role="dialog" aria-label="Help">
          <h4>Keyboard shortcuts</h4>
          <ShortcutList />
        </div>
      )}

      {popover === 'account' && user && (
        <div id="topnav-account" className="topnav__menu" role="dialog" aria-label="Account">
          <h4>{displayName}</h4>
          <p style={{ color: 'var(--muted)', fontSize: '13px', marginBottom: 12 }}>{user.email}</p>
          <Link className="menu-item" to="/settings" onClick={() => setPopover(null)}>
            Settings
          </Link>
          <Link className="menu-item" to="/recordings" onClick={() => setPopover(null)}>
            My recordings
          </Link>
          <button className="menu-item" onClick={signOut}>
            Sign out
          </button>
        </div>
      )}

      <div
        id="topnav-sheet"
        ref={sheetRef}
        className={`topnav__sheet${sheetOpen ? ' is-open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="Menu"
      >
        <div className="topnav__sheet-body">
          <nav aria-label="Main">
            <ul className="topnav__sheet-links">
              {LINKS.map((link, index) => (
                <li key={link.to}>
                  <NavLink
                    ref={index === 0 ? firstSheetLinkRef : undefined}
                    to={link.to}
                    className="topnav__sheet-link"
                    onClick={closeSheet}
                  >
                    {({ isActive }) => (
                      <>
                        <span className="topnav__sheet-label">{link.label}</span>
                        {isActive && (
                          <span className="topnav__sheet-current" aria-hidden="true">
                            Current page
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          <div className="topnav__sheet-utilities">
            <NavLink to="/settings" className="topnav__sheet-utility" onClick={closeSheet}>
              <GearIcon />
              Settings
            </NavLink>
            {hasFinePointer && (
              <>
                <button
                  type="button"
                  className="topnav__sheet-utility"
                  aria-expanded={shortcutsOpen}
                  aria-controls="topnav-sheet-shortcuts"
                  onClick={() => setShortcutsOpen(!shortcutsOpen)}
                >
                  <HelpIcon />
                  <span className="topnav__sheet-utility-label">Keyboard shortcuts</span>
                  <svg
                    className="topnav__chevron"
                    width="12"
                    height="8"
                    viewBox="0 0 12 8"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M1 1l5 5 5-5" />
                  </svg>
                </button>
                {shortcutsOpen && (
                  <div id="topnav-sheet-shortcuts" className="topnav__sheet-shortcuts">
                    <ShortcutList />
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {!loading &&
          (user ? (
            <div className="topnav__sheet-account">
              <span className="avatar" aria-hidden="true">
                {initial}
              </span>
              <div className="topnav__sheet-identity">
                <span className="topnav__sheet-name">{displayName}</span>
                <span className="topnav__sheet-email">{user.email}</span>
              </div>
              <button type="button" className="topnav__sheet-signout" onClick={signOut}>
                Sign out
              </button>
            </div>
          ) : (
            <Link className="topnav__sheet-login" to="/login" onClick={closeSheet}>
              Log in
            </Link>
          ))}
      </div>
    </header>
  )
}
