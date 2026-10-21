import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { GearIcon, HelpIcon, LogoMark } from '@/components/ui/Icons'
import { useAuth } from '@/app/AuthProvider'
import './TopNav.css'

const LINKS = [
  { to: '/projects', label: 'Projects' },
  { to: '/motions', label: 'Motions' },
  { to: '/recordings', label: 'Recordings' },
  { to: '/streaming', label: 'Streaming' },
]

export function TopNav() {
  const navigate = useNavigate()
  const [menu, setMenu] = useState<'help' | 'account' | null>(null)
  const { user, loading, logout } = useAuth()
  const displayName = user ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email : ''
  const initial = (user?.first_name || user?.email || '?').charAt(0).toUpperCase()

  return (
    <header className="topnav">
      <Link to="/" className="topnav__brand">
        <LogoMark size={50} />
        <span>MotionBoxPro</span>
      </Link>

      <nav className="topnav__links" aria-label="Main">
        {LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            className={({ isActive }) => `topnav__link${isActive ? ' is-active' : ''}`}
          >
            {link.label}
          </NavLink>
        ))}
      </nav>

      <div className="topnav__actions">
        <button
          className="iconbtn"
          aria-label="Help"
          aria-pressed={menu === 'help'}
          onClick={() => setMenu(menu === 'help' ? null : 'help')}
        >
          <HelpIcon />
        </button>
        <NavLink
          to="/settings"
          className="iconbtn"
          aria-label="Settings"
          onClick={() => setMenu(null)}
        >
          <GearIcon />
        </NavLink>
        {!loading &&
          (user ? (
            <button
              className="avatar"
              aria-label={`Account — ${displayName}`}
              onClick={() => setMenu(menu === 'account' ? null : 'account')}
            >
              {initial}
            </button>
          ) : (
            <Link className="btn btn--ghost btn--sm" to="/login">
              Log in
            </Link>
          ))}
      </div>

      {menu === 'help' && (
        <div className="topnav__menu" role="dialog" aria-label="Help">
          <h4>Keyboard shortcuts</h4>
          <dl>
            <dt>R</dt>
            <dd>Start / stop a take</dd>
            <dt>Space</dt>
            <dd>Play or pause the viewport</dd>
            <dt>C</dt>
            <dd>Recalibrate the suit</dd>
          </dl>
        </div>
      )}

      {menu === 'account' && user && (
        <div className="topnav__menu" role="dialog" aria-label="Account">
          <h4>{displayName}</h4>
          <p style={{ color: 'var(--muted)', fontSize: '13px', marginBottom: 12 }}>{user.email}</p>
          <Link className="menu-item" to="/settings" onClick={() => setMenu(null)}>
            Settings
          </Link>
          <Link className="menu-item" to="/recordings" onClick={() => setMenu(null)}>
            My recordings
          </Link>
          <button
            className="menu-item"
            onClick={async () => {
              setMenu(null)
              await logout()
              navigate('/')
            }}
          >
            Sign out
          </button>
        </div>
      )}
    </header>
  )
}
