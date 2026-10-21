import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Motion } from '@/types'
import { AddToProjectDialog } from './AddToProjectDialog'
import { MoreIcon } from './Icons'
import { StickFigure } from './StickFigure'
import './cards.css'

export function MotionCard({ motion }: { motion: Motion }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [adding, setAdding] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // a click anywhere else closes the menu
  useEffect(() => {
    if (!menuOpen) return
    const onDown = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onDown)

    return () => document.removeEventListener('mousedown', onDown)
  }, [menuOpen])

  return (
    <div className="mcard-wrap">
      <Link className="mcard" to={`/motions/${motion.id}`}>
        <div className="mcard__stage">
          <StickFigure pose={motion.pose} color={`var(--${motion.accent})`} size={112} strokeWidth={6} />
          {motion.duration && <span className="mcard__time">{motion.duration}</span>}
        </div>
        <p className="mcard__name">{motion.name}</p>
        <p className="mcard__project">{motion.projects.map((p) => p.name).join(' · ') || 'No project'}</p>
      </Link>

      <div className="mcard-menu" ref={menuRef}>
        <button
          type="button"
          className="mcard-menu__btn"
          aria-label={`Actions for ${motion.name}`}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <MoreIcon />
        </button>
        {menuOpen && (
          <div className="mcard-menu__list" role="menu">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false)
                setAdding(true)
              }}
            >
              Add to project
            </button>
          </div>
        )}
      </div>

      {adding && <AddToProjectDialog motion={motion} onClose={() => setAdding(false)} />}
    </div>
  )
}
