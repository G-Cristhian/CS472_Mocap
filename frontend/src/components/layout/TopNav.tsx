import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { GearIcon, HelpIcon, LogoMark, SearchIcon } from '@/components/ui/Icons'
import { currentUser } from '@/lib/data'
import './TopNav.css'

const LINKS = [
  { to: '/', label: 'Home', end: true },
  { to: '/record', label: 'Record' },
  { to: '/projects', label: 'Projects' },
  { to: '/library', label: 'Motion Library' },
]

export function TopNav() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [menu, setMenu] = useState<'help' | 'account' | null>(null)

  return (
    <header className="topnav">
      <Link to="/" className="topnav__brand">
        <LogoMark />
        <span>[APP NAME]</span>
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

      <form
        className="topnav__search search"
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          navigate(`/library?q=${encodeURIComponent(query)}`)
        }}
      >
        <SearchIcon />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search projects and clips"
          aria-label="Search projects and clips"
        />
      </form>

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
        <button
          className="avatar"
          aria-label={`Account — ${currentUser.name}`}
          onClick={() => setMenu(menu === 'account' ? null : 'account')}
        >
          {currentUser.initial}
        </button>
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
            <dt>/</dt>
            <dd>Jump to search</dd>
          </dl>
        </div>
      )}

      {menu === 'account' && (
        <div className="topnav__menu" role="dialog" aria-label="Account">
          <h4>{currentUser.name}</h4>
          <p style={{ color: 'var(--muted)', fontSize: '13px', marginBottom: 12 }}>
            Wearing {currentUser.suit} · calibrated
          </p>
          <Link className="menu-item" to="/settings" onClick={() => setMenu(null)}>
            Settings
          </Link>
          <Link className="menu-item" to="/library" onClick={() => setMenu(null)}>
            My clips
          </Link>
          <button className="menu-item" onClick={() => setMenu(null)}>
            Sign out
          </button>
        </div>
      )}
    </header>
  )
}
